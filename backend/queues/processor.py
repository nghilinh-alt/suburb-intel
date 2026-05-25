"""
backend/queues/processor.py

Queue processor that coordinates API calls with caching and rate limiting.
Orchestrates background job processing in coordination with cache layer.
"""

import json
from typing import Optional, Dict, Any
from datetime import datetime
from starlette.background import BackgroundTask
import asyncio


class QueueProcessor:
    """
    Processor that handles queued API calls with caching and rate limiting.
    
    Responsibilities:
    1. Retrieve jobs from queue
    2. Rate limit throttle before API calls
    3. Cache results in local/Redis
    4. Track metrics for monitoring
    
    Can be used standalone or integrated with FastAPI middleware.
    """
    
    def __init__(self, cache_layer=None, redis_client=None):
        self.cache_layer = cache_layer
        self.redis_client = redis_client
        self.rate_limit_config = {
            'overpass_api': 8,        # seconds between requests
            'abs_data_api': 10,
            'aihw_api': 10,
            'infrastructure_australia': 15,
        }
    
    async def process_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single queued API call.
        
        Args:
            job_data: Dictionary with job details from queue
            
        Returns:
            Dictionary with processing result
        """
        
        suburb_name = job_data.get('suburb_name', 'unknown')
        api_type = job_data.get('api_type', 'unknown')
        endpoint_path = job_data.get('endpoint_path', '')
        payload = job_data.get('payload', {})
        
        # Build cache key
        cache_key = f"{api_type}:{suburb_name}"
        
        # Check cache first (if available)
        cached_data = None
        if self.cache_layer:
            try:
                cached_data = await self._get_from_cache(cache_key)
                if cached_data:
                    return {
                        'success': True,
                        'suburb_name': suburb_name,
                        'api_type': api_type,
                        'cache_hit': True,
                        'data': json.loads(cached_data) if isinstance(cached_data, bytes) else cached_data
                    }
            except Exception as e:
                pass  # Cache failure is not critical
        
        # Rate limit throttle
        throttle_seconds = payload.get('throttle_seconds', 
                                       self.rate_limit_config.get(api_type, 6))
        
        await asyncio.sleep(throttle_seconds)
        
        # Make API call (hook for implementation)
        api_data = await self._make_api_call(
            suburb_name=suburb_name,
            api_type=api_type,
            endpoint_path=endpoint_path
        )
        
        # Cache result
        if cache_key and self.cache_layer:
            await self._set_cache(cache_key, api_data)
        
        return {
            'success': True,
            'suburb_name': suburb_name,
            'api_type': api_type,
            'endpoint_path': endpoint_path,
            'cache_hit': False,
            'data': api_data,
            'processing_time_ms': None  # Would track in production
        }
    
    async def process_batch(self, jobs: list) -> list:
        """
        Process multiple jobs with rate limiting between them.
        
        Args:
            jobs: List of job dictionaries to process
            
        Returns:
            List of processing results
        """
        
        results = []
        
        for i, job in enumerate(jobs):
            result = await self.process_job(job)
            results.append(result)
            
            # Brief pause between requests (prevents accidental rate limit hits)
            if i < len(jobs) - 1:
                await asyncio.sleep(2)
        
        return results
    
    async def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """Get cached data (implementation depends on cache layer)."""
        
        from cachetools import TTLCache
        
        if not self.cache_layer:
            return None
        
        try:
            return self.cache_layer.get(cache_key)
        except Exception:
            return None
    
    async def _set_cache(self, cache_key: str, data: Any):
        """Set cached data (implementation depends on cache layer)."""
        
        if not self.cache_layer:
            return
        
        try:
            # Convert to JSON string for storage
            import json
            self.cache_layer[cache_key] = json.dumps(data)
        except Exception as e:
            print(f"Cache set failed for {cache_key}: {e}")
    
    async def _make_api_call(self, suburb_name: str, api_type: str, 
                            endpoint_path: str) -> Dict[str, Any]:
        """
        Make actual API call to external service.
        
        This is the main implementation hook - replace with real API calls.
        """
        
        # TODO: Implement real API calls here
        
        # Example implementations:
        
        # ABS Census API:
        # async def fetch_abs_population(suburb_name: str) -> dict:
        #     from requests import get
        #     response = get(f'https://api.abs.gov.au/v1/data/Census2021/PopulationByAge',
        #                    params={'SA3': suburb_code})
        #     return response.json()
        
        # Overpass API:
        # async def fetch_osm_amenities(suburb_name: str) -> dict:
        #     from requests import get
        #     query = f'''
        #         [out:json][timeout:25]
        #         {{
        #             area.search["name":"{suburb_name}"];
        #             (
        #                 node["amenity"]("cafe", "restaurant", "shop");
        #             );
        #             out count;
        #         }}'''
        #     response = get('https://overpass-api.de/api/interpreter', params={'data': query})
        #     return response.json()
        
        # For MVP testing, return mock data
        return {
            "success": True,
            "suburb": suburb_name,
            "api_type": api_type,
            "endpoint": endpoint_path,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "message": f"API call completed for {suburb_name}",
            "data": None  # Would contain actual API response
        }


# ============================================================================
# Batch Job Processor
# ============================================================================

async def process_batch_with_rate_limiting(jobs: list, rate_limit_seconds: int = 6) -> list:
    """
    Process batch of jobs with configurable rate limiting.
    
    Args:
        jobs: List of job dictionaries
        rate_limit_seconds: Seconds between each request
    
    Returns:
        List of processing results
    """
    
    results = []
    
    for i, job in enumerate(jobs):
        # Process single job
        result = await process_job(job)
        results.append(result)
        
        # Rate limit throttle between requests
        if i < len(jobs) - 1:
            await asyncio.sleep(rate_limit_seconds)
    
    return results


async def process_job(job_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to process single job.
    Useful for cron jobs or external processors.
    """
    
    suburb_name = job_dict.get('suburb_name', 'unknown')
    api_type = job_dict.get('api_type', 'overpass_api')
    endpoint_path = job_dict.get('endpoint_path', '')
    payload = job_dict.get('payload', {})
    
    # Build cache key
    cache_key = f"{api_type}:{suburb_name}"
    
    # Check cache first
    cached_data = None
    
    # Try Redis if available
    redis_host = 'localhost'
    redis_client = None  # In production, would connect to Redis
    
    try:
        from redis import Redis
        redis_client = Redis(host=redis_host, port=6379)
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return {
                'success': True,
                'suburb_name': suburb_name,
                'api_type': api_type,
                'cache_hit': True,
                'data': json.loads(cached_data.decode())
            }
    except ImportError:
        pass
    
    # Rate limit throttle
    throttle_seconds = payload.get('throttle_seconds', 6)
    await asyncio.sleep(throttle_seconds)
    
    # Make API call (would implement here)
    api_data = {
        "suburb": suburb_name,
        "api_type": api_type,
        "endpoint": endpoint_path,
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }
    
    # Cache result
    if redis_client:
        import json
        redis_client.setex(cache_key, 3600, json.dumps(api_data))
    
    return {
        'success': True,
        'suburb_name': suburb_name,
        'api_type': api_type,
        'cache_hit': False,
        'data': api_data
    }


