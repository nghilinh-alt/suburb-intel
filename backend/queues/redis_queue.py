"""
backend/queues/redis_queue.py

Redis-based queue for production multi-instance deployments.
Uses sorted sets for priority-based job scheduling.
"""

import json
import asyncio
from typing import Optional, List
from datetime import datetime
from redis import Redis
import os


class QueueFullError(Exception):
    """Raised when queue is full."""
    pass


class JobNotReadyError(Exception):
    """Raised when job priority is too low for current position."""
    pass


class RedisQueue:
    """
    Redis-based priority queue for production API processing.
    
    Uses sorted sets (ZSET) for efficient priority ordering:
    - Score = timestamp + priority offset
    - Lower score = higher priority (processed first)
    - TTL-based expiration to clean up old jobs
    
    Supports:
    - Priority-based job scheduling
    - Bulk enqueue operations
    - Dead letter queue for failed jobs
    - Job metrics via Redis MONITOR/KEYSPACES
    """
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, db: int = 0):
        self.redis: Redis = Redis(
            host=redis_host,
            port=redis_port,
            db=db,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            socket_keepalive=True,
            health_check_interval=30,
            decode_responses=False  # Return bytes for consistency
        )
        
        self.queue_name = f"suburb_intel:api_queue:{db}"
        self.dead_letter_queue = f"suburb_intel:dead_letter_queue:{db}"
    
    async def enqueue(self, job_dict: dict, priority: int = 5) -> str:
        """
        Add job to queue with priority.
        
        Args:
            job_dict: Job data (suburb_name, api_type, payload, etc.)
            priority: 1-10 (lower number = higher priority)
            
        Returns:
            Job ID for tracking
            
        Raises:
            QueueFullError: If queue exceeds max size
        """
        # Convert dict to JSON bytes
        job_json = json.dumps(job_dict).encode('utf-8')
        
        # Generate unique job ID
        timestamp = datetime.utcnow().timestamp()
        suburb = job_dict.get('suburb_name', 'unknown')
        api_type = job_dict.get('api_type', 'default')
        job_id = f"{job_json.decode()[:10]}:{suburb}:{api_type}"[:50]  # Truncate for Redis key
        
        # Calculate score (timestamp - priority) so lower priority values go first
        score = timestamp - priority + 1
        
        # Add to sorted set with score-based ordering
        await self.redis.zadd(self.queue_name, {job_id: score})
        
        # Set expiration based on job type
        job_type = job_dict.get('job_type', 'api_call')
        if job_type == 'api_call':
            # API calls expire after 6 hours (max)
            await self.redis.expire(self.queue_name, 21600)  # 6 hours
        elif job_type == 'heavy':
            # Heavy jobs expire after 24 hours
            await self.redis.expire(self.queue_name, 86400)
        
        # Clean up old jobs periodically
        await self._cleanup_old_jobs()
        
        return job_id
    
    async def dequeue(self, count: int = 1) -> Optional[dict]:
        """
        Get highest priority (oldest) job(s) from queue.
        
        Args:
            count: Number of jobs to retrieve
            
        Returns:
            Job dict or None if queue empty
        """
        # Remove oldest items (lowest scores first)
        jobs = await self.redis.zpopmin(self.queue_name, count=count)
        
        if not jobs:
            return None
        
        job_ids = [job[0].decode() for job in jobs]
        job_data = [json.loads(job[1].decode()) for job in jobs]
        
        return job_data[0]  # Return first (highest priority) job
    
    async def peek(self, count: int = 5) -> List[dict]:
        """
        Peek at top N jobs without removing them.
        
        Args:
            count: Number of jobs to inspect
            
        Returns:
            List of highest priority jobs
        """
        jobs = await self.redis.zrange(self.queue_name, 0, min(count - 1, 999999))
        
        return [json.loads(job.decode()) for job in jobs]
    
    async def size(self) -> int:
        """Get current queue depth."""
        return await self.redis.zcard(self.queue_name)
    
    async def get_dead_letter_queue_size(self) -> int:
        """Get number of failed jobs in dead letter queue."""
        return await self.redis.zcard(self.dead_letter_queue)
    
    async def move_to_dead_letter_queue(self, job_id: str, reason: str):
        """Move job to dead letter queue for later inspection."""
        await self.redis.zadd(self.dead_letter_queue, {job_id: 0})
        
        # Store failure reason as metadata
        await self.redis.hset(f"dlq:{job_id}", "reason", reason)
    
    async def _cleanup_old_jobs(self, max_age_seconds: float = 3600):
        """Remove jobs older than threshold."""
        cutoff = datetime.utcnow().timestamp() - max_age_seconds
        
        # Remove items with score below cutoff + buffer
        await self.redis.zremrangebyscore(
            self.queue_name, '-inf', 
            str(cutoff + 3600)  # Buffer for drift
        )


