from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import SA2Region, SuburbScore
from app.core.scoring import calculate_investment_score

router = APIRouter()


@router.get("/")
async def get_rankings(
    limit: int = Query(25, ge=10, le=200, description="Number of suburbs to rank"),
    score_type: str = Query("investment", description="Score type: investment, population, income"),
    include_details: bool = Query(False, description="Include full suburb details"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get ranked list of suburbs
    
    Args:
        limit: Number of top suburbs to return (10-200)
        score_type: Primary ranking metric
        include_details: Include full suburb information
    
    Returns:
        Ranked suburbs with their scores and details
    """
    
    # For MVP, generate mock rankings
    # In production, query suburb_scores table
    
    import random
    
    sa2_codes = [
        "30150", "34005", "48210", "47002", "22625",
        "21045", "31395", "20605", "31285", "25605",
        "27705", "22305", "38305", "31065", "25765",
        "24910", "37755", "22210", "31050", "20705"
    ]
    
    suburb_names = [
        "Altona Gardens", "Ashtabula", "Brisbane Waters", "Chermside", "Cronulla Sydney",
        "Fairfield", "Greenslopes", "Hurstville", "Kogarah", "Liverpool",
        "Manly", "Parramatta", "Ringwood", "South Melbourne", "Strathfield",
        "Tweed Heads", "Wavell Heights", "Zillmere", "Blacktown", "Campbelltown"
    ]
    
    # Generate rankings data
    rankings = []
    for i in range(limit):
        sa2_code = random.choice(sa2_codes)
        
        # Weighted random scores to create realistic distribution
        base_score = random.gauss(70, 15)
        investment_score = round(min(max(base_score, 45), 98), 1)
        
        demographic_score = round(random.uniform(60, 90), 1)
        economic_score = round(random.uniform(55, 85), 1)
        housing_pressure_score = round(random.uniform(45, 75), 1)
        resilience_score = round(random.uniform(55, 80), 1)
        gov_investment_score = round(random.uniform(30, 95), 1)
        
        # Generate some risk flags occasionally
        risk_flags = None
        if random.random() < 0.3:
            risk_type = random.choice(["retail", "rental", "industry"])
            risk_flags = [f"High {risk_type} concentration"]
        
        # Generate tags based on scores
        tags = []
        if investment_score > 85:
            tags.append("Premium Investment")
        elif investment_score > 70:
            tags.append("Strong Growth")
        else:
            tags.append("Emerging Opportunity")
        
        if gov_investment_score > 80:
            tags.append("Infrastructure-Driven")
        elif gov_investment_score > 50:
            tags.append("Government-Supported")
        
        suburb = {
            "rank": i + 1,
            "sa2_code": sa2_code,
            "investment_score": investment_score,
            "demographic_score": demographic_score,
            "economic_score": economic_score,
            "housing_pressure_score": housing_pressure_score,
            "resilience_score": resilience_score,
            "government_investment_score": gov_investment_score,
            "risk_flags": risk_flags,
            "tags": tags
        }
        
        if include_details:
            suburb["suburb_name"] = random.choice(suburb_names)
            suburb["state"] = random.choice(["NSW", "VIC", "QLD"])
            suburb["population"] = random.randint(8000, 45000)
            suburb["median_income"] = random.randint(75000, 120000)
        
        rankings.append(suburb)
    
    # Reverse to show highest scores first
    rankings.sort(key=lambda x: x["investment_score"], reverse=True)
    
    return {
        "rankings": rankings,
        "total_available": len(sa2_codes),
        "score_type": score_type
    }
