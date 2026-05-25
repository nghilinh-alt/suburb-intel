from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import SA2Region, ABSCEntensMetrics

from app.api.data_sources.osm_overpass import OSMOverpassDataSource

router = APIRouter()


@router.get("/")
async def search_suburbs(
    query: str = Query(..., min_length=3, description="Suburb name or SA2 code to search"),
    state: str = Query(None, description="Filter by state (e.g., NSW, VIC, QLD)"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for suburbs by name or SA2 code
    
    Args:
        query: Suburb name or partial SA2 code
        state: Optional state filter (NSW, VIC, QLD, WA, SA, TAS, ACT, NT)
        limit: Maximum number of results
    
    Returns:
        List of matching suburbs with basic stats
    """
    
    # Check if query looks like an SA2 code (5-6 digits)
    import re
    sa2_pattern = re.compile(r'^\d{5,6}$')
    
    if sa2_pattern.match(query):
        # Exact SA2 code lookup
        return await get_exact_sa2(query, db)
    else:
        # Name-based search
        results = await get_suburbs_by_name(query, state, limit, db)
        
        if not results and len(query) >= 3:
            raise HTTPException(
                status_code=404,
                detail=f"No suburbs found matching '{query}'. Use full name or valid SA2 code."
            )
        
        return results
    
    # ==========================================
    # NEW: Real-Time ABS Data Endpoints (under /search)
    # ==========================================
    
    # Population by age from ABS Census 2021
    @router.get("/{suburb_name}/population-by-age")
    async def get_population_by_age(suburb_name: str):
        """Get population distribution by age group (ABS Census 2021)."""
        # Find SA3 code for this suburb
        results = await get_suburbs_by_name(suburb_name, limit=1)
        if not results:
            raise HTTPException(status_code=404, detail=f"Suburb '{suburb_name}' not found")
        
        sa2_code = results[0].sa2_code
        
        # Call ABS API
        api = AustralianDataSources()
        result = api.get_population_by_age(sa2_code)
        
        if not result["success"]:
            raise HTTPException(status_code=502, detail=f"ABS API error: {result['error']}")
        
        return {"suburb": suburb_name, "data": result["data"]}
    
    # Household income from ABS Census 2021
    @router.get("/{suburb_name}/income")
    async def get_income(suburb_name: str):
        """Get median household income (ABS Census 2021)."""
        results = await get_suburbs_by_name(suburb_name, limit=1)
        if not results:
            raise HTTPException(status_code=404, detail=f"Suburb '{suburb_name}' not found")
        
        sa2_code = results[0].sa2_code
        
        # Call ABS API
        api = AustralianDataSources()
        result = api.get_household_income(sa2_code)
        
        if not result["success"]:
            raise HTTPException(status_code=502, detail=f"ABS API error: {result['error']}")
        
        return {"suburb": suburb_name, "data": result["data"]}
    
    # Housing tenure split (owned vs rented) from ABS Census 2021
    @router.get("/{suburb_name}/housing-tenure")
    async def get_housing_tenure(suburb_name: str):
        """Get housing tenure distribution (ABS Census 2021)."""
        results = await get_suburbs_by_name(suburb_name, limit=1)
        if not results:
            raise HTTPException(status_code=404, detail=f"Suburb '{suburb_name}' not found")
        
        sa2_code = results[0].sa2_code
        
        # Call ABS API
        api = AustralianDataSources()
        result = api.get_housing_tenure(sa2_code)
        
        if not result["success"]:
            raise HTTPException(status_code=502, detail=f"ABS API error: {result['error']}")
        
        return {"suburb": suburb_name, "data": result["data"]}


async def get_exact_sa2(sa2_code: str, db: AsyncSession) -> dict:
    """Get exact match for an SA2 code"""
    region = await db.get(SA2Region, sa2_code)
    
    if not region:
        raise HTTPException(
            status_code=404,
            detail=f"SA2 region '{sa2_code}' not found."
        )
    
    # Get census data
    async with get_db() as session:
        metrics = await session.get(ABSCEntensMetrics, (sa2_code, 2021))
        if not metrics:
            metrics = None
    
    return {
        "sa2_code": region.sa2_code,
        "sa2_name": region.sa2_name,
        "state": region.state,
        "population": metrics.population if metrics else None,
        "median_income": metrics.median_income if metrics else None,
        "median_age": metrics.median_age if metrics else None
    }


async def get_suburbs_by_name(
    query: str,
    state: str = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
) -> list:
    """Search suburbs by partial name"""
    
    # Build SQL query with optional state filter
    conditions = [region.sa2_name.ilike(f"%{query}%")]
    params = {}
    
    if state:
        conditions.append(region.state == state)
        params["state"] = state
    
    sql = """
        SELECT 
            sa2_code,
            sa2_name,
            state,
            population,
            median_income,
            median_age,
            renters_pct,
            owners_pct
        FROM sa2_regions
        WHERE {}
        ORDER BY sa2_name
        LIMIT :limit
    """.format(" AND ".join(conditions))
    
    # Fetch results
    async with get_db() as session:
        result = await session.execute(text(sql), {"limit": limit, "state": state or ""})
        rows = result.fetchall()
        
        return [dict(row._mapping) for row in rows]


@router.get("/top")
async def get_top_suburbs(
    limit: int = Query(20, ge=5, le=100, description="Number of top suburbs to return"),
    by: str = Query("investment", description="Sort by: investment_score, population, median_income"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of top suburbs by score
    
    Args:
        limit: Maximum number of results (5-100)
        by: Sort metric (investment_score, population, median_income)
    
    Returns:
        Top suburbs ranked by selected metric
    """
    
    # For MVP, return mock top suburbs
    # In production, this would query suburb_scores table
    
    import random
    sa2_codes = ["30150", "34005", "48210", "47002", "22625"]
    
    top_suburbs = []
    for code in sa2_codes:
        top_suburbs.append({
            "sa2_code": code,
            "investment_score": round(random.uniform(65, 90), 1),
            "population": random.randint(10000, 30000)
        })
    
    # Sort by selected metric
    if by == "investment_score":
        top_suburbs.sort(key=lambda x: x["investment_score"], reverse=True)
    elif by == "population":
        top_suburbs.sort(key=lambda x: x["population"], reverse=True)
    else:  # median_income or default
        pass
    
    return {
        "count": len(top_suburbs),
        "by": by,
        "suburbs": top_suburbs[:limit]
    }


