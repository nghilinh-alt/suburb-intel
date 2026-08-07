import asyncio
from app.db.session import get_sync_session, init_db, sync_engine
from sqlalchemy.exc import SQLAlchemyError
import requests
import pandas as pd
from bs4 import BeautifulSoup


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
            "amenity_score": 6.2,
            "building_approvals_1yr": 38,
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
            "amenity_score": 4.8,
            "building_approvals_1yr": 112,
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
            "amenity_score": 7.1,
            "building_approvals_1yr": 65,
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
            "amenity_score": 8.3,
            "building_approvals_1yr": 210,
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
            "amenity_score": 7.9,
            "building_approvals_1yr": 84,
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

    # One SuburbMarketStats row per SA2 (period = 2026-07)
    market_stats_data = [
        {
            "id": "VIC-altona-gardens-vic-2026-07",
            "sa2_code": "30150",
            "suburb_name": "Altona Gardens VIC",
            "state": "VIC",
            "period": "2026-07",
            "median_house_price": 820000,
            "median_unit_price": 510000,
            "median_house_rent_weekly": 520,
            "median_unit_rent_weekly": 390,
            "gross_yield_house_pct": 3.30,
            "gross_yield_unit_pct": 3.98,
            "growth_house_1y_pct": 4.8,
            "growth_house_3y_pct": 12.1,
            "growth_house_5y_pct": 28.4,
            "days_on_market_house": 32,
            "days_on_market_unit": 28,
            "stock_on_market_pct_house": 1.2,
            "stock_on_market_pct_unit": 0.9,
            "inventory_months_house": 1.8,
            "inventory_months_unit": 1.4,
            "heat_score_house": 6.1,
            "heat_score_unit": 5.8,
            "vacancy_rate_pct": 1.4,
            "sales_12mo_house": 148,
        },
        {
            "id": "QLD-ashtabula-qld-2026-07",
            "sa2_code": "34005",
            "suburb_name": "Ashtabula QLD",
            "state": "QLD",
            "period": "2026-07",
            "median_house_price": 490000,
            "median_unit_price": 310000,
            "median_house_rent_weekly": 420,
            "median_unit_rent_weekly": 295,
            "gross_yield_house_pct": 4.46,
            "gross_yield_unit_pct": 4.95,
            "growth_house_1y_pct": 7.2,
            "growth_house_3y_pct": 22.8,
            "growth_house_5y_pct": 41.0,
            "days_on_market_house": 18,
            "days_on_market_unit": 15,
            "stock_on_market_pct_house": 0.7,
            "stock_on_market_pct_unit": 0.5,
            "inventory_months_house": 0.9,
            "inventory_months_unit": 0.7,
            "heat_score_house": 8.4,
            "heat_score_unit": 8.1,
            "vacancy_rate_pct": 0.8,
            "sales_12mo_house": 214,
        },
        {
            "id": "QLD-brisbane-waters-qld-2026-07",
            "sa2_code": "48210",
            "suburb_name": "Brisbane Waters QLD",
            "state": "QLD",
            "period": "2026-07",
            "median_house_price": 740000,
            "median_unit_price": 460000,
            "median_house_rent_weekly": 580,
            "median_unit_rent_weekly": 420,
            "gross_yield_house_pct": 4.07,
            "gross_yield_unit_pct": 4.75,
            "growth_house_1y_pct": 9.1,
            "growth_house_3y_pct": 31.5,
            "growth_house_5y_pct": 55.2,
            "days_on_market_house": 14,
            "days_on_market_unit": 12,
            "stock_on_market_pct_house": 0.5,
            "stock_on_market_pct_unit": 0.4,
            "inventory_months_house": 0.7,
            "inventory_months_unit": 0.5,
            "heat_score_house": 9.2,
            "heat_score_unit": 8.9,
            "vacancy_rate_pct": 0.6,
            "sales_12mo_house": 310,
        },
        {
            "id": "QLD-chermside-qld-2026-07",
            "sa2_code": "47002",
            "suburb_name": "Chermside QLD",
            "state": "QLD",
            "period": "2026-07",
            "median_house_price": 850000,
            "median_unit_price": 540000,
            "median_house_rent_weekly": 640,
            "median_unit_rent_weekly": 470,
            "gross_yield_house_pct": 3.91,
            "gross_yield_unit_pct": 4.52,
            "growth_house_1y_pct": 11.3,
            "growth_house_3y_pct": 38.7,
            "growth_house_5y_pct": 62.4,
            "days_on_market_house": 10,
            "days_on_market_unit": 9,
            "stock_on_market_pct_house": 0.3,
            "stock_on_market_pct_unit": 0.2,
            "inventory_months_house": 0.5,
            "inventory_months_unit": 0.4,
            "heat_score_house": 9.7,
            "heat_score_unit": 9.5,
            "vacancy_rate_pct": 0.4,
            "sales_12mo_house": 520,
        },
        {
            "id": "NSW-cronulla-sydney-nsw-2026-07",
            "sa2_code": "22625",
            "suburb_name": "Cronulla Sydney NSW",
            "state": "NSW",
            "period": "2026-07",
            "median_house_price": 2100000,
            "median_unit_price": 950000,
            "median_house_rent_weekly": 1050,
            "median_unit_rent_weekly": 680,
            "gross_yield_house_pct": 2.60,
            "gross_yield_unit_pct": 3.72,
            "growth_house_1y_pct": 5.6,
            "growth_house_3y_pct": 18.3,
            "growth_house_5y_pct": 34.8,
            "days_on_market_house": 22,
            "days_on_market_unit": 19,
            "stock_on_market_pct_house": 0.9,
            "stock_on_market_pct_unit": 0.7,
            "inventory_months_house": 1.2,
            "inventory_months_unit": 1.0,
            "heat_score_house": 7.3,
            "heat_score_unit": 7.0,
            "vacancy_rate_pct": 1.1,
            "sales_12mo_house": 285,
        },
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

        # Insert market stats
        for ms in market_stats_data:
            stat = models.SuburbMarketStats(**ms)
            session.add(stat)
        
        session.commit()
        
        print("Database seeded successfully!")
        print(f"Inserted {len(sa2_data)} SA2 regions (with amenity_score + building_approvals_1yr)")
        print(f"Inserted {len(census_data)} census records")
        print(f"Inserted {len(infrastructure_data)} infrastructure projects")
        print(f"Inserted {len(link_data)} project links")
        print(f"Inserted {len(market_stats_data)} market stats rows (price, yield, growth, heat, DOM, stock, inventory)")
        
    except SQLAlchemyError as e:
        print(f"Database seeding error: {e}")
        raise


if __name__ == "__main__":
    seed_database_sync()