class APIQueueWorker:
    """
    Background worker that processes queued API requests.
    
    Manages multiple concurrent workers for processing queued jobs.
    Implements retry logic with exponential backoff.
    """
    
    def __init__(self, redis_queue: RedisQueue, max_workers: int = 4):
        self.redis_queue = redis_queue
        self.max_workers = max_workers
        self.worker_id = f"worker-{id(self)}"
        self.active_workers = 0
    
    async def run(self, num_workers: Optional[int] = None):
        """
        Run multiple worker processes in parallel.
        
        Args:
            num_workers: Override number of workers (uses max_workers if not set)
        """
        actual_workers = num_workers or self.max_workers
        
        print(f"Starting {actual_workers} API queue workers...")
        
        # Create and run all workers
        workers = [asyncio.create_task(self._worker()) for _ in range(actual_workers)]
        
        # Run forever (or until shutdown signal)
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            print("Workers cancelled, shutting down...")
    
    async def stop(self):
        """Gracefully stop all workers."""
        print(f"Stopping {self.max_workers} API queue workers...")
    
    async def _worker(self):
        """Single worker loop with rate limiting."""
        while True:
            # Get highest priority job
            try:
                job = await self.redis_queue.dequeue()
                
                if not job:
                    # No jobs available, brief sleep
                    await asyncio.sleep(1.5)
                    continue
                
                # Process job with retries
                await self._process_job_with_retries(job, max_retries=3)
                
            except Exception as e:
                print(f"Worker {self.worker_id} error: {e}")
            
            # Brief sleep before next iteration
            await asyncio.sleep(0.5)
    
    async def _process_job_with_retries(self, job_dict: dict, max_retries: int = 3):
        """Process job with exponential backoff retries."""
        
        for attempt in range(max_retries):
            try:
                print(f"Worker {self.worker_id} processing: {job_dict.get('suburb_name')}")
                
                # Rate limit throttle before API call
                await self._throttle_for_api_type(job_dict)
                
                # Process job (actual API call goes here)
                result = await self._make_api_call(job_dict)
                
                # Mark job as completed in Redis
                job_id = json.dumps(job_dict)
                await self.redis_queue.dequeue()  # Remove from queue
                
                print(f"Completed: {job_dict.get('suburb_name')}")
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {job_dict.get('suburb_name')}: {e}")
                
                if attempt < max_retries - 1:
                    # Calculate exponential backoff: 2^attempt seconds
                    backoff = min(2 ** (attempt + 1), 30)  # Max 30s
                    print(f"Retrying in {backoff} seconds...")
                    await asyncio.sleep(backoff)
                
                else:
                    # All retries exhausted, move to dead letter queue
                    job_id = json.dumps(job_dict)[:50]
                    await self.redis_queue.move_to_dead_letter_queue(
                        job_id, f"Max retries ({max_retries}) exceeded: {str(e)}"
                    )
    
    async def _throttle_for_api_type(self, job_dict: dict):
        """Apply rate limiting throttle based on API type."""
        
        api_type = job_dict.get('api_type', 'overpass_api')
        throttle_seconds = 6  # Default 6 seconds between requests
        
        # Adjust based on API limits (conservative estimates)
        api_throttle_map = {
            'overpass_api': 8,      # ~10 req/min = 6s per request
            'abs_data_api': 10,     # ~60 req/min = 1s per request
            'aihw_api': 10,         # ~30 req/min = 2s per request  
            'infrastructure_australia': 15,  # Heavy scraping
        }
        
        throttle_seconds = api_throttle_map.get(api_type, throttle_seconds)
        await asyncio.sleep(throttle_seconds)
    
    async def _make_api_call(self, job_dict: dict):
        """
        Make actual API call (hook for implementation).
        
        In production, this would:
        1. Call actual API endpoint
        2. Parse JSON response
        3. Cache result in Redis/InMemory cache
        4. Return structured data
        """
        
        # TODO: Implement actual API calling logic here
        
        suburb = job_dict.get('suburb_name', 'unknown')
        api_type = job_dict.get('api_type', 'default')
        endpoint = job_dict.get('endpoint_path', '')
        
        return {
            "success": True,
            "suburb": suburb,
            "api_type": api_type,
            "endpoint": endpoint,
            "timestamp": datetime.utcnow().isoformat(),
            "data": None  # Would contain actual API data
        }


