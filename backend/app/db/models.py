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
    distance_to_cbd_km = Column(Float, nullable=True, comment="Haversine distance from SA2 centroid to its state capital's CBD")
    adjacent_sa2_codes = Column(JSON, nullable=True, comment="SA2 codes sharing a border, precomputed once via shapely .intersects() — avoids per-request geometry ops")

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


class PropertySale(Base):
    """Individual sold-property records (bedrooms/price/date) tied to an SA2.

    Schema in place ahead of the PropRadar ingestion loader (gated on
    PROPRADAR_API_KEY, not yet configured) — see docs/nl_search_build_brief.md
    Phase 2. Table is empty until that loader runs; the suburb report endpoint
    already queries it so recent sales appear automatically once populated.
    """

    __tablename__ = "property_sales"

    id = Column(Text, primary_key=True, comment="e.g. propradar property_id + sold date hash")
    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False)
    address = Column(Text, nullable=True)
    suburb_name = Column(Text, nullable=True)
    state = Column(Text, nullable=True)
    postcode = Column(Text, nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    property_type = Column(Text, nullable=True, comment="house | unit | townhouse")
    land_size_sqm = Column(Integer, nullable=True, comment="Land size in sqm, if the source provides it")
    sold_price = Column(Integer, nullable=True)
    sold_date = Column(Text, nullable=True, comment="ISO date string")
    source = Column(Text, nullable=False, default="propradar")
    fetched_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_property_sales_sa2_beds_price_date", "sa2_code", "bedrooms", "sold_price", "sold_date"),
    )


class LocalSchool(Base):
    """School locations (name + type + coordinates) from Overture Maps places.

    No ratings of its own — used for early-childhood/vocational/tertiary
    entries ACARA doesn't cover. K-12 schools with a real rating are shown
    via SchoolRating instead (see school_service.py for how the two merge
    without duplicating entries).
    """

    __tablename__ = "local_schools"

    id = Column(Text, primary_key=True, comment="Hash of name+lat+lon")
    name = Column(Text, nullable=False)
    category = Column(Text, nullable=True, comment="Raw Overture category, e.g. elementary_school")
    level = Column(Text, nullable=True, comment="Friendly label, e.g. Primary School")
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False, comment="Containing SA2")

    __table_args__ = (Index("ix_local_schools_sa2", "sa2_code"),)


class SchoolRating(Base):
    """Per-school ICSEA rating + sector, from ACARA's School Profile file.

    Mapped to SA2 via postcode (same dominant-postcode-to-SA2 lookup as
    school_icsea_loader.py's aggregate) — coarser than LocalSchool's
    point-in-polygon match, but ACARA's file only gives a postcode, not
    coordinates.
    """

    __tablename__ = "school_ratings"

    id = Column(Text, primary_key=True, comment="ACARA 'School AGE ID'")
    name = Column(Text, nullable=False)
    suburb = Column(Text, nullable=True, comment="ACARA's own suburb text, not necessarily the SA2 name")
    state = Column(Text, nullable=True)
    sector = Column(Text, nullable=True, comment="Catholic | Independent | Government")
    is_public = Column(Integer, nullable=True, comment="1 if Government sector, 0 if Catholic/Independent (SQLite has no bool)")
    school_type = Column(Text, nullable=True, comment="Primary | Secondary | Combined | Special")
    icsea = Column(Float, nullable=True)
    icsea_percentile = Column(Float, nullable=True, comment="ACARA's own percentile (national, 0-99)")
    total_enrolments = Column(Integer, nullable=True)
    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=True, comment="Via postcode->SA2 lookup; null if postcode unmatched")

    __table_args__ = (Index("ix_school_ratings_sa2", "sa2_code"),)


class PointOfInterest(Base):
    """Named points of interest beyond the counted amenity categories —
    hospitals, shopping centres, stadiums/arenas, and other attractions,
    from Overture Maps places. Point-in-polygon matched to SA2, same as
    LocalSchool.
    """

    __tablename__ = "points_of_interest"

    id = Column(Text, primary_key=True, comment="Hash of name+lat+lon")
    name = Column(Text, nullable=False)
    category = Column(Text, nullable=True, comment="Raw Overture category, e.g. football_stadium")
    group_label = Column(Text, nullable=True, comment="Friendly grouping, e.g. Hospital, Shopping Centre, Stadium & Arena, Attraction")
    is_public_hospital = Column(Integer, nullable=True, comment="Best-effort name heuristic for hospitals only (1=public, 0=private, null otherwise) — not authoritative, see loader docstring")
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False, comment="Containing SA2")

    __table_args__ = (Index("ix_points_of_interest_sa2", "sa2_code"),)


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