# ============================================================================
# Usage Example with FastAPI Integration
# ============================================================================

"""
Usage in FastAPI application:

from fastapi import FastAPI
from backend.queues.processor import QueueProcessor, process_job

app = FastAPI()

# Initialize processor
processor = QueueProcessor(cache_layer=TTLCache(maxsize=1000, ttl=86400))

# Background worker that processes jobs
@app.on_event("startup")
async def startup():
    asyncio.create_task(background_worker())

async def background_worker():
    """Process queued API calls."""
    while True:
        # Wait for new job from queue
        job = await api_queue.dequeue()
        
        if not job:
            continue
        
        # Process job (with rate limiting)
        result = await processor.process_job(job)
        
        # Log result
        print(f"Processed {job['suburb_name']}: {result.get('success')}")

# Admin endpoint to add jobs
@app.post("/admin/add-job")
async def add_api_job(suburb_name: str, api_type: str):
    """Add new API call to queue."""
    
    job = BackgroundJob.create_api_call_job(
        suburb_name=suburb_name,
        api_type=api_type,
        endpoint_path=f"/api/search/{suburb_name}/{api_type}"
    )
    
    # Validate and enqueue
    if job.validate():
        await api_queue.enqueue(job)
    
    return {"status": "queued", "job_id": job.job_id}

# Admin endpoint to check queue status
@app.get("/admin/queue/stats")
async def queue_stats():
    """Get queue statistics."""
    
    stats = {
        'current_depth': await api_queue.size(),
        'pending_jobs': 42,  # Would be actual count
    }
    
    return stats

# Process queued jobs with batch mode (for bulk data refreshes)
@app.post("/admin/bulk-refresh")
async def bulk_refresh_suburb_data(suburbs: list):
    """Queue bulk suburb data refresh."""
    
    jobs = []
    for suburb in suburbs:
        job = BackgroundJob.create_abs_population_job(suburb)
        jobs.append(job.to_dict())
    
    # Process all with rate limiting (batch mode)
    results = await process_batch_with_rate_limiting(jobs, rate_limit_seconds=10)
    
    return {
        'processed': len(results),
        'successful': sum(1 for r in results if r.get('success')),
        'failed': sum(1 for r in results if not r.get('success'))
    }
"""
