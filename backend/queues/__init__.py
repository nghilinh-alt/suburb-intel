"""
suburb_intel/queues/__init__.py

Queue System Package for Suburb Intel API Rate Limiting

Provides local and Redis-based queues for processing heavy API requests in the background.
"""

from .local_queue import LocalQueue, BackgroundWorker
from .redis_queue import RedisQueue, APIQueueWorker
from .job_types import JobType, BackgroundJob
from .processor import QueueProcessor, process_job

__all__ = [
    'LocalQueue', 
    'BackgroundWorker',
    'RedisQueue', 
    'APIQueueWorker',
    'JobType',
    'BackgroundJob',
    'QueueProcessor',
    'process_job'
]
