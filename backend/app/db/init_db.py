import asyncio
from app.db.session import get_sync_session, init_db, sync_engine
from sqlalchemy.exc import SQLAlchemyError


def seed_database_sync():
    """Seed the database with sample data (SQLite sync mode)"""
    
    sa2_data = [
        {"sa2_code": "30150", "sa2_name": "Altona Gardens VIC", "state": "VIC"},
        {"sa2_code": "34005", "sa2_name": "Ashtabula QLD", "state": "QLD"},
        {"sa2_code": "48210", "sa2_name": "Brisbane Waters QLD", "state": "QLD"},
        {"sa2_code": "47002", "sa2_name": "Chermside QLD", "state": "QLD"},
        {"sa2_code": "22625", "sa2_name": "Cronulla Sydney NSW", "state": "NSW"},
    ]
    
    census_data = [
        {
            "sa2_code": "30150",
            "year": 2021,
            "population": 8450,
            "median_income": 95000,
            "median_age": 34.2,
            "renters_pct": 45.5,
            "owners_pct": 45.5,
            "industry_profile": {"healthcare": 0.15, "retail": 0.22, "finance": 0.18, "tech": 0.10, "education": 0.14}
        },
        {
            "sa2_code": "34005",
            "year": 2021,
            "population": 6230,
            "median_income": 78000,
            "median_age": 29.8,
            "renters_pct": 52.3,
            "owners_pct": 47.7,
            "industry_profile": {"manufacturing": 0.12, "retail": 0.28, "finance": 0.12}
        },
        {
            "sa2_code": "48210",
            "year": 2021,
            "population": 12450,
            "median_income": 87000,
            "median_age": 32.5,
            "renters_pct": 42.1,
            "owners_pct": 57.9,
            "industry_profile": {"tech": 0.25, "healthcare": 0.18, "retail": 0.15, "finance": 0.20}
        },
        {
            "sa2_code": "47002",
            "year": 2021,
            "population": 28900,
            "median_income": 102000,
            "median_age": 31.5,
            "renters_pct": 31.5,
            "owners_pct": 48.9,
            "industry_profile": {"tech": 0.18, "finance": 0.22, "retail": 0.20, "education": 0.16}
        },
        {
            "sa2_code": "22625",
            "year": 2021,
            "population": 18750,
            "median_income": 91000,
            "median_age": 38.9,
            "renters_pct": 38.9,
            "owners_pct": 44.1,
            "industry_profile": {"healthcare": 0.16, "retail": 0.25, "finance": 0.17, "tech": 0.12}
        },
    ]
    
    infrastructure_data = [
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
    ]
    
    link_data = [
        {"sa2_code": "48210", "project_id": "INFRA-001", "impact_score": 85.0},
        {"sa2_code": "47002", "project_id": "INFRA-002", "impact_score": 92.0},
        {"sa2_code": "22625", "project_id": "INFRA-004", "impact_score": 78.0},
    ]
    
    try:
        from app.db import models
        
        session = get_sync_session()
        
        # Insert SA2 regions
        for sa2 in sa2_data:
            region = models.SA2Region(**sa2)
            session.add(region)
        
        # Insert census metrics
        for census in census_data:
            metric = models.ABSCEntensMetrics(**census)
            session.add(metric)
        
        # Insert infrastructure projects
        for infra in infrastructure_data:
            project = models.InfrastructureProject(**infra)
            session.add(project)
        
        # Insert links
        for link in link_data:
            sa2_link = models.SA2ProjectLink(**link)
            session.add(sa2_link)
        
        session.commit()
        
        print("Database seeded successfully!")
        print(f"Inserted {len(sa2_data)} SA2 regions")
        print(f"Inserted {len(census_data)} census records")
        print(f"Inserted {len(infrastructure_data)} infrastructure projects")
        print(f"Inserted {len(link_data)} project links")
        
    except SQLAlchemyError as e:
        print(f"Database seeding encountered an error: {e}")


if __name__ == "__main__":
    seed_database_sync()
