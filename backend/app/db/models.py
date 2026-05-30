from sqlalchemy import Column, Text, Integer, Float, DateTime, JSON, ForeignKeyConstraint, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


class SA2Region(Base):
    __tablename__ = "sa2_regions"

    sa2_code = Column(Text, primary_key=True)
    sa2_name = Column(Text, nullable=False)
    state = Column(Text, nullable=False)

    # Hierarchical geography codes (derived from SA2 code prefix during ingestion)
    sa3_code = Column(Text, nullable=True)
    sa3_name = Column(Text, nullable=True)
    sa4_code = Column(Text, nullable=True)
    sa4_name = Column(Text, nullable=True)
    gcc_code = Column(Text, nullable=True)
    gcc_name = Column(Text, nullable=True)
    area_sqkm = Column(Float, nullable=True)
    # Simplified polygon as GeoJSON text.
    # SQLite: stored as TEXT.  PostgreSQL migration: ALTER COLUMN → GEOMETRY(MultiPolygon, 4326) + PostGIS index.
    geometry_geojson = Column(Text, nullable=True, comment="Simplified GeoJSON polygon (WGS84). Migrate to PostGIS GEOMETRY on PostgreSQL.")

    __table_args__ = (Index("ix_sa2_regions_name", "sa2_name"),)


