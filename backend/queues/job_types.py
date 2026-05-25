"""
backend/queues/job_types.py

Defines job types for different API processing scenarios.
Provides structured interfaces for job creation and validation.
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime


class JobType(Enum):
    """Types of background jobs that can be queued."""
    
    API_CALL = "api_call"           # Standard API request with rate limiting
    SCRAPER = "scraper"             # Web scraping for non-API data (Infrastructure Australia)
    CACHE_CLEANUP = "cache_cleanup" # Periodic cache maintenance
    DATA_SYNC = "data_sync"         # Bulk data synchronization jobs
    ANALYSIS = "analysis"           # Heavy computation that should be backgrounded
    
    @classmethod
    def from_path(cls, path: str) -> 'JobType':
        """Derive job type from endpoint path."""
        
        path_lower = path.lower()
        
        if 'infrastructure' in path_lower or 'scrape' in path_lower:
            return JobType.SCRAPER
        
        elif 'clean' in path_lower or 'purge' in path_lower:
            return JobType.CACHE_CLEANUP
        
        elif 'sync' in path_lower:
            return JobType.DATA_SYNC
        
        else:
            return JobType.API_CALL


class BackgroundJob:
    """
    Base class for all background jobs.
    
    Provides standard interface and validation for job creation.
    """
    
    def __init__(self, job_type: str, suburb_name: Optional[str],
                 payload: Dict[str, Any], priority: int = 5):
        self.job_id = f"{suburb_name or 'default'}:{job_type}:{datetime.utcnow().strftime('%Y%m%d%H')}"
        self.job_type = job_type
        self.suburb_name = suburb_name
        self.payload = payload
        self.priority = priority  # 1-10, lower number = higher priority
        self.created_at = datetime.utcnow()
        
        # Status tracking
        self.status = "pending"
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate job configuration."""
        
        required_fields = ['suburb_name', 'api_type'] if 'api_type' in self.payload else []
        
        for field in required_fields:
            if not getattr(self, field):
                print(f"Job missing required field: {field}")
                return False
        
        # Check priority range
        if not (1 <= self.priority <= 10):
            print(f"Job priority must be 1-10, got: {self.priority}")
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for storage/transmission."""
        
        return {
            'job_type': self.job_type,
            'suburb_name': self.suburb_name,
            'api_type': self.payload.get('api_type', 'unknown'),
            'endpoint_path': self.payload.get('endpoint_path', ''),
            'payload': self.payload,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'status': self.status,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackgroundJob':
        """Create job from dictionary."""
        
        return cls(
            job_type=data['job_type'],
            suburb_name=data.get('suburb_name'),
            payload=data.get('payload', {}),
            priority=data.get('priority', 5)
        )
    
    @classmethod
    def create_api_call_job(cls, suburb_name: str, api_type: str, 
                           endpoint_path: str) -> 'BackgroundJob':
        """Create a job for API call to external service."""
        
        return cls(
            job_type=JobType.API_CALL.value,
            suburb_name=suburb_name,
            payload={
                'api_type': api_type,
                'endpoint_path': endpoint_path,
                'throttle_seconds': 6,
            },
            priority=2
        )
    
    @classmethod
    def create_scraper_job(cls, url: str, save_path: str) -> 'BackgroundJob':
        """Create a job for web scraping."""
        
        return cls(
            job_type=JobType.SCRAPER.value,
            suburb_name=None,  # Scrapers often target whole site
            payload={
                'url': url,
                'save_path': save_path,
                'max_pages': 100,
            },
            priority=3
        )


# ============================================================================
# Helper Functions for Job Creation
# ============================================================================

def create_osm_amenity_job(suburb_name: str) -> BackgroundJob:
    """Create job for fetching OSM amenities."""
    
    return BackgroundJob(
        job_type='api_call',
        suburb_name=suburb_name,
        payload={
            'api_type': 'overpass_api',
            'endpoint_path': '/osm/amenities',
            'cache_key': f"osm:amenity_density:{suburb_name}",
        },
        priority=2  # High priority - amenity data is frequently requested
    )


def create_abs_population_job(suburb_name: str) -> BackgroundJob:
    """Create job for fetching ABS population data."""
    
    return BackgroundJob(
        job_type='api_call',
        suburb_name=suburb_name,
        payload={
            'api_type': 'abs_data_api',
            'endpoint_path': '/abs/population-by-age',
            'cache_key': f"abs:population:{suburb_name}",
            'ttl_seconds': 3600,
        },
        priority=2
    )


def create_hospital_job(suburb_name: str) -> BackgroundJob:
    """Create job for fetching nearby hospital data."""
    
    return BackgroundJob(
        job_type='api_call',
        suburb_name=suburb_name,
        payload={
            'api_type': 'aihw_api',
            'endpoint_path': '/hospitals-nearby',
            'cache_key': f"aihw:hospitals:{suburb_name}",
            'ttl_seconds': 86400,
        },
        priority=2
    )


def create_infrastructure_job(suburb_name: str) -> BackgroundJob:
    """Create job for scraping infrastructure projects."""
    
    return BackgroundJob(
        job_type='scraper',
        suburb_name=suburb_name,
        payload={
            'api_type': 'infrastructure_australia',
            'endpoint_path': '/infrastructure-projects',
            'cache_key': f"infra:projects:{suburb_name}",
            'ttl_seconds': 86400,
            'throttle_seconds': 15,
        },
        priority=3  # Lower priority - heavy scraping job
    )


# ============================================================================
# Usage Example
# ============================================================================

"""
from backend.queues.job_types import (
    BackgroundJob, 
    create_osm_amenity_job,
    create_abs_population_job,
)

# Create job for OSM amenities
osm_job = create_osm_amenity_job('Carlton')
print(f"Created job: {osm_job.to_dict()}")

# Create job for ABS population data
abs_job = create_abs_population_job('South Yarra')
print(f"ABS Job created: {abs_job.to_dict()}")

# Validate before queuing
if osm_job.validate():
    print("Job is valid, can be queued")
else:
    print("Invalid job, do not queue")

# Output for debugging
import json
print(json.dumps(osm_job.to_dict(), indent=2))
"""


__all__ = ['JobType', 'BackgroundJob']
