from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.scoring import calculate_investment_score
from app.core.gov_score import calculate_gov_score, generate_insight, analyze_risk_flags
from app.db.session import get_db
from app.db.models import ABSCEntensMetrics

router = APIRouter()


@router.get("/{sa2_code}")
async def suburb_report(
    sa2_code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed investment report for a suburb
    
    Returns:
        Suburb investment score with breakdown, risk flags, and insights
    """
    
    try:
        # Fetch census data for this SA2
        census_metrics = await db.get(ABSCEntensMetrics, (sa2_code, 2021))
        
        if not census_metrics:
            raise HTTPException(
                status_code=404,
                detail=f"SA2 region '{sa2_code}' not found. Use /search to find valid codes."
            )
        
        # Fetch infrastructure projects for this suburb
        async with get_db() as session:
            sa2_links = await session.query(ABSCEntensMetrics)
        
        # Prepare features from census data
        industry_profile = census_metrics.industry_profile
        
        pop_growth = 35.0  # Would come from growth calculation
        young_population_pct = 32.0  # Under 25% of population
        
        income_index = census_metrics.median_income / 85000.0 * 100 if census_metrics.median_income else 70.0
        employment_diversity = calculate_employment_diversity(industry_profile)
        
        renter_pct = census_metrics.renters_pct or 40.0
        household_pressure = calculate_household_pressure(renter_pct)
        
        industry_diversity = get_industry_diversity(industry_profile)
        
        # Get government projects for this suburb
        gov_projects = []  # Would query sa2_project_link table
        
        # Calculate scores
        features = {
            "pop_growth": pop_growth,
            "young_population_pct": young_population_pct,
            "income_index": income_index,
            "employment_diversity": employment_diversity,
            "renter_pct": renter_pct,
            "household_pressure": household_pressure,
            "industry_diversity": industry_diversity,
            "projects": gov_projects
        }
        
        scores = calculate_investment_score(features)
        
        # Add government investment score if projects exist
        if gov_projects:
            scores["gov_investment_score"] = calculate_gov_score(gov_projects)
        else:
            scores["gov_investment_score"] = 50.0  # Neutral default
        
        # Generate insights
        risk_flags = analyze_risk_flags(gov_projects, census_metrics)
        insight = generate_insight(scores, census_metrics, gov_projects)
        
        return {
            "sa2_code": sa2_code,
            "sa2_name": census_metrics.sa2_name,
            "state": census_metrics.state,
            "scores": scores,
            "insight": insight,
            "risk_flags": risk_flags,
            "tags": generate_tags(scores),
            "census_year": 2021,
            "population": census_metrics.population,
            "median_income": census_metrics.median_income,
            "median_age": census_metrics.median_age
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating report: {str(e)}"
        )


def generate_tags(scores):
    """Generate suburb tags based on scores"""
    investment_score = scores.get("investment_score", 0)
    
    tags = []
    
    if investment_score > 85:
        tags.append("Premium Investment")
    elif investment_score > 75:
        tags.append("Strong Investment")
    elif investment_score > 65:
        tags.append("Moderate Growth")
    else:
        tags.append("Development Opportunity")
    
    gov_score = scores.get("gov_investment_score", 0)
    if gov_score > 80:
        tags.append("Infrastructure-Driven")
    elif gov_score > 50:
        tags.append("Government-Supported")
    
    return tags