class ABSCEntensMetrics(Base):
    __tablename__ = "abs_census_metrics"

    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False, primary_key=True)
    year = Column(Integer, nullable=False, primary_key=True)

    # ── Demographics (G02, G09, G29, G37) ────────────────────────────────────
    population = Column(Integer, nullable=True, comment="Usual resident population (from G44 Tot_P)")
    median_age = Column(Float, nullable=True)
    median_income = Column(Integer, nullable=True, comment="Median annual personal income (weekly × 52)")
    median_mortgage_monthly = Column(Float, nullable=True)
    median_rent_weekly = Column(Float, nullable=True)
    overseas_born_pct = Column(Float, nullable=True, comment="% of population born overseas (G09)")
    families_with_children_pct = Column(Float, nullable=True, comment="% of families with children under 15 (G29)")
    renters_pct = Column(Float, nullable=True)
    owners_pct = Column(Float, nullable=True)
    social_housing_pct = Column(Float, nullable=True, comment="% of dwellings rented from govt/community housing (G37)")

    # ── Property (G35, G36, G38, G40) ────────────────────────────────────────
    avg_household_size = Column(Float, nullable=True)
    separate_house_pct = Column(Float, nullable=True, comment="% of occupied private dwellings that are separate houses (G36)")
    flat_apartment_pct = Column(Float, nullable=True, comment="% of occupied private dwellings that are flats/apartments (G36)")
    high_mortgage_stress_pct = Column(Float, nullable=True, comment="% of mortgaged dwellings paying ≥$3 000/month (G38)")
    high_rent_stress_pct = Column(Float, nullable=True, comment="% of rented dwellings paying ≥$650/week (G40)")

    # ── Growth / Gentrification (G44, G45, G49, G60) ─────────────────────────
    moved_in_1yr_pct = Column(Float, nullable=True, comment="% who moved from a different SA2 or overseas in the past year (G44)")
    moved_in_5yr_pct = Column(Float, nullable=True, comment="% who moved from a different SA2 or overseas in the past 5 years (G45)")
    uni_degree_pct = Column(Float, nullable=True, comment="% with bachelor degree or higher (G49)")
    professionals_managers_pct = Column(Float, nullable=True, comment="% employed as managers or professionals (G60)")

    # ── Lifestyle (G34, G62) ──────────────────────────────────────────────────
    zero_car_dwellings_pct = Column(Float, nullable=True, comment="% of dwellings with no motor vehicles (G34)")
    pt_commute_pct = Column(Float, nullable=True, comment="% who commute by public transport (single-mode, G62)")
    car_commute_pct = Column(Float, nullable=True, comment="% who commute by car (single-mode, G62)")
    work_from_home_pct = Column(Float, nullable=True, comment="% who work from home (G62)")

    # ── Risk (G37, G41, G46) ─────────────────────────────────────────────────
    one_bedroom_pct = Column(Float, nullable=True, comment="% of dwellings with 1 bedroom (G41)")
    unemployment_pct = Column(Float, nullable=True, comment="Unemployment rate within labour force (G46)")

    # ── SEIFA 2021 ───────────────────────────────────────────────────────────
    seifa_irsd_score  = Column(Float,   nullable=True, comment="IRSD score (~1000 mean; low = more disadvantaged)")
    seifa_irsd_decile = Column(Integer, nullable=True, comment="IRSD decile 1–10 within Australia (1 = most disadvantaged)")
    seifa_irsad_score  = Column(Float,   nullable=True, comment="IRSAD score (advantage AND disadvantage)")
    seifa_irsad_decile = Column(Integer, nullable=True, comment="IRSAD decile 1–10 within Australia")
    seifa_ier_score    = Column(Float,   nullable=True, comment="IER score (economic resources)")
    seifa_ier_decile   = Column(Integer, nullable=True, comment="IER decile 1–10 within Australia")
    seifa_ieo_score    = Column(Float,   nullable=True, comment="IEO score (education and occupation)")
    seifa_ieo_decile   = Column(Integer, nullable=True, comment="IEO decile 1–10 within Australia")

    # ── Schools (ICSEA 2025) ─────────────────────────────────────────────────
    avg_school_icsea = Column(Float, nullable=True, comment="Enrolment-weighted avg ICSEA across schools whose postcode maps to this SA2 (2025 data)")
    num_schools = Column(Integer, nullable=True, comment="Number of schools with a valid ICSEA score in this SA2 (2025 data)")

    # ── Public Transport stops (GTFS) ────────────────────────────────────────
    pt_stop_train = Column(Integer, nullable=True, comment="Count of unique rail/metro stops within SA2 boundary (GTFS route_type 1, 2)")
    pt_stop_tram  = Column(Integer, nullable=True, comment="Count of unique tram/light-rail stops within SA2 boundary (GTFS route_type 0)")
    pt_stop_bus   = Column(Integer, nullable=True, comment="Count of unique bus stops within SA2 boundary (GTFS route_type 3)")
    pt_stop_ferry = Column(Integer, nullable=True, comment="Count of unique ferry stops within SA2 boundary (GTFS route_type 4)")

    # ── Amenity counts (Overture Maps) ──────────────────────────────────────
    osm_cafes        = Column(Integer, nullable=True, comment="Cafes + coffee shops (excludes bakeries)")
    osm_bakeries     = Column(Integer, nullable=True, comment="Bakeries")
    osm_restaurants  = Column(Integer, nullable=True, comment="Total sit-down restaurants (all cuisines, excludes fast food + cafes)")
    osm_fast_food    = Column(Integer, nullable=True, comment="Fast food restaurants + burger/pizza chains")
    osm_supermarkets = Column(Integer, nullable=True, comment="Supermarkets + grocery stores + convenience stores")
    osm_parks        = Column(Integer, nullable=True, comment="Parks, reserves, playgrounds, beaches")
    osm_gyms         = Column(Integer, nullable=True, comment="Gyms + yoga + pilates + sports centres")
    osm_hospitals    = Column(Integer, nullable=True, comment="Hospitals + clinics + medical centres + GPs")
    osm_pharmacies   = Column(Integer, nullable=True, comment="Pharmacies + drugstores")
    osm_shopping_centres = Column(Integer, nullable=True, comment="Shopping malls + department stores")
    # ── Restaurant cuisine breakdown (subsets of osm_restaurants) ───────────
    osm_rest_chinese       = Column(Integer, nullable=True, comment="Chinese restaurants")
    osm_rest_indian        = Column(Integer, nullable=True, comment="Indian restaurants")
    osm_rest_thai          = Column(Integer, nullable=True, comment="Thai restaurants")
    osm_rest_italian       = Column(Integer, nullable=True, comment="Italian + pizza restaurants")
    osm_rest_japanese      = Column(Integer, nullable=True, comment="Japanese + sushi restaurants")
    osm_rest_vietnamese    = Column(Integer, nullable=True, comment="Vietnamese restaurants")
    osm_rest_korean        = Column(Integer, nullable=True, comment="Korean restaurants")
    osm_rest_greek         = Column(Integer, nullable=True, comment="Greek + Mediterranean restaurants")
    osm_rest_mexican       = Column(Integer, nullable=True, comment="Mexican restaurants")
    osm_rest_middle_eastern = Column(Integer, nullable=True, comment="Middle Eastern restaurants")
    osm_rest_seafood       = Column(Integer, nullable=True, comment="Seafood restaurants")
    amenity_score    = Column(Float,   nullable=True, comment="Weighted liveability score 0–10")

    # ── Property market (Domain API) ─────────────────────────────────────────
    domain_median_house_price = Column(Float,   nullable=True, comment="Median house sold price $ — most recent 12-month period (Domain API)")
    domain_median_unit_price  = Column(Float,   nullable=True, comment="Median unit/apartment sold price $ — most recent 12-month period (Domain API)")
    domain_days_on_market     = Column(Float,   nullable=True, comment="Median days on market for houses (Domain API)")
    domain_clearance_rate     = Column(Float,   nullable=True, comment="Auction clearance rate 0–1 for houses; null if < 10 auctions (Domain API)")

    # ── Building Approvals (ABS, FY2024-25) ──────────────────────────────────
    building_approvals_1yr = Column(Integer, nullable=True, comment="New residential dwellings approved in last full financial year (ABS SA2 building approvals)")

    # ── Population Projections (ABS, base 2022, series B) ────────────────────
    pop_proj_2026 = Column(Integer, nullable=True, comment="ABS projected total population at 30 June 2026 (series B medium)")
    pop_proj_2031 = Column(Integer, nullable=True, comment="ABS projected total population at 30 June 2031 (series B medium)")
    pop_growth_proj_pct = Column(Float, nullable=True, comment="Projected population % change 2023→2031 (ABS series B)")

    # ── Legacy / cross-census fields ─────────────────────────────────────────
    industry_profile = Column(JSON, nullable=True, comment="DEPRECATED – industry bucket proportions (G53 not in scope)")
    pop_growth_5yr = Column(Float, nullable=True, comment="Population growth % between 2016 and 2021 Census")
    young_population_pct = Column(Float, nullable=True, comment="DEPRECATED – % aged 15-34 (G01 not in scope)")


