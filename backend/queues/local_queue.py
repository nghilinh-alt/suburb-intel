"""
backend/queues/local_queue.py

Simple in-memory queue for local development and staging environments.
Uses asyncio.Queue with TTL-based cleanup to prevent memory bloat.
"""

import asyncio
from typing import Dict, Optional
from collections import deque
import time
import json
import os
from datetime import datetime
from enum import Enum

class JobStatus(Enum):
    """Job processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundJob:
    """Represents a background job to be processed."""
    
    def __init__(self, job_type: str, suburb_name: Optional[str], 
                 api_type: Optional[str], endpoint_path: Optional[str],
                 payload: Dict, priority: int = 5):
        self.job_id = f"{job_type}:{suburb_name or 'unknown'}:{api_type or endpoint_path or ''}"
        self.job_type = job_type
        self.suburb_name = suburb_name
        self.api_type = api_type
        self.endpoint_path = endpoint_path
        self.payload = payload
        self.priority = priority  # Lower number = higher priority (1-10)
        self.status = JobStatus.PENDING
        self.result_data: Optional[dict] = None
        self.error_message: Optional[str] = None
        self.attempt_count = 0
    
    def to_dict(self) -> dict:
        """Convert job to dictionary for storage."""
        return {
            'job_id': self.job_id,
            'job_type': self.job_type,
            'suburb_name': self.suburb_name,
            'api_type': self.api_type,
            'endpoint_path': self.endpoint_path,
            'payload': self.payload,
            'priority': self.priority,
            'status': self.status.value,
            'result_data': self.result_data,
            'error_message': self.error_message,
            'attempt_count': self.attempt_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BackgroundJob':
        """Create job from dictionary."""
        return cls(
            job_type=data['job_type'],
            suburb_name=data.get('suburb_name'),
            api_type=data.get('api_type'),
            endpoint_path=data.get('endpoint_path'),
            payload=data.get('payload', {}),
            priority=data.get('priority', 5),
        )


class LocalQueue:
    """
    Simple in-memory queue for local development/staging.
    
    Features:
    - Priority-based job ordering
    - TTL-based cleanup of old jobs
    - Job processing callbacks
    - Thread-safe async operations
    """
    
    def __init__(self, max_size: int = 500, default_ttl_seconds: int = 3600):
        self.queue: deque = deque()
        self.max_size = max_size
        self.default_ttl = default_ttl_seconds
        self.processing_callbacks: list = []
    
    async def enqueue(self, job: BackgroundJob) -> bool:
        """
        Add job to queue with priority ordering.
        
        Args:
            job: BackgroundJob instance to queue
            
        Returns:
            True if enqueued successfully, False if queue is full
        """
        if len(self.queue) >= self.max_size:
            # Remove oldest jobs to make space for high-priority jobs
            while len(self.queue) >= self.max_size - 10:
                oldest = self.queue.popleft()
                await self._handle_failed_job(oldest, "Queue full")
            else:
                raise RuntimeError(f"Queue full at {len(self.queue)} items")
        
        # Use priority as timestamp for ordering (lower priority value = earlier)
        import random
        job.timestamp = time.time() - job.priority + random.uniform(-100, 0)
        
        self.queue.append(job)
        return True
    
    async def dequeue(self, timeout: float = 1.0) -> Optional[BackgroundJob]:
        """
        Get next job from queue based on priority.
        
        Args:
            timeout: Seconds to wait for job availability
            
        Returns:
            BackgroundJob or None if no jobs available
        """
        deadline = time.time() + timeout
        
        while True:
            # Sort by priority (lower number first) and timestamp
            if self.queue:
                sorted_queue = sorted(self.queue, key=lambda j: j.priority)
                
                for job in sorted_queue[:5]:  # Look at top 5 highest priority jobs
                    if time.time() - job.timestamp < self.default_ttl:
                        return job
            
            # No suitable job available, wait briefly
            if len(self.queue) > 0:
                await asyncio.sleep(0.5)
            else:
                return None
    
    async def size(self) -> int:
        """Get current queue depth."""
        return len(self.queue)
    
    async def clear_old_jobs(self, max_age_seconds: float = 3600):
        """Remove jobs older than threshold."""
        cutoff = time.time() - max_age_seconds
        
        # Filter out old jobs
        new_queue = []
        for job in self.queue:
            if time.time() - job.timestamp < max_age_seconds:
                new_queue.append(job)
            
            else:
                await self._handle_failed_job(job, "Expired")
        
        # Replace queue with filtered items
        self.queue.clear()
        self.queue.extend(new_queue)
    
    def get_statistics(self) -> dict:
        """Get queue statistics."""
        total = len(self.queue)
        priorities = {}
        
        for job in self.queue:
            priority_key = str(job.priority)
            priorities[priority_key] = priorities.get(priority_key, 0) + 1
        
        return {
            'total_jobs': total,
            'high_priority_1_2': sum(1 for j in self.queue if j.priority <= 2),
            'medium_priority_3_5': sum(1 for j in self.queue if 3 <= j.priority <= 5),
            'low_priority_6_plus': sum(1 for j in self.queue if j.priority > 5),
            'priorities': priorities,
        }
    
    async def _handle_failed_job(self, job: BackgroundJob, reason: str):
        """Mark job as failed and trigger callbacks."""
        job.status = JobStatus.FAILED
        job.error_message = f"Failed: {reason}"
        
        # Trigger completion callbacks
        for callback in self.processing_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(job)
                else:
                    callback(job)
            except Exception as e:
                print(f"Callback error: {e}")


class BackgroundWorker:
    """
    Worker that processes jobs from the queue.
    
    Can run multiple concurrent workers to process jobs in parallel.
    """
    
    def __init__(self, queue: LocalQueue, max_workers: int = 4):
        self.queue = queue
        self.max_workers = max_workers
        self.worker_count = 0
    
    async def start(self):
        """Start background worker loop."""
        workers = [asyncio.create_task(self._worker()) for _ in range(self.max_workers)]
        
        # Run forever or until shutdown signal
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            pass
    
    async def stop(self):
        """Stop all workers."""
        self.worker_count = 0
    
    async def _worker(self):
        """Single worker loop."""
        while True:
            job = await self.queue.dequeue(timeout=2.0)
            
            if not job:
                continue
            
            print(f"Worker {self.worker_count} processing job: {job.job_id}")
            
            try:
                # Process job (with rate limiting throttle)
                if 'api_type' in job.payload:
                    await asyncio.sleep(job.payload.get('throttle_seconds', 6))
                
                result = await self._process_job(job)
                
                # Update job status
                job.status = JobStatus.COMPLETED
                job.result_data = result
                
            except Exception as e:
                print(f"Job failed: {job.job_id}, error: {e}")
                job.status = JobStatus.FAILED
                job.error_message = str(e)
            
            self.worker_count += 1
    
    async def _process_job(self, job: BackgroundJob):
        """Process a background job (hook for implementation)."""
        
        # TODO: Implement actual API call processing here
        print(f"Processing {job.job_type} for {job.suburb_name}")
        
        return {"success": True, "processed_at": datetime.utcnow().isoformat()}


# ============================================================================
# Usage Example
# ============================================================================

"""
Usage in FastAPI application:

# Import and initialize queue
from backend.queues.local_queue import LocalQueue, BackgroundWorker

# Create queue
api_queue = LocalQueue(max_size=500)

# Add jobs to queue
job = BackgroundJob(
    job_type='api_call',
    suburb_name='Carlton',
    api_type='overpass_api',
    endpoint_path='/api/search/Carlton/osm-amenity-density',
    payload={
        'throttle_seconds': 6,
        'cache_key': 'osm:amenity_density:Carlton'
    },
    priority=2  # High priority
)

await api_queue.enqueue(job)

# Start background worker
worker = BackgroundWorker(api_queue, max_workers=4)
asyncio.create_task(worker.start())

# Queue metrics endpoint for monitoring
from fastapi import APIRouter
from backend.queues.local_queue import api_queue

router = APIRouter(prefix="/internal/queue")

@router.get("/stats")
async def queue_stats():
    stats = api_queue.get_statistics()
    return {
        'queue_size': await api_queue.size(),
        'statistics': stats,
    }
"""