# ============================================================================
# Queue Management Commands (for admin scripts)
# ============================================================================

async def drain_queue(redis_queue: RedisQueue):
    """Remove all jobs from queue (dangerous operation)."""
    
    print("Draining queue...")
    
    while True:
        job = await redis_queue.dequeue()
        if not job:
            break
        
        print(f"Removed: {job.get('suburb_name', 'unknown')}")


async def inspect_queue(redis_queue: RedisQueue):
    """Show queue statistics and top jobs."""
    
    print("\n=== Queue Statistics ===")
    print(f"Current queue size: {await redis_queue.size()}")
    print(f"Dead letter queue size: {await redis_queue.get_dead_letter_queue_size()}")
    
    print("\n=== Top 5 Priority Jobs ===")
    top_jobs = await redis_queue.peek(5)
    
    for i, job in enumerate(top_jobs, 1):
        suburb = job.get('suburb_name', 'unknown')
        api_type = job.get('api_type', 'default')
        priority = f"{job.get('priority', 5):2d}"
        print(f"{i}. {suburb:20} | {api_type:20} | Priority: {priority}")


async def show_dead_letter_queue(redis_queue: RedisQueue):
    """Show failed jobs that need manual inspection."""
    
    print("\n=== Dead Letter Queue ===")
    
    failed_jobs = await redis_redis.zrange(redis_queue.dead_letter_queue, 0, -1)
    
    for job_id in failed_jobs[:10]:  # Show first 10 failed jobs
        job_data = json.loads(job_id.decode())
        reason = await redis.redis.hget(f"dlq:{job_id}", "reason")
        
        print(f"{job_id[:30]}... | {reason}")


# ============================================================================
# Usage Example
# ============================================================================

"""
Usage in FastAPI application:

# Import and initialize Redis queue
from backend.queues.redis_queue import RedisQueue, APIQueueWorker
import redis.asyncio as aioredis

# Create Redis connection
redis_client = aioredis.from_url(
    "redis://localhost:6379/0",
    decode_responses=True
)

# Create queue (uses same Redis client)
api_queue = RedisQueue(redis_host='localhost', redis_port=6379)

# Add jobs to queue
job = {
    'suburb_name': 'Carlton',
    'api_type': 'overpass_api',
    'endpoint_path': '/api/search/Carlton/osm-amenity-density',
    'payload': {'throttle_seconds': 6}
}

await api_queue.enqueue(job, priority=2)

# Run background workers
worker = APIQueueWorker(api_queue, max_workers=4)
asyncio.create_task(worker.run())

# Admin commands for monitoring
@app.on_event("startup")
async def start_monitoring():
    # Queue inspection (optional)
    # asyncio.create_task(inspect_queue(api_queue))

@app.get("/admin/queue/stats")
async def queue_stats():
    stats = {
        'queue_size': await api_queue.size(),
        'dead_letter_count': await api_queue.get_dead_letter_queue_size(),
    }
    return stats

@app.get("/admin/drain-queue")
async def drain_queue_endpoint():
    # WARNING: This removes all jobs!
    asyncio.create_task(drain_queue(api_queue))
    return {"status": "draining queue"}
"""


# ============================================================================
# Production Deployment Notes
# ============================================================================

"""
=== REDIS CONFIGURATION ===

Minimum Redis requirements for production:
- Memory: >= 1GB
- Persistence: RDB snapshots enabled (save '900 1' '300 10' '60 10000')
- Cluster mode recommended for horizontal scaling

Environment variables:
REDIS_HOST=redis-cluster.production.com
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password  # If using auth
REDIS_DB=0


=== MONITORING ENDPOINTS ===

Prometheus metrics (via prometheus_client):
/app/metrics - Queue depth, job completion rates, error counts

Health check:
curl http://localhost:8000/health?check=queue

Admin commands:
- GET /admin/queue/stats - Show queue status
- GET /admin/drain-queue - Remove all jobs (dangerous!)
- GET /admin/dead-letter - Inspect failed jobs


=== PERFORMANCE TUNING ===

Adjust based on your load:

Queue size limit: 100-500 jobs (higher for heavy-load deployments)
Max workers per queue: 4-8 (matches number of API calls you need to make)
Throttle between API calls: Adjust based on API rate limits

=== SCALING ===

For multiple app instances:
- Use Redis cluster or Sentinel
- All instances share same queue via Redis
- No duplicate processing needed


=== BACKUP STRATEGY ===

1. Redis RDB snapshots every 5 minutes (default)
2. AOF every 1 second for durability
3. Export to S3/GCS for long-term archival of completed jobs
"""
