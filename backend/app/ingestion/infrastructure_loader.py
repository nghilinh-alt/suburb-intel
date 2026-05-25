"""Infrastructure Australia Data Loader
    
This script loads Infrastructure Australia's project pipeline data
for SA2 regions into the suburb_intel database.
    
Data Source: Infrastructure Australia Pipeline Database
    
Usage:
    python infrastructure_loader.py [--year 2024] [--status all|active|completed]
    
"""

import asyncio
import os


async def fetch_infrastructure_projects(status="all", region_filter=None):
    """Fetch infrastructure projects from Infrastructure Australia
    
    Args:
        status: "all", "active", "planned", "approved", or "under_construction"
        region_filter: Optional lat/lon bounding box for geographic filtering
    
    Returns:
        List of project dictionaries
    """
    
    # Mock data generation for MVP testing
    print("Fetching Infrastructure Australia project pipeline...")
    
    return generate_mock_infrastructure_projects(status, region_filter)


def generate_mock_infrastructure_projects(status="all", region_filter=None):
    """Generate mock infrastructure projects for MVP testing"""
    
    # Realistic project types and values (millions AUD)
    projects = [
        {
            "project_id": "INFRA-001",
            "name": "Brisbane Metro Tunnel Extension",
            "type": "transport",
            "value_aud": 2500000000,
            "status": "under_construction",
            "lat": -27.4700,
            "lon": 153.0300
        },
        {
            "project_id": "INFRA-002",
            "name": "Chermside Hospital Upgrade",
            "type": "health",
            "value_aud": 450000000,
            "status": "approved",
            "lat": -27.4850,
            "lon": 153.0600
        },
        {
            "project_id": "INFRA-003",
            "name": "Gold Coast School Complex",
            "type": "education",
            "value_aud": 120000000,
            "status": "under_construction",
            "lat": -28.0167,
            "lon": 153.4000
        },
        {
            "project_id": "INFRA-004",
            "name": "Sydney West Rail Link",
            "type": "transport",
            "value_aud": 3200000000,
            "status": "planned",
            "lat": -33.9200,
            "lon": 151.1800
        },
        {
            "project_id": "INFRA-005",
            "name": "Melbourne Western Freeway Extension",
            "type": "transport",
            "value_aud": 1800000000,
            "status": "planned",
            "lat": -37.8136,
            "lon": 144.9631
        },
        {
            "project_id": "INFRA-006",
            "name": "Adelaide Medical Research Hub",
            "type": "health",
            "value_aud": 680000000,
            "status": "approved",
            "lat": -34.9285,
            "lon": 138.6007
        },
    ]
    
    # Filter by status if specified
    status_map = {
        "all": lambda p: True,
        "active": lambda p: p["status"] in ("under_construction", "approved"),
        "planned": lambda p: p["status"] == "planned",
        "approved": lambda p: p["status"] == "approved",
        "under_construction": lambda p: p["status"] == "under_construction"
    }
    
    filtered = [p for p in projects if status_map.get(status, lambda _: True)(p)]
    
    # Filter by region (simple lat/lon bounding box)
    if region_filter:
        lat_min, lon_min, lat_max, lon_max = region_filter
        filtered = [
            p for p in filtered
            if lat_min <= p["lat"] <= lat_max and lon_min <= p["lon"] <= lon_max
        ]
    
    print(f"Found {len(filtered)} projects with status filter: {status}")
    
    return filtered


async def load_infrastructure_projects():
    """Main loading function"""
    
    # Fetch data
    projects = await fetch_infrastructure_projects(status="all")
    
    # In production: insert into database
    print("Infrastructure projects loaded. Ready for insertion into DB.")
    
    return projects


async def main():
    """Entry point"""
    
    print("Infrastructure Australia Data Loader")
    print("=" * 40)
    
    projects = await load_infrastructure_projects()
    
    # Print sample projects
    if projects:
        print("\nSample project:")
        import json
        print(json.dumps(projects[0], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
