"""Common utility functions"""


def parse_jsonb(data_str):
    """Parse JSONB string to dict, return empty dict on failure"""
    try:
        import json
        if data_str:
            return json.loads(str(data_str))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


def safe_divide(numerator, denominator, default=0.0):
    """Safe division with default value on zero"""
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


def format_currency(amount):
    """Format integer amount as currency string"""
    import locale
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    return f"${locale.format_string('%d', amount)}"


def calculate_population_growth(sa2_code, year):
    """Calculate population growth rate for a suburb"""
    from app.db.session import get_db
    from app.db.models import ABSCEntensMetrics
    
    async with get_db() as session:
        metrics = session.get(ABSCEntensMetrics, (sa2_code, year))
        if metrics:
            current_pop = metrics.population or 0
            prev_year = year - 1
            previous_metrics = session.get(ABSCEntensMetrics, (sa2_code, prev_year))
            
            if previous_metrics and previous_metrics.population:
                prev_pop = previous_metrics.population
                return safe_divide(current_pop - prev_pop, prev_pop) * 100
                
        return 0.0


def get_industry_diversity(industry_profile):
    """Calculate industry diversity score (more sectors = more diverse)"""
    if not industry_profile:
        return 50.0
    
    num_sectors = len(industry_profile)
    
    # Normalize to 0-100 scale (assume max meaningful sectors is ~8)
    normalized_diversity = num_sectors / 8.0 * 100
    
    return round(normalized_diversity, 2)


def calculate_employment_diversity(industry_profile):
    """Calculate employment diversity (inverse concentration risk)"""
    if not industry_profile:
        return 50.0
    
    # Get the most dominant sector's share
    max_share = max(industry_profile.values()) if industry_profile else 0
    
    # Lower concentration = higher diversity
    diversity = (1 - max_share) * 100 + 25  # Minimum 25, maximum ~100
    
    return round(min(diversity, 100), 2)


def calculate_household_pressure(renters_pct):
    """Calculate housing pressure from renter percentage"""
    # Higher renter % = more housing pressure
    return min(renters_pct * 0.85, 100)
