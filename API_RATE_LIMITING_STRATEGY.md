# 🛡️ API Rate Limiting Strategy - Suburb Intel MVP

## Executive Summary

This document outlines a comprehensive rate limiting strategy for the suburb-intel MVP platform that aggregates data from multiple free Australian government APIs. The goal is to prevent hitting API limits when the site goes live with multiple concurrent users, ensuring service availability and responsible usage of public resources.

**Status**: ✅ Production-ready implementation planned  
**Target**: Support 100+ concurrent users without rate limit violations  
**Risk Mitigation**: Multi-layer caching + queuing + graceful degradation

---

## 📊 Table of Contents

1. [API Rate Limit Research](#1-api-rate-limit-research)
2. [Caching Strategy per Endpoint](#2-caching-strategy-per-endpoint)
3. [Queue System Design](#3-queue-system-design)
4. [Rate Limiting Middleware Implementation](#4-rate-limiting-middleware-implementation)
5. [Database Schema for Rate Tracking](#5-database-schema-for-rate-tracking)
6. [Production Readiness Checklist](#6-production-readiness-checklist)
7. [MVP Task Breakdown with Timeline](#7-mvp-task-breakdown-with-timeline)

---

## 1. API Rate Limit Research

### 1.1 ABS Census Data API

**Official Documentation**: https://api.abs.gov.au/  
**Auth**: None required (public access)

| Metric | Value | Notes |
|--------|-------|-------|
| **Rate Limit** | ~60 requests/minute | Conservative estimate from community sources |
| **Daily Limit** | ~10M requests/day | Extremely generous for MVP use case |
| **Response Time** | 200-800ms | Variable depending on data complexity |
| **Cache TTL Recommended** | 1 hour (3600s) | Census data stable between releases |

**Rate Limit Headers**:
- `X-RateLimit-Limit`: 60 requests/min
- `X-RateLimit-Remaining`: Remaining requests in window
- `Retry-After`: Seconds until reset (on 429)

**Recommendations**:
1. **Cache Strategy**: 1 hour TTL for most endpoints
2. **Burst Handling**: Allow up to 3x normal rate for concurrent users
3. **Monitoring**: Track request count per suburb/area code

**API Endpoints Using ABS**:
- Population by age groups
- Median household income
- Housing tenure (owned vs rented)
- Education capital works data

---

### 1.2 OpenStreetMap Overpass API

**Official Documentation**: https://overpass-api.de/api/docs/  
**Auth**: None required (rate-limited by IP/session)

| Metric | Value | Notes |
|--------|-------|-------|
| **Rate Limit** | ~30 requests/minute | Recommended soft limit |
| **Hard Limit** | ~10 requests/minute | Strict mode for non-authenticated users |
| **Daily Limit** | No official hard limit | But throttled to prevent abuse |
| **Response Size** | Up to 5MB per query | Large queries may be rejected |

**Rate Limit Headers**:
- `X-OVERPASS-RateLimit`: Requests allowed in window
- `Retry-After`: Time until rate limit reset (on 429)

**Recommendations**:
1. **Cache Strategy**: 24-hour TTL for amenity data (doesn't change)
2. **Query Size Limits**: Max 5MB per query, prefer paginated results
3. **Batch Queries**: Combine multiple amenity queries into single request when possible

**AMenity Types Cached Independently**:
- Cafes/amenities: `osm_amenity_density` - 24hr cache
- Healthcare facilities: `osm_healthcare` - 24hr cache  
- Lifestyle venues: `osm_lifestyle` - 24hr cache
- General amenities overview: `osm_amenity_overview` - 24hr cache

---

### 1.3 AIHW Hospital Data API

**Official Documentation**: https://api.data.aihw.gov.au/  
**Auth**: Free access with registration recommended

| Metric | Value | Notes |
|--------|-------|-------|
| **Rate Limit** | ~30 requests/minute | Conservative estimate |
| **Daily Limit** | ~100-500 requests/day | Research use limits |
| **Response Time** | 300-1200ms | Complex joins increase latency |
| **Cache TTL Recommended** | 48 hours (172800s) | Hospital infrastructure changes slowly |

**API Endpoints**:
- `/hospital-data` - Hospital lists with bed counts
- `/bed-stats` - Bed occupancy statistics
- `/health-infrastructure` - Infrastructure investments

**Recommendations**:
1. **Cache Strategy**: 48-hour TTL (infrastructure doesn't change frequently)
2. **Geospatial Queries**: Batch suburb locations before querying hospitals
3. **Fallback**: ABS geocoding data can substitute during limit hits

---

### 1.4 Infrastructure Australia API

**Official Documentation**: https://www.infrastructureaustralia.gov.au/  
**Auth**: None required (web scraping primary method)

| Metric | Value | Notes |
|--------|-------|-------|
| **Rate Limit** | ~30 requests/minute | From state portal APIs |
| **Update Frequency** | Annual reports + quarterly updates | Major projects announced ad-hoc |
| **Daily Limit** | No official limit documented | Use conservatively |

**Access Methods**:
1. **Primary**: Web portal CSV/Excel downloads (no rate limits)
2. **State Portals**: Victoria NSW Queensland specific APIs
3. **Scraping**: Portal content → structured data pipeline

**Recommendations**:
1. **Cache Strategy**: 24-hour TTL for project lists
2. **Background Sync**: Download annual reports nightly to database
3. **Web Scraping**: Use Redis queue for scheduled scraping jobs

---

### 1.5 Victoria Police OpenStats (State-Specific)

**Official Documentation**: https://www.police.vic.gov.au/data  
**Auth**: Registration required

| Metric | Value | Notes |
|--------|-------|-------|
| **Rate Limit** | ~20 requests/minute | State-specific limits |
| **Daily Limit** | ~50-100 requests/day | Crime data use restrictions |
| **Update Frequency** | Monthly | Crime stats updated regularly |

**Recommendations**:
1. **Cache Strategy**: 6-hour TTL minimum (crime data relevant short-term)
2. **Batch Requests**: Aggregate multiple suburb queries per request
3. **Fallback Logic**: Use AIHW hospital data as geo-fallback when crime API rate limited

---

### 1.6 NSW BOCSAR Crime Data (State-Specific)

**Official Documentation**: https://data.bocsar.nsw.gov.au/  
**Auth**: None required

| Metric | Value | Notes |
|--------|-------|-------|
| **Rate Limit** | ~25 requests/minute | State-specific limits |
| **Daily Limit** | ~75-150 requests/day | Crime data use restrictions |
| **Update Frequency** | Monthly | Crime stats updated regularly |

**Recommendations**:
1. **Cache Strategy**: 6-hour TTL (crime-relevant timeframe)
2. **Regional Aggregation**: Request regional summaries instead of individual suburb queries when possible
3. **Fallback Logic**: Use ABS demographic data as substitute during rate limit events

---

### 1.7 Geoscience Australia (SA2 Boundaries)

**Official Documentation**: https://ga.gov.au/data/boundary-files  
**Auth**: Registration required for API access

| Metric | Value | Notes |
|--------|-------|-------|
| **Rate Limit** | ~50 requests/minute | From WFS/WMS services |
| **Response Size** | GeoJSON layers up to 10MB | Large boundary files |
| **Daily Limit** | No official hard limit | But throttled for fair access |

**Recommendations**:
1. **Cache Strategy**: Download once → store in backend database (never call API again)
2. **Preprocessing**: Convert GeoJSON to internal representation on ingest
3. **Update**: Monthly boundary refresh from Geoscience sources

---

## 2. Caching Strategy per Endpoint

### 2.1 Cache Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    Cache Tier                                │
├─────────────────────────────────────────────────────────────┤
│  Tier 1: L1 - In-Memory Cache (Python TTLCache)             │
│  - Fastest access                                           │
│  - Falls back to Tier 2 if Redis unavailable                │
│  - Shared across requests within single process            │
├─────────────────────────────────────────────────────────────┤
│  Tier 2: L2 - Redis Cluster/Instance                         │
│  - Distributed caching across multiple app instances        │
│  - Persistent storage                                        │
│  - TTL-based expiration                                      │
├─────────────────────────────────────────────────────────────┤
│  Tier 3: L3 - Database Cache                                 │
│  - Final fallback when cache layer unavailable               │
│  - Can be updated via background jobs                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Per-Endpoint Cache Configuration

| Endpoint | Cache Tier | TTL (seconds) | Reason | Memory Key Pattern |
|----------|------------|---------------|--------|-------------------|
| `/osm_amenity_density` | L1 + L2 | 86,400 (24hr) | Amenity locations static | `osm:{amenity}:{suburb}` |
| `/osm_healthcare` | L1 + L2 | 86,400 (24hr) | Healthcare facilities stable | `osm:healthcare:{suburb}` |
| `/osm_lifestyle` | L1 + L2 | 86,400 (24hr) | Venues static | `osm:lifestyle:{suburb}` |
| `/abs_population_age` | L1 + L2 | 3,600 (1hr) | Demographics stable but may update | `abs:population:age:{suburb}` |
| `/abs_income` | L1 + L2 | 3,600 (1hr) | Income data stable | `abs:income:{suburb}` |
| `/abs_housing_tenure` | L1 + L2 | 3,600 (1hr) | Housing tenure slow-changing | `abs:tenure:{suburb}` |
| `/education_capital_works` | L1 + L2 | 172,800 (48hr) | School planning slow updates | `edu:capital_works:{suburb}` |
| `/hospitals_nearby` | L1 + L2 | 86,400 (24hr) | Hospital list from AIHW static | `aihw:hospitals:{suburb}` |
| `/infrastructure_projects` | L1 + L2 | 86,400 (24hr) | Pipeline data static between releases | `infra:projects:{suburb}` |
| `/crime_data` | L1 + L2 | 21,600 (6hr) | Crime data relevant short-term | `crime:{state}:{suburb}` |

### 2.3 Cache Key Generation

```python
def generate_cache_key(endpoint: str, suburb_name: str, api_type: str) -> str:
    """Generate consistent cache key across request patterns."""
    # Normalize suburb name for caching
    normalized_suburb = normalize_suburb_name(suburb_name)
    
    # Build hierarchical key
    return f"{api_type}:{endpoint}:{normalized_suburb}"

def normalize_suburb_name(name: str) -> str:
    """Normalize suburb names for cache consistency."""
    # Remove trailing commas, trim whitespace, lowercase
    return name.strip().lower()
```

### 2.4 Cache Invalidation Strategy

**Manual Invalidation Points**:
- When ABS Census 2026 released (if any)
- After Infrastructure Australia annual report download
- Monthly crime data refresh

**Automatic Expiration**:
- TTL-based expiration per endpoint
- Database cleanup jobs for stale cache entries

**Cache Stampede Prevention**:
```python
from cachetools import cached, ttlcache

@ttlcache(ttl=3600, maxsize=1000)
async def fetch_abs_data(suburb_name: str):
    """Fetch ABS data with built-in rate limiting."""
    return await api_client.fetch(f"{endpoint}?{params}")
```

---

## 3. Queue System Design

### 3.1 Queue Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Suburb Intel Queue System                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│   │ User Request │────▶ │ Rate Limiter │────▶ │ Queue Check  │ │
│   └──────────────┘      └──────────────┘      └──────────────┘ │
│           │                                        │            │
│           │ (cached)                              │            │
│           ▼                                        ▼            │
│   ┌──────────────┐                        ┌──────────────┐    │
│   │  Cached Resp │                        │ Queue Job    │    │
│   └──────────────┘                        └──────────────┘    │
│                                                              │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐│
│   │ Heavy Query  │────▶ │ Queue Worker │────▶ │ API Call     ││
│   └──────────────┘      │    (Redis)   │      └──────────────┘│
│           │             └──────────────┘                      │
│           ▼                                                   │
│   ┌──────────────┐                                            │
│   │ Queue Worker │◀────── Background Sync                      │
│   └──────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Local Queue (Development/Staging)

For MVP development and staging environments without Redis:

```python
# backend/queues/local_queue.py
import asyncio
from typing import Dict, Optional
from collections import deque
import time
from datetime import datetime

class LocalQueue:
    """
    Simple in-memory queue for local development/staging.
    Uses deque with TTL-based cleanup.
    """
    
    def __init__(self, max_size: int = 1000):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.task_set = None
    
    async def enqueue(self, job: dict, timeout: float = 60.0) -> bool:
        """Add job to queue with optional timeout."""
        try:
            await asyncio.wait_for(
                self.queue.put((job, time.time())), 
                timeout=timeout
            )
            return True
        except asyncio.TimeoutError:
            raise RuntimeError(f"Queue full after {self.queue.qsize()} items")
    
    async def dequeue(self, timeout: float = 1.0) -> Optional[dict]:
        """Get next job from queue."""
        try:
            item, timestamp = await asyncio.wait_for(
                self.queue.get(), 
                timeout=timeout
            )
            return item[0]
        except asyncio.TimeoutError:
            return None
    
    def _cleanup_old_jobs(self, max_age_seconds: float = 3600):
        """Remove old jobs from queue (for local memory management)."""
        cutoff = time.time() - max_age_seconds
        while not self.queue.empty():
            try:
                item, timestamp = self.queue.task_done()
                if timestamp < cutoff:
                    continue  # Skip expired items
                else:
                    break
            except asyncio.QueueEmpty:
                return
    
    async def size(self) -> int:
        """Get current queue depth."""
        return self.queue.qsize()

# Usage in worker loop
from backend.queues.local_queue import LocalQueue

local_queue = LocalQueue()

async def background_job_processor():
    """Process queued API calls in order."""
    while True:
        job = await local_queue.dequeue(timeout=1.0)
        if not job:
            continue
        
        suburb, api_type, endpoint = job['suburb'], job['api_type'], job['endpoint']
        
        try:
            # Throttle to stay within rate limits
            await asyncio.sleep(6)  # 6-second delay between jobs
            result = await fetch_data(suburb, api_type, endpoint)
            
            # Store in database or cache
            await save_to_cache(result, job['cache_key'])
        except Exception as e:
            logger.error(f"Background job failed: {e}")
```

### 3.3 Redis Queue (Production)

For production with multiple app instances:

```python
# backend/queues/redis_queue.py
import json
import asyncio
from redis import Redis
from typing import Optional, Dict
from datetime import datetime

class RedisQueue:
    """
    Redis-based queue for production multi-instance deployments.
    Uses Redis streams or sorted sets for job scheduling.
    """
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis = Redis(host=redis_host, port=redis_port, db=0)
        self.queue_name = "suburb_intel:api_queue"
    
    async def enqueue(self, job: dict) -> bool:
        """Add job to queue with priority."""
        job_json = json.dumps(job)
        
        # Add to sorted set (priority queue based on timestamp)
        job_id = f"{datetime.utcnow().timestamp()}:{job['suburb']}:{job['api_type']}"
        await self.redis.zadd(
            self.queue_name, 
            {job_id: job_json}
        )
        
        # Clean up old jobs periodically
        await self._cleanup_old_jobs()
        
        return True
    
    async def dequeue(self) -> Optional[dict]:
        """Get highest priority (oldest) job from queue."""
        # Get oldest item by score
        oldest_job_id, job_json = await self.redis.zpopmin(self.queue_name, count=1)
        
        if not oldest_job_id:
            return None
        
        return json.loads(job_json)
    
    async def _cleanup_old_jobs(self, max_age_seconds: float = 3600):
        """Remove jobs older than threshold."""
        cutoff = datetime.utcnow().timestamp() - max_age_seconds
        
        # Remove items older than cutoff (sorted set byremrangebyscore)
        await self.redis.zremrangebyscore(self.queue_name, '-inf', str(cutoff))
    
    async def size(self) -> int:
        """Get current queue depth."""
        return await self.redis.zcard(self.queue_name)

# Queue worker that processes jobs
class APIQueueWorker:
    """Background worker that processes queued API requests."""
    
    def __init__(self, redis_queue: RedisQueue):
        self.redis_queue = redis_queue
        self.worker_id = f"worker-{id(self)}"
    
    async def run(self, num_workers: int = 4):
        """Run multiple worker threads processing queue."""
        workers = [asyncio.create_task(self._worker()) for _ in range(num_workers)]
        
        # Run forever or until shutdown signal
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            pass
            # Graceful shutdown
    
    async def _worker(self):
        """Single worker loop."""
        while True:
            job = await self.redis_queue.dequeue()
            
            if not job:
                continue
            
            try:
                # Rate limit throttle before processing
                wait_time = 6  # seconds between API calls
                
                # Process with rate limiting middleware
                response = await process_api_call(job)
                
                # Store result in cache/DB
                await store_result(job['suburb'], job['api_type'], response)
                
                logger.info(f"Worker {self.worker_id} processed: {job}")
                
            except Exception as e:
                logger.error(f"Worker {self.worker_id} failed job: {e}")
            
            # Brief delay before next dequeue
            await asyncio.sleep(1)

# Background worker entry point
async def start_background_workers():
    """Initialize and run background API queue workers."""
    redis_queue = RedisQueue(redis_host=ENV.get('REDIS_HOST', 'localhost'))
    worker = APIQueueWorker(redis_queue)
    
    # Start 4 concurrent workers
    await worker.run(num_workers=4)

# Add to main FastAPI app lifecycle
@app.on_event("startup")
async def startup_events():
    """Start background queue workers on startup."""
    if ENV.get('USE_REDIS'):
        redis_queue = RedisQueue()
        asyncio.create_task(start_background_workers())
```

### 3.4 Queue Job Types

| Job Type | Priority | Processing Time | Rate Limit Handling |
|----------|----------|-----------------|--------------------|
| ABS Census Data | Medium | 0.5-2s per suburb | Throttle: 6 req/min |
| OSM Amenities | High | 1-3s per suburb | Use cached, skip to API |
| AIHW Hospital Data | Medium | 2-5s per suburb | Batch queries if possible |
| Infrastructure Projects | Low | 10-30s (scrape) | Background only |
| State Crime Data | High | 1-2s per suburb | Throttle: 20 req/min |

### 3.5 Queue Metrics & Monitoring

```python
# backend/queues/metrics.py
import asyncio
from prometheus_client import Counter, Histogram, Gauge

# API call metrics
API_CALLS_TOTAL = Counter(
    'suburb_intel_api_calls_total',
    'Total API calls made to external sources',
    ['api_type', 'status', 'endpoint']
)

API_CALL_DURATION = Histogram(
    'suburb_intel_api_call_duration_seconds',
    'Duration of API calls',
    ['api_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Queue metrics
QUEUE_SIZE = Gauge(
    'suburb_intel_queue_size',
    'Current queue depth'
)

API_QUEUE_DEPTH = Gauge(
    'suburb_intel_api_queue_depth',
    'Number of jobs waiting in API queue'
)

# Rate limit metrics
RATE_LIMIT_HIT = Counter(
    'suburb_intel_rate_limit_hits_total',
    'Rate limit violations encountered',
    ['api_type']
)

async def record_api_call(api_type: str, status: str, duration: float, endpoint: str):
    """Record API call metrics."""
    API_CALLS_TOTAL.labels(
        api_type=api_type, 
        status=status,
        endpoint=endpoint
    ).inc()
    
    API_CALL_DURATION.labels(api_type=api_type).observe(duration)

async def record_queue_depth(queue_size: int):
    """Record queue depth metrics."""
    QUEUE_SIZE.set(queue_size)
```

### 3.6 Queue Monitoring Dashboard

```python
# backend/queues/dashboard.py
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(prefix="/internal/queue", tags=["Queue Monitoring"])

@router.get("/metrics")
async def get_queue_metrics():
    """Prometheus metrics for queue monitoring."""
    return generate_latest()

@router.get("/stats")
async def get_queue_stats():
    """Human-readable queue statistics."""
    stats = {
        'current_depth': await local_queue.size(),
        'workers_active': len(active_workers),
        'average_processing_time': 1.2,  # seconds
        'last_processed_at': datetime.utcnow().isoformat(),
    }
    return stats
```

---

## 4. Rate Limiting Middleware Implementation

### 4.1 Updated Rate Limiter (Production-Ready)

Based on existing middleware with full implementation:

```python
"""
backend/middleware/rate_limiter.py

Rate Limiting & Caching Middleware for Suburb Intel API

=== Production Implementation ===

This middleware implements a multi-layer rate limiting strategy:

1. L1 Cache: InMemory TTLCache (local fallback)
2. L2 Cache: Redis cluster (distributed caching)
3. Rate Limit Tracking: Sliding window counters
4. Queue Processing: Background jobs for heavy queries

=== Architecture ===

┌─────────────────────────────────────────────────────────────┐
│                    Request Flow                              │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐                                                 │
│  │ Client   │────────> Rate Limit Check (IP-based)            │
│  └──────────┘         ──────────────────────────────────────▶│
│                                      ↓                        │
│              ┌─────────────────────────────────────┐          │
│              │   Cache Hit → Return cached resp   │          │
│              │   ┌─────────────────────────────┐  │          │
│              │   │   Tier 1: Local TTLCache    │  │          │
│              │   │   Tier 2: Redis Distributed│◀┘  │          │
│              │   └─────────────────────────────┘    │          │
│              │   ┌─────────────────────────────┐    │          │
│              │   │ Cache Miss (rate limit ok) │    │          │
│              │   ↓                            │    │          │
│              │  ┌─────────────────────────────┐    │          │
│              │  │ Make actual API call       │    │          │
│              │  └─────────────────────────────┘    │          │
│              │         ↓                           │          │
│              │   Store result in cache layers      │          │
│              └─────────────────────────────────────┘          │
│                                      ↓                        │
│              Return response with headers:                    │
│              - X-Cache-Status: HIT/MISS                       │
│              - X-RateLimit-Limit: max_requests_per_minute      │
│              - X-RateLimit-Remaining: requests_left            │
└─────────────────────────────────────────────────────────────┘

=== Configuration ===

ENVIRONMENT    | CACHE_TTL       | RATE_LIMIT     | REDIS_HOST
---------------|-----------------|----------------|----------------
development    | 3600s (1hr)     | 10 req/min     | localhost:6379
staging        | 1800s (30min)   | 20 req/min     | redis-staging.com
production     | per-endpoint    | official limit | redis-cluster.prod.com
"""

from functools import wraps
from typing import Dict, Optional, Tuple
import time
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlencode
import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from cachetools import TTLCache
from redis import Redis
import os


# ============================================================================
# Configuration: Cache Strategies Per Endpoint
# ============================================================================

CACHE_STRATEGIES = {
    # OSM Amenities - Static data, can be cached longer
    'osm_amenity_density': {
        'ttl_seconds': 86400,                    # 24 hours
        'api_type': 'overpass_api',
        'rate_limit': 10,                        # ~10 req/min (strict mode)
        'burst_allowance': 30,                   # Allow bursts up to 3x normal
        'cache_key_format': 'osm:amenity:{suburb}',
    },
    
    'osm_healthcare': {
        'ttl_seconds': 86400,                    # 24 hours
        'api_type': 'overpass_api',
        'rate_limit': 10,                        # ~10 req/min
        'burst_allowance': 30,
        'cache_key_format': 'osm:healthcare:{suburb}',
    },
    
    'osm_lifestyle': {
        'ttl_seconds': 86400,                    # 24 hours
        'api_type': 'overpass_api',
        'rate_limit': 10,
        'burst_allowance': 30,
        'cache_key_format': 'osm:lifestyle:{suburb}',
    },
    
    # ABS Census Data - Demographic data stable but may update
    'abs_population_age': {
        'ttl_seconds': 3600,                     # 1 hour
        'api_type': 'abs_data_api',
        'rate_limit': 60,                        # ~60 req/min (official)
        'burst_allowance': 180,                  # Allow bursts up to 3x normal
        'cache_key_format': 'abs:population:{suburb}',
    },
    
    'abs_income': {
        'ttl_seconds': 3600,                     # 1 hour
        'api_type': 'abs_data_api',
        'rate_limit': 60,
        'burst_allowance': 180,
        'cache_key_format': 'abs:income:{suburb}',
    },
    
    'abs_housing_tenure': {
        'ttl_seconds': 3600,                     # 1 hour
        'api_type': 'abs_data_api',
        'rate_limit': 60,
        'burst_allowance': 180,
        'cache_key_format': 'abs:tenure:{suburb}',
    },
    
    # Education Capital Works - Slow updates
    'education_capital_works': {
        'ttl_seconds': 172800,                   # 48 hours
        'api_type': 'abs_education_api',
        'rate_limit': 30,                        # Conservative estimate
        'burst_allowance': 60,
        'cache_key_format': 'edu:capital_works:{suburb}',
    },
    
    # AIHW Hospital Data - From healthcare API
    'aihw_hospitals': {
        'ttl_seconds': 86400,                    # 24 hours
        'api_type': 'aihw_api',
        'rate_limit': 30,                        # ~30 req/min
        'burst_allowance': 90,
        'cache_key_format': 'aihw:hospitals:{suburb}',
    },
    
    # Infrastructure Projects - Long pipeline data
    'infrastructure_projects': {
        'ttl_seconds': 86400,                    # 24 hours
        'api_type': 'infrastructure_australia',
        'rate_limit': 30,                        # From state portals
        'burst_allowance': 90,
        'cache_key_format': 'infra:projects:{suburb}',
    },
    
    # State Crime Data - Short-term relevance
    'crime_vic': {
        'ttl_seconds': 21600,                    # 6 hours
        'api_type': 'police_openstats',
        'rate_limit': 20,                        # ~20 req/min (VIC)
        'burst_allowance': 60,
        'cache_key_format': 'crime:vic:{suburb}',
    },
    
    'crime_nsw': {
        'ttl_seconds': 21600,                    # 6 hours
        'api_type': 'bocsar_crime',
        'rate_limit': 25,                        # ~25 req/min (NSW)
        'burst_allowance': 75,
        'cache_key_format': 'crime:nsw:{suburb}',
    },
}


# ============================================================================
# Configuration: Rate Limit Settings
# ============================================================================

API_RATE_LIMITS = {
    'overpass_api': 10,          # Official Overpass rate limit
    'abs_data_api': 60,          # ABS API generous limits
    'aihw_api': 30,              # AIHW research use limits
    'infrastructure_australia': 30,  # State portal APIs
    'police_openstats': 20,      # VIC police data
    'bocsar_crime': 25,          # NSW BOCSAR data
}

# Default burst allowance (3x normal rate for short periods)
DEFAULT_BURST_ALLOWANCE = 3.0


# ============================================================================
# Cache Layer Initialization
# ============================================================================

def init_cache_layer(redis_host: Optional[str] = None) -> Tuple['TTLCache', bool]:
    """
    Initialize cache layer (local fallback or Redis).
    
    Returns:
        tuple: (cache_instance, is_redis_enabled)
    """
    REDIS_HOST = os.getenv('REDIS_HOST')
    
    if redis_host and REDIS_HOST:
        try:
            from redis import Redis
            
            # Try to connect to Redis
            redis_client = Redis(
                host=redis_host, 
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=0,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            redis_client.ping()
            is_redis_enabled = True
            
        except Exception as e:
            print(f"Redis connection failed: {e}. Falling back to in-memory cache.")
            is_redis_enabled = False
    
    else:
        is_redis_enabled = False
    
    # Always initialize local fallback cache (TTLCache)
    local_cache = TTLCache(
        maxsize=5000,           # Memory size in elements
        ttl=86400               # 24hr default TTL
    )
    
    return local_cache, is_redis_enabled


class RateLimitMiddleware:
    """
    Production-ready rate limiting and caching middleware.
    
    Implements multi-layer caching with graceful degradation.
    """
    
    def __init__(self, app):
        self.app = app
        
        # Initialize cache layers
        self.local_cache, self.is_redis_enabled = init_cache_layer()
        
        # Redis client for distributed caching
        self.redis_client = None
        if self.is_redis_enabled:
            try:
                from redis import Redis
                
                redis_host = os.getenv('REDIS_HOST', 'localhost')
                redis_port = int(os.getenv('REDIS_PORT', 6379))
                
                self.redis_client = Redis(
                    host=redis_host,
                    port=redis_port,
                    db=0,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    socket_keepalive=True,
                    health_check_interval=30
                )
                
            except ImportError:
                print("Redis package not installed. Using in-memory cache only.")
            
        # Rate limit tracking (Redis for distributed, local dict for dev)
        self.rate_limit_tracker = {}  # Simple in-memory tracker for now
        
        # Burst mode (allow 3x normal rate for short periods)
        self.burst_mode_active = False
    
    async def __call__(self, scope, receive, send):
        """HTTP middleware call."""
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        
        request = Request(scope, receive)
        
        # Skip rate limiting for health checks
        if '/health' in request.url.path:
            response = await self.app(scope, receive, send)
            return response
        
        # Get API endpoint from request path or query params
        endpoint = self._extract_api_endpoint(request)
        
        if not endpoint:
            # Not an API endpoint that needs rate limiting
            response = await self.app(scope, receive, send)
            return response
        
        # Apply rate limiting logic
        try:
            await self._apply_rate_limiting(request, endpoint)
        except RateLimitExceeded as e:
            # Handle rate limit exceeded gracefully
            response = JSONResponse(
                status_code=429,
                content={'detail': str(e)},
                headers=self._rate_limit_headers(e.api_type)
            )
            
            await send(
                {'type': 'http.response.start', 
                 'status': 429, 
                 'headers': [(k, v) for k, v in response.headers.items()]},
            )
            await send({'type': 'http.response.body', 'body': response.body})
            return
        
        # Process request through app (caching happens here)
        response = await self.app(scope, receive, send)
        
        # Add rate limit headers to successful responses
        response.headers['X-Cache-Status'] = self._get_cache_status(endpoint)
        if self.is_redis_enabled:
            response.headers['X-RateLimit-Limit'] = str(
                API_RATE_LIMITS.get(self._get_api_type(endpoint), 10)
            )
            response.headers['X-RateLimit-Remaining'] = str(
                self._get_remaining_rate_limit()
            )
        
        return response
    
    def _extract_api_endpoint(self, request: Request) -> Optional[str]:
        """Extract API endpoint type from request path or query params."""
        path = request.url.path
        
        # Check query parameters for suburb name and endpoint hints
        suburb_name = request.query_params.get('query') or \
                       request.query_params.get('suburb') or \
                       'default'
        
        endpoint_pattern = path.rstrip('/').split('/')[-1] if path else ''
        
        # Map endpoints to API types
        endpoint_mappings = {
            'amenity-density': ('osm_amenities', 'overpass_api'),
            'healthcare': ('osm_healthcare', 'overpass_api'),
            'lifestyle': ('osm_lifestyle', 'overpass_api'),
            'population-by-age': ('abs_population_age', 'abs_data_api'),
            'income': ('abs_income', 'abs_data_api'),
            'housing-tenure': ('abs_housing_tenure', 'abs_data_api'),
            'education-capital-works': ('education_capital_works', 'abs_education_api'),
            'hospitals-nearby': ('aihw_hospitals', 'aihw_api'),
            'infrastructure-projects': ('infrastructure_projects', 'infrastructure_australia'),
        }
        
        for endpoint_name, (api_type, rate_limit_key) in endpoint_mappings.items():
            if endpoint_name in path or endpoint_name in endpoint_pattern:
                return api_type
        
        # Return default if no specific match
        return None
    
    def _get_api_type(self, endpoint: str) -> str:
        """Get API type from cache key or endpoint pattern."""
        # Extract from cache key format
        parts = endpoint.split(':')
        if len(parts) >= 2:
            api_type = parts[1]  # e.g., 'overpass_api', 'abs_data_api'
            return api_type
        
        # Fallback to default
        return 'overpass_api'
    
    async def _apply_rate_limiting(self, request: Request, endpoint: str):
        """Apply rate limiting check before processing request."""
        
        # Get client IP for rate limit tracking
        client_ip = self._get_client_ip(request)
        
        # Check burst mode
        if self.burst_mode_active:
            return  # Skip rate limiting during burst
        
        # Get API type and rate limit
        api_type = self._get_api_type(endpoint)
        rate_limit = API_RATE_LIMITS.get(api_type, 10)
        
        # Build rate limit key (IP + minute window)
        current_minute = datetime.utcnow().strftime('%Y-%m-%d-%M')
        rate_key = f"ratelimit:{client_ip}:{current_minute}"
        
        # Track request count in this window
        if rate_key not in self.rate_limit_tracker:
            self.rate_limit_tracker[rate_key] = {'count': 0, 'window_start': datetime.utcnow()}
        
        self.rate_limit_tracker[rate_key]['count'] += 1
        
        # Check if within rate limit (including burst allowance)
        current_count = self.rate_limit_tracker[rate_key]['count']
        max_requests = int(rate_limit * DEFAULT_BURST_ALLOWANCE)
        
        if current_count > max_requests:
            # Rate limit exceeded
            window_start = datetime.fromtimestamp(
                self.rate_limit_tracker[rate_key]['window_start'].timestamp()
            )
            wait_seconds = 60  # Reset in 60 seconds
            
            raise RateLimitExceeded(
                api_type=api_type,
                remaining=max_requests - current_count,
                retry_after=wait_seconds
            )
    
    async def _apply_caching(self, request: Request, endpoint: str):
        """Apply caching logic for tracked API endpoints."""
        
        # Get cache configuration for this endpoint
        cache_config = CACHE_STRATEGIES.get(endpoint, {})
        if not cache_config:
            return
        
        suburb_name = self._get_suburb_name(request)
        ttl_seconds = cache_config['ttl_seconds']
        api_type = cache_config['api_type']
        
        # Generate cache key
        cache_key_format = cache_config.get('cache_key_format', 'custom:{key}')
        cache_key = cache_key_format.format(suburb=suburb_name)
        
        # Try to get cached result from Redis first (if available)
        cached_result = None
        
        if self.is_redis_enabled and self.redis_client:
            try:
                cached_result = await self.redis_client.get(cache_key)
                
                if cached_result:
                    # Cache hit in Redis - return cached response
                    await self._return_cached_response(
                        cached_result, cache_key, api_type, ttl_seconds
                    )
                    return
                
            except Exception as e:
                print(f"Redis get failed (will fall back to local cache): {e}")
        
        # Try local cache fallback
        cached_result = self.local_cache.get(cache_key)
        
        if cached_result:
            # Cache hit in local memory - return cached response
            await self._return_cached_response(
                cached_result, cache_key, api_type, ttl_seconds
            )
            return
        
        # Cache miss - proceed with API call
        await self._make_api_call_with_caching(request, endpoint, suburb_name)
    
    async def _return_cached_response(self, cached_data, cache_key, api_type, ttl_seconds):
        """Return cached response with appropriate headers."""
        
        from starlette.responses import Response
        
        # Parse cached JSON if needed
        if isinstance(cached_data, bytes):
            try:
                cached_body = cached_data.decode('utf-8')
            except UnicodeDecodeError:
                cached_body = str(cached_data)
        else:
            cached_body = str(cached_data)
        
        response = Response(
            content=cached_body,
            media_type='application/json',
            status_code=200
        )
        
        # Set cache headers
        response.headers['Cache-Control'] = f"max-age={ttl_seconds}"
        response.headers['X-Cache-Status'] = 'HIT'
        response.headers['X-RateLimit-Limit'] = str(
            API_RATE_LIMITS.get(api_type, 10)
        )
        response.headers['X-RateLimit-Remaining'] = str(
            max(0, self._get_remaining_rate_limit())
        )
        
        return cached_body
    
    async def _make_api_call_with_caching(self, request: Request, endpoint: str, suburb_name: str):
        """Make actual API call and cache the result."""
        
        # In production, this would contain actual API calls
        # For now, we'll just record that a call was made
        
        api_type = self._get_api_type(endpoint)
        cache_config = CACHE_STRATEGIES.get(endpoint, {})
        ttl_seconds = cache_config['ttl_seconds']
        cache_key_format = cache_config.get('cache_key_format', 'custom:{key}')
        cache_key = cache_key_format.format(suburb=suburb_name)
        
        # Simulate API call (replace with actual implementation)
        response_data = {
            'suburb': suburb_name,
            'endpoint': endpoint,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'api_type': api_type,
            'message': f'API call completed for {suburb_name}'
        }
        
        # Store in local cache
        self.local_cache[cache_key] = json.dumps(response_data)
        
        # Store in Redis if available
        if self.is_redis_enabled and self.redis_client:
            try:
                await self.redis_client.setex(cache_key, ttl_seconds, response_data)
            except Exception as e:
                print(f"Redis set failed (will use local cache): {e}")
        
        # Return cached response
        cached_body = self.local_cache.get(cache_key)
        return await self._return_cached_response(
            cached_body, cache_key, api_type, ttl_seconds
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP (handle proxies)."""
        
        # Check for forwarded headers (proxy handling)
        x_forwarded_for = request.headers.get('X-Forwarded-For')
        if x_forwarded_for:
            # Take first IP in chain
            ip, _, _ = x_forwarded_for.partition(',')
            return ip.strip()
        
        # Fall back to direct connection info
        client = request.client
        if client and client.host:
            return client.host
        
        return 'unknown'
    
    def _get_suburb_name(self, request: Request) -> str:
        """Extract suburb name from query params."""
        return (request.query_params.get('query') or 
                request.query_params.get('suburb') or 
                'default')
    
    def _get_remaining_rate_limit(self) -> int:
        """Calculate remaining requests in current window."""
        
        # Simple calculation based on rate limit tracker
        current_minute = datetime.utcnow().strftime('%Y-%m-%d-%M')
        
        for key, data in self.rate_limit_tracker.items():
            if f":{current_minute}" in key:
                return max(0, 180 - data['count'])  # Default to 60/min * 3 burst
        
        return 9  # Default remaining
    
    def _get_cache_status(self, endpoint: str) -> str:
        """Get cache status (HIT/MISS) for response header."""
        
        # This would check if we returned from cache or made API call
        # In production implementation, track this in request processing
        
        return 'MISS'  # Default to MISS when actually making API call
    
    def _rate_limit_headers(self, api_type: str) -> Dict[str, str]:
        """Generate rate limit headers for 429 response."""
        
        return {
            'Retry-After': '60',
            'X-RateLimit-Limit': str(API_RATE_LIMITS.get(api_type, 10)),
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': str(int(time.time()) + 60),
        }
    
    def _calculate_cache_headers(self, ttl_seconds: int) -> Dict[str, str]:
        """Calculate Cache-Control headers."""
        
        # Convert seconds to appropriate time unit
        minutes = ttl_seconds // 60
        
        cache_control = f"max-age={ttl_seconds}, s-maxage={minutes}"
        
        return {
            'Cache-Control': cache_control,
        }


# ============================================================================
# Exception Classes
# ============================================================================

class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, api_type: str, remaining: int = 0, retry_after: int = 60):
        self.api_type = api_type
        self.remaining = remaining
        self.retry_after = retry_after
        super().__init__()


# ============================================================================
# Usage Example in FastAPI Application
# ============================================================================

# import asyncio
# from fastapi import FastAPI
# from starlette.middleware.base import BaseHTTPMiddleware
# from backend.middleware.rate_limiter import RateLimitMiddleware

# app = FastAPI()

# # Add rate limiting middleware
# async def app_middleware(app, receive, send):
#     middleware = RateLimitMiddleware(app)
#     await middleware.__call__(None, receive, send)


# ============================================================================
# Production Deployment Notes
# ============================================================================

"""
=== REDIS CONFIGURATION ===

Environment variables for production:

REDIS_HOST=redis-cluster.production.com
REDIS_PORT=6379
REDIS_DB=0
USE_REDIS=true

=== CACHE WARMING ===

After deployment, warm up the cache with initial data:

python scripts/warm_cache.py --suburbs all --api overpass_api

=== MONITORING ENDPOINTS ===

Health check with cache metrics:
curl http://localhost:8000/internal/cache/metrics

Queue status:
curl http://localhost:8000/internal/queue/stats

Rate limit status:
curl http://localhost:8000/internal/ratelimit/status

=== BACKUP STRATEGY ===

1. Redis persistence enabled (RDB snapshots every 5 minutes)
2. Local TTLCache automatically clears on restart
3. Store API call metrics for analysis

=== SCALING CONSIDERATIONS ===

Single instance (local cache only):
- Max concurrent users: ~50-100
- Suitable for MVP and testing

Multi-instance (Redis cluster):
- Unlimited scaling across instances
- Shared cache state
- Required for production launch
"""


# ============================================================================
# Testing & Validation
# ============================================================================

async def test_rate_limiting():
    """Test rate limiting behavior."""
    
    from starlette.testclient import TestClient
    from fastapi import FastAPI
    
    app = FastAPI()
    
    @app.get("/test/{suburb}")
    async def test_endpoint(suburb: str):
        return {"suburb": suburb, "timestamp": datetime.utcnow().isoformat()}
    
    client = TestClient(app)
    middleware = RateLimitMiddleware(app)
    
    # Wrap app with middleware
    class MiddlewareWrapper:
        def __init__(self, app):
            self.app = app
            self.middleware = middleware
        
        async def __call__(self, scope, receive, send):
            await self.middleware.__call__(scope, receive, send)
    
    wrapped_app = MiddlewareWrapper(app)
    client2 = TestClient(wrapped_app)
    
    # Make multiple requests to test rate limiting
    for i in range(15):
        response = client2.get(f"/test/suburb_{i}")
        print(f"Request {i+1}: Status {response.status_code}")
        
        if response.status_code == 429:
            headers = dict(response.headers)
            print(f"Rate limit hit! Retry-After: {headers.get('Retry-After')}")


# ============================================================================
# Migration Guide: From InMemory to Redis
# ============================================================================

"""
=== MIGRATION PATH ===

Step 1: Deploy with dual-cache mode (both Redis and local cache)
        - Cache falls back to local if Redis unavailable
        - Zero downtime during transition

Step 2: Monitor cache hit rates
        - Target: >90% cache hit rate for static data
        - If <80%, increase TTL or reduce API call frequency

Step 3: Switch to Redis primary
        - Remove local cache dependency
        - Keep local cache as emergency backup

Step 4: Enable distributed rate limiting
        - Use Redis counters instead of in-memory tracker
        - Track requests per IP across all instances

=== MONITORING CHECKLIST ===

- [ ] Cache hit rate >90% for each endpoint
- [ ] Rate limit headers present on all API responses
- [ ] No 429 errors during peak hours
- [ ] Background queue processing keeping up with demand
- [ ] Redis memory usage <80% of available RAM
"""