class InfrastructureProject(Base):
    __tablename__ = "infrastructure_projects"

    project_id = Column(Text, primary_key=True)
    name       = Column(Text, nullable=False)
    type       = Column(Text, nullable=False)
    value_aud  = Column(Integer, nullable=True)
    status     = Column(Text, nullable=False)
    lat        = Column(Float, nullable=True)
    lon        = Column(Float, nullable=True)
    # IA-specific fields (added via migration if DB already exists)
    state      = Column(Text, nullable=True, comment="State codes, e.g. 'NSW' or 'VIC, NSW'")
    timing     = Column(Text, nullable=True, comment="IA timing category OR '<start> to <end>' date string")
    source     = Column(Text, nullable=True, comment="Data source label")
    # iPAMS-specific fields (added via migration)
    agc_aud       = Column(Integer, nullable=True, comment="Australian Government Commitment (AUD) from iPAMS")
    sub_program   = Column(Text,    nullable=True, comment="iPAMS sub-program, e.g. 'Black Spot Projects'")
    expected_start = Column(Text,   nullable=True, comment="Expected start date string from iPAMS")
    expected_end   = Column(Text,   nullable=True, comment="Expected end date string from iPAMS")
    project_url    = Column(Text,   nullable=True, comment="URL to project detail page")


class SA2ProjectLink(Base):
    __tablename__ = "sa2_project_link"
    
    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False, primary_key=True)
    project_id = Column(Text, ForeignKey("infrastructure_projects.project_id"), nullable=False, primary_key=True)
    impact_score = Column(Float, nullable=True)


