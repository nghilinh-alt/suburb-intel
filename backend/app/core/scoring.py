"""Core scoring logic - the product moat"""


def normalize(value, min_v, max_v):
    """Normalize a value to 0-100 scale"""
    if max_v == min_v or (max_v - min_v) == 0:
        return 0
    return (value - min_v) / (max_v - min_v) * 100


def calculate_demographic_score(pop_growth, young_population_pct):
    """Demographic momentum score"""
    # Population growth weighted at 50%, young population at 50%
    demographic = (
        pop_growth * 0.5 +
        young_population_pct * 0.5
    )
    return round(demographic, 2)


def calculate_economic_score(income_index, employment_diversity):
    """Economic strength score, clamped to the 0-100 contract.

    Income index weighted at 60%, employment diversity at 40%. The clamp is
    defensive: callers should already cap income_index at 100, but if either
    input slips above 100 we still honour the public score range.
    """
    economic = income_index * 0.6 + employment_diversity * 0.4
    return round(min(max(economic, 0.0), 100.0), 2)


def calculate_housing_pressure_score(renter_pct, household_pressure):
    """Housing pressure score"""
    # Renter percentage weighted at 50%, household pressure at 50%
    housing = (
        renter_pct * 0.5 +
        household_pressure * 0.5
    )
    return round(housing, 2)


def calculate_resilience_score(industry_diversity):
    """Employment resilience score"""
    return float(industry_diversity)


def calculate_gov_investment_score(projects):
    """Government investment uplift score (0-100)"""
    
    type_weights = {
        "transport": 1.0,
        "health": 0.9,
        "education": 0.7,
        "civic": 0.4
    }
    
    stage_weights = {
        "under_construction": 1.0,
        "approved": 0.7,
        "planned": 0.4
    }
    
    total_score = 0
    
    for p in projects:
        project_type = p.get("type", "")
        project_value = p.get("value_aud", 1) or 1
        project_status = p.get("status", "planned")
        
        type_weight = type_weights.get(project_type, 0.5)
        stage_weight = stage_weights.get(project_status, 0.3)
        
        total_score += project_value * type_weight * stage_weight
    
    # Normalize to 0-100 scale (divide by million AUD and cap at 100)
    normalized_score = min(total_score / 1_000_000, 100)
    return round(normalized_score, 2)


def calculate_investment_score(features):
    """
    Main investment score calculator.
    
    Investment Score = 
        25% Demographic Momentum +
        20% Economic Strength +
        20% Housing Pressure +
        15% Employment Resilience +
        20% Government Investment Uplift
    """
    
    demographic = calculate_demographic_score(
        features.get("pop_growth", 0),
        features.get("young_population_pct", 0)
    )

    economic = calculate_economic_score(
        features.get("income_index", 0),
        features.get("employment_diversity", 0)
    )

    housing = calculate_housing_pressure_score(
        features.get("renter_pct", 0),
        features.get("household_pressure", 0)
    )

    resilience = calculate_resilience_score(
        features.get("industry_diversity", 0)
    )

    gov = calculate_gov_investment_score(features.get("projects", []))

    investment_score = (
        demographic * 0.25 +
        economic * 0.20 +
        housing * 0.20 +
        resilience * 0.15 +
        gov * 0.20
    )

    return {
        "investment_score": round(investment_score, 2),
        "demographic_score": demographic,
        "economic_score": economic,
        "housing_pressure_score": housing,
        "resilience_score": resilience,
        "gov_investment_score": gov
    }
