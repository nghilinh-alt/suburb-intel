"""Government Investment Score Module"""


def calculate_gov_score(projects):
    """Calculate government investment score from project pipeline
    
    Args:
        projects: List of infrastructure project dicts with keys:
            - type: one of transport, health, education, civic
            - status: under_construction, approved, planned, cancelled
            - value_aud: project value in AUD
            - lat/lon: geographic coordinates (optional)
    
    Returns:
        Government investment score normalized to 0-100
    
    Weightings:
        Type weights: transport(1.0), health(0.9), education(0.7), civic(0.4)
        Stage weights: under_construction(1.0), approved(0.7), planned(0.4)
    """
    
    type_weights = {
        "transport": 1.0,
        "health": 0.9,
        "education": 0.7,
        "civic": 0.4
    }
    
    stage_weights = {
        "under_construction": 1.0,
        "approved": 0.7,
        "planned": 0.4,
        "completed": 0.2,
        "cancelled": 0.0
    }
    
    score = 0
    
    for p in projects:
        type_weight = type_weights.get(p.get("type", ""), 0.5)
        stage_weight = stage_weights.get(p.get("status", "planned"), 0.3)
        project_value = p.get("value_aud") or 1
        
        score += project_value * type_weight * stage_weight
    
    # Normalize to 0-100 scale (million AUD base)
    normalized_score = min(score / 1_000_000, 100)
    
    return round(normalized_score, 2)


def analyze_risk_flags(projects, census_metrics):
    """Generate risk flag analysis for a suburb"""
    risk_flags = []
    
    # Check for single-industry dependency
    industry_profile = census_metrics.get("industry_profile", {})
    if industry_profile:
        max_industry_share = max(industry_profile.values()) if industry_profile else 0
        if max_industry_share > 0.3:
            dominant_industry = max(industry_profile, key=industry_profile.get)
            risk_flags.append(f"HIGH dependency on {dominant_industry} sector ({max_industry_share*100:.0f}%)")
    
    # Check for high rental pressure
    renter_pct = census_metrics.get("renters_pct", 0)
    if renter_pct > 40:
        risk_flags.append(f"High rental pressure: {renter_pct:.1f}% of residents are renters")
    
    # Check for low owner occupancy
    owners_pct = census_metrics.get("owners_pct", 0)
    if owners_pct < 50:
        risk_flags.append(f"Low homeownership rate: only {owners_pct:.1f}% own their home")
    
    # Check project uncertainty
    uncertain_projects = [p for p in projects if p.get("status") in ("planned", "cancelled")]
    if uncertain_projects:
        risk_flags.append(f"{len(uncertain_projects)} government projects at uncertainty (planned/cancelled)")
    
    return risk_flags


def generate_insight(scores, census_metrics, projects):
    """Generate human-readable insight about the suburb"""
    
    investment_score = scores.get("investment_score", 0)
    gov_score = scores.get("gov_investment_score", 0)
    pop_growth = census_metrics.get("pop_growth", 0)
    young_pct = census_metrics.get("young_population_pct", 0)
    
    insight_parts = []
    
    if investment_score > 80:
        insight_parts.append("Exceptional investment opportunity")
    elif investment_score > 70:
        insight_parts.append("Strong investment profile")
    elif investment_score > 60:
        insight_parts.append("Moderate investment potential")
    else:
        insight_parts.append("Caution recommended - lower scores")
    
    if gov_score > 80:
        insight_parts.append("Major infrastructure tailwind in pipeline")
    elif gov_score > 50:
        insight_parts.append("Supportive government investment trajectory")
    
    if pop_growth > 30 and young_pct > 25:
        insight_parts.append("Demographic momentum accelerating")
    
    industry_profile = census_metrics.get("industry_profile", {})
    if len(industry_profile) < 3 or max(industry_profile.values(), default=0) > 0.35:
        insight_parts.append("Diversification needed across sectors")
    else:
        insight_parts.append("Well-diversified employment base")
    
    return "; ".join(insight_parts) if insight_parts else "Mixed investment characteristics"