class SuburbScore(Base):
    __tablename__ = "suburb_scores"

    sa2_code = Column(Text, primary_key=True)
    investment_score = Column(Float, nullable=True)
    demographic_score = Column(Float, nullable=True)
    economic_score = Column(Float, nullable=True)
    housing_pressure_score = Column(Float, nullable=True)
    resilience_score = Column(Float, nullable=True)
    gov_investment_score = Column(Float, nullable=True)
    risk_flags = Column(JSON, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_suburb_scores_investment_desc", "investment_score"),)


class School(Base):
    __tablename__ = "schools"

    acara_id    = Column(Text, primary_key=True, comment="ACARA SML ID — unique school identifier")
    name        = Column(Text, nullable=False)
    suburb      = Column(Text, nullable=True)
    state       = Column(Text, nullable=True)
    postcode    = Column(Text, nullable=True)
    sector      = Column(Text, nullable=True, comment="Government | Catholic | Independent")
    school_type = Column(Text, nullable=True, comment="Primary | Secondary | Combined | Special")
    is_special  = Column(Integer, nullable=True, comment="1 if special school, 0 otherwise")
    lat         = Column(Float, nullable=True)
    lon         = Column(Float, nullable=True)
    sa2_code    = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=True, comment="Containing SA2 (from ACARA location data)")
    remoteness  = Column(Text, nullable=True, comment="ABS Remoteness Area Name")
    year_range  = Column(Text, nullable=True, comment="e.g. 'Prep-12'")
    icsea       = Column(Float, nullable=True)
    icsea_percentile = Column(Float, nullable=True)
    total_enrolments = Column(Integer, nullable=True)
    indigenous_pct   = Column(Float, nullable=True, comment="% Indigenous enrolments")
    source_year = Column(Integer, nullable=True, comment="ACARA data year (e.g. 2025)")
    # Provenance
    acara_location_age_id = Column(Text, nullable=True, comment="Location AGE ID from ACARA location file")

    __table_args__ = (
        Index("ix_schools_sa2", "sa2_code"),
        Index("ix_schools_state", "state"),
        Index("ix_schools_sector_type", "sector", "school_type"),
    )


class HealthFacility(Base):
    __tablename__ = "health_facilities"

    facility_id   = Column(Text, primary_key=True, comment="'aihw-<code>' or 'ga-<objectid>'")
    name          = Column(Text, nullable=False)
    facility_type = Column(Text, nullable=True, comment="public_hospital | private_hospital | aged_care | nursing_home | indigenous_health | disability_support")
    lat           = Column(Float, nullable=True)
    lon           = Column(Float, nullable=True)
    state         = Column(Text, nullable=True)
    address       = Column(Text, nullable=True)
    suburb        = Column(Text, nullable=True)
    phn_name      = Column(Text, nullable=True, comment="Primary Health Network name (AIHW)")
    is_operational = Column(Integer, nullable=True, comment="1 = operational, 0 = closed")
    source        = Column(Text, nullable=True, comment="AIHW | GA Foundation Facilities")
    # Provenance
    source_id     = Column(Text, nullable=True, comment="Original ID from source system")

    __table_args__ = (
        Index("ix_health_facilities_type", "facility_type"),
        Index("ix_health_facilities_state", "state"),
    )


class SA2HealthLink(Base):
    __tablename__ = "sa2_health_link"

    sa2_code    = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False, primary_key=True)
    facility_id = Column(Text, ForeignKey("health_facilities.facility_id"), nullable=False, primary_key=True)
    impact_score = Column(Float, nullable=True, comment="1.0 = containing SA2, 0.5 = border-adjacent SA2")


class SA2SchoolLink(Base):
    __tablename__ = "sa2_school_link"

    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False, primary_key=True)
    acara_id = Column(Text, ForeignKey("schools.acara_id"), nullable=False, primary_key=True)
    impact_score = Column(Float, nullable=True, comment="1.0 = containing SA2, 0.5 = border-adjacent SA2")


class AmenityData(Base):
    """Store OpenStreetMap Overpass API amenity counts for suburb intelligence."""
    
    __tablename__ = "osm_amenities"
    
    suburb_id = Column(Text, primary_key=True, comment="Suburb identifier (name or code)")
    amenity_type = Column(Text, nullable=False, comment="Type of amenity: cafe, gym, hospital, etc.")
    
    count_500m = Column(Integer, nullable=False, default=0, comment="Count within 500m radius")
    count_1km = Column(Integer, nullable=False, default=0, comment="Count within 1km radius")
    count_2km = Column(Integer, nullable=False, default=0, comment="Count within 2km radius")
    
    amenity_density_score = Column(
        Float, 
        nullable=True, 
        comment="Normalized score from amenity counts"
    )
    
    overpass_response = Column(JSON, nullable=True, comment="Full Overpass API response JSON")
    
    last_fetched = Column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    data_source = Column(Text, nullable=False, default="overpass_api")
    fetched_by = Column(Text, nullable=True)
