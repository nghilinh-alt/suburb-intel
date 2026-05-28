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

    # ── OSM amenity counts (Overpass API) ───────────────────────────────────
    osm_cafes        = Column(Integer, nullable=True, comment="OSM cafes within SA2 polygon")
    osm_restaurants  = Column(Integer, nullable=True, comment="OSM restaurants + fast food within SA2 polygon")
    osm_supermarkets = Column(Integer, nullable=True, comment="OSM supermarkets + convenience stores within SA2 polygon")
    osm_parks        = Column(Integer, nullable=True, comment="OSM parks (nodes, ways, relations) within SA2 polygon")
    osm_gyms         = Column(Integer, nullable=True, comment="OSM fitness centres / sports centres within SA2 polygon")
    osm_hospitals    = Column(Integer, nullable=True, comment="OSM hospitals + clinics + doctors within SA2 polygon")
    osm_pharmacies   = Column(Integer, nullable=True, comment="OSM pharmacies within SA2 polygon")
    amenity_score    = Column(Float,   nullable=True, comment="Weighted liveability score 0–10 from OSM amenity counts")

    # ── Property market (Domain API) ─────────────────────────────────────────
    domain_median_house_price = Column(Float,   nullable=True, comment="Median house sold price $ — most recent 12-month period (Domain API)")
    domain_median_unit_price  = Column(Float,   nullable=True, comment="Median unit/apartment sold price $ — most recent 12-month period (Domain API)")
    domain_days_on_market     = Column(Float,   nullable=True, comment="Median days on market for houses (Domain API)")
    domain_clearance_rate     = Column(Float,   nullable=True, comment="Auction clearance rate 0–1 for houses; null if < 10 auctions (Domain API)")

    # ── Legacy / cross-census fields ─────────────────────────────────────────
    industry_profile = Column(JSON, nullable=True, comment="DEPRECATED – industry bucket proportions (G53 not in scope)")
    pop_growth_5yr = Column(Float, nullable=True, comment="Population growth % between 2016 and 2021 Census")
    young_population_pct = Column(Float, nullable=True, comment="DEPRECATED – % aged 15-34 (G01 not in scope)")


class InfrastructureProject(Base):
    __tablename__ = "infrastructure_projects"
    
    project_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    value_aud = Column(Integer, nullable=True)
    status = Column(Text, nullable=False)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)


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
