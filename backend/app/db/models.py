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
    separate_house_pct     = Column(Float, nullable=True, comment="% of occupied private dwellings that are separate houses (G36)")
    flat_apartment_pct     = Column(Float, nullable=True, comment="% of occupied private dwellings that are flats/apartments (G36)")
    flat_low_rise_pct      = Column(Float, nullable=True, comment="% of dwellings that are flats in 1-2 storey blocks (G41)")
    flat_mid_rise_pct      = Column(Float, nullable=True, comment="% of dwellings that are flats in 3-8 storey blocks (G41)")
    flat_high_rise_pct     = Column(Float, nullable=True, comment="% of dwellings that are flats in 9+ storey blocks (G41)")
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
    osm_hospitals        = Column(Integer, nullable=True, comment="Actual hospitals only: hospital, urgent_care_center, emergency_room (Overture)")
    osm_medical_centers  = Column(Integer, nullable=True, comment="GP clinics + medical centres + doctors offices (Overture primary care)")
    osm_pharmacies   = Column(Integer, nullable=True, comment="Pharmacies + drugstores")
    osm_shopping_centres = Column(Integer, nullable=True, comment="Shopping malls + department stores")

    # ── ABS Business Register counts (ANZSIC, June 2025) ─────────────────
    biz_food_services     = Column(Integer, nullable=True, comment="ANZSIC H: Accommodation and Food Services (cafes, restaurants, takeaways)")
    biz_retail_trade      = Column(Integer, nullable=True, comment="ANZSIC G: Retail Trade (shops)")
    biz_health_social     = Column(Integer, nullable=True, comment="ANZSIC Q: Health Care and Social Assistance (GPs, pharmacies, allied health)")
    biz_construction      = Column(Integer, nullable=True, comment="ANZSIC E: Construction (builders, tradies)")
    biz_professional      = Column(Integer, nullable=True, comment="ANZSIC M: Professional, Scientific and Technical Services")
    biz_education         = Column(Integer, nullable=True, comment="ANZSIC P: Education and Training")
    biz_finance           = Column(Integer, nullable=True, comment="ANZSIC K: Financial and Insurance Services")
    biz_arts_recreation   = Column(Integer, nullable=True, comment="ANZSIC R: Arts and Recreation Services (gyms, sport)")
    biz_other_services    = Column(Integer, nullable=True, comment="ANZSIC S: Other Services (mechanics, hair, laundry)")
    biz_total             = Column(Integer, nullable=True, comment="Total registered businesses across all ANZSIC divisions")

    # ── Service businesses (Overture) ────────────────────────────────────
    osm_mechanics        = Column(Integer, nullable=True, comment="Auto repair / mechanics")
    osm_hardware_stores  = Column(Integer, nullable=True, comment="Hardware stores (Bunnings etc)")
    osm_petrol_stations  = Column(Integer, nullable=True, comment="Petrol / fuel stations")
    osm_banks            = Column(Integer, nullable=True, comment="Bank branches")
    osm_post_offices     = Column(Integer, nullable=True, comment="Post offices")
    osm_laundries        = Column(Integer, nullable=True, comment="Laundromats + dry cleaners")
    osm_car_washes       = Column(Integer, nullable=True, comment="Car washes")
    osm_vets             = Column(Integer, nullable=True, comment="Veterinary clinics")
    osm_pet_stores       = Column(Integer, nullable=True, comment="Pet stores")
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
    """Scored output for each SA2. Populated by app/jobs/backfill_scores.py.

    All *_score columns are 0–10 (higher = better).
    Intermediate columns store the key derived inputs so the self-investigation
    system can explain any score without re-running the pipeline.
    """
    __tablename__ = "suburb_scores"

    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), primary_key=True)

    # ── Composite score ───────────────────────────────────────────────────────
    investment_score = Column(Float, nullable=True, comment="Weighted composite 0–10")

    # ── Dimension scores (0–10) ───────────────────────────────────────────────
    liveability_score     = Column(Float, nullable=True, comment="Amenity + transit + healthcare + parks")
    education_score       = Column(Float, nullable=True, comment="School ICSEA quality + type coverage")
    growth_score          = Column(Float, nullable=True, comment="Population growth + investment + gentrification")
    demographic_score     = Column(Float, nullable=True, comment="Income + SEIFA + education + employment")
    housing_score         = Column(Float, nullable=True, comment="Mortgage/rent stress + dwelling character")
    infrastructure_score  = Column(Float, nullable=True, comment="Govt committed investment pipeline")
    gentrification_index  = Column(Float, nullable=True, comment="0–10 composite gentrification signal")

    # ── Derived intermediates (explain scores, support self-investigation) ────
    edu_avg_icsea         = Column(Float,   nullable=True, comment="Enrolment-weighted avg ICSEA of linked K-12 schools")
    edu_top_school_count  = Column(Integer, nullable=True, comment="Schools with ICSEA ≥ 1100 within/adjacent SA2")
    edu_secondary_count   = Column(Integer, nullable=True, comment="Secondary + Combined schools within/adjacent")
    edu_tertiary_count    = Column(Integer, nullable=True, comment="University + TAFE campuses within/adjacent")
    health_hospital_score = Column(Float,   nullable=True, comment="Sum of impact_score for public hospitals (1.0=in SA2, 0.5=adjacent)")
    health_gp_count       = Column(Integer, nullable=True, comment="GP clinics + medical centres (from Overture)")
    infra_committed_aud   = Column(Float,   nullable=True, comment="Total committed govt investment linked to SA2 ($AUD)")
    infra_project_count   = Column(Integer, nullable=True, comment="Active infrastructure projects linked to SA2")
    transit_score_raw     = Column(Float,   nullable=True, comment="train×4 + tram×3 + ferry×2 + bus×1 stop count")

    # ── Risk flags ────────────────────────────────────────────────────────────
    risk_flags = Column(JSON, nullable=True, comment="List of raised risk flag strings")

    # ── Metadata ─────────────────────────────────────────────────────────────
    score_version = Column(Text,     nullable=True, comment="Engine version tag")
    updated_at    = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_suburb_scores_investment_desc", "investment_score"),
        Index("ix_suburb_scores_growth", "growth_score"),
        Index("ix_suburb_scores_liveability", "liveability_score"),
    )


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
    source      = Column(Text, nullable=True, comment="Data source: ACARA | GA Foundation Facilities")
    # Provenance
    acara_location_age_id = Column(Text, nullable=True, comment="Location AGE ID from ACARA location file")

    __table_args__ = (
        Index("ix_schools_sa2", "sa2_code"),
        Index("ix_schools_state", "state"),
        Index("ix_schools_sector_type", "sector", "school_type"),
    )


class ShoppingCentre(Base):
    """Named shopping centres sourced from OpenStreetMap (shop=mall).

    Loaded by python -m app.ingestion.shopping_centres_loader
    Refreshed periodically — OSM data is community-maintained and improving.
    """
    __tablename__ = "shopping_centres"

    osm_id    = Column(Text, primary_key=True, comment="OSM element ID")
    name      = Column(Text, nullable=False)
    lat       = Column(Float, nullable=True)
    lon       = Column(Float, nullable=True)
    state     = Column(Text, nullable=True)
    suburb    = Column(Text, nullable=True)
    postcode  = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_shopping_centres_latlon", "lat", "lon"),
        Index("ix_shopping_centres_state", "state"),
    )


class PropRadarSuburbCache(Base):
    """PropRadar suburb market data — cached for 30 days on first request.

    Populated by GET /suburb-group/{slug} on first view via propradar_loader.py.
    Contains median prices, yields, growth rates, days on market, vacancy, heat score.
    """
    __tablename__ = "propradar_suburb_cache"

    suburb_id              = Column(Text, primary_key=True)

    # Median prices
    house_median_price     = Column(Integer, nullable=True)
    unit_median_price      = Column(Integer, nullable=True)
    house_weekly_rent      = Column(Integer, nullable=True)
    unit_weekly_rent       = Column(Integer, nullable=True)

    # Yields
    house_gross_yield_pct  = Column(Float, nullable=True)
    unit_gross_yield_pct   = Column(Float, nullable=True)

    # Capital growth
    house_1y_growth_pct    = Column(Float, nullable=True)
    unit_1y_growth_pct     = Column(Float, nullable=True)
    house_3y_growth_pct    = Column(Float, nullable=True)
    unit_3y_growth_pct     = Column(Float, nullable=True)
    house_5y_growth_pct    = Column(Float, nullable=True)
    unit_5y_growth_pct     = Column(Float, nullable=True)
    house_growth_confidence = Column(Text, nullable=True)

    # Market dynamics
    house_days_on_market   = Column(Integer, nullable=True)
    unit_days_on_market    = Column(Integer, nullable=True)
    vacancy_rate_pct       = Column(Float, nullable=True)
    house_sales_12mo       = Column(Integer, nullable=True)
    unit_sales_12mo        = Column(Integer, nullable=True)
    house_heat_score       = Column(Float, nullable=True)
    sold_vs_asking_pct     = Column(Float, nullable=True)

    fetched_at  = Column(DateTime, nullable=True)
    as_of       = Column(Text, nullable=True, comment="PropRadar data timestamp")


class SuburbPlaceCache(Base):
    """On-demand Foursquare place counts per suburb, cached for 30 days.

    Populated by GET /suburb-group/{slug}/places on first request.
    source = 'foursquare_v3'
    data_json = JSON object: {category_name: count, ...}
    """
    __tablename__ = "suburb_place_cache"

    suburb_id  = Column(Text, primary_key=True)
    source     = Column(Text, nullable=False, default="foursquare_v3")
    data_json  = Column(JSON, nullable=True, comment="Category→count mapping")
    lat        = Column(Float, nullable=True, comment="Centroid lat used for query")
    lon        = Column(Float, nullable=True, comment="Centroid lon used for query")
    radius_m   = Column(Integer, nullable=True, comment="Query radius in metres")
    fetched_at = Column(DateTime, nullable=True)


class PostcodeSA2Map(Base):
    """Maps Australian postcodes to SA2 regions (ABS 2021 mesh block correspondence).

    One postcode can span multiple SA2s — all are stored. is_dominant=1 marks
    the SA2 that contains the most mesh blocks for that postcode.
    Built by app/jobs/build_postcode_map.py.
    """
    __tablename__ = "postcode_sa2_map"

    postcode  = Column(Text, primary_key=True)
    sa2_code  = Column(Text, ForeignKey("sa2_regions.sa2_code"), primary_key=True)
    mb_count  = Column(Integer, nullable=True, comment="Number of mesh blocks in this postcode that fall in this SA2")
    is_dominant = Column(Integer, nullable=True, comment="1 if this SA2 has the most mesh blocks for this postcode")

    __table_args__ = (Index("ix_postcode_sa2_postcode", "postcode"),)


class SuburbAggregate(Base):
    """Population-weighted aggregate of all SA2s that share the same base suburb name.

    Built by app/jobs/build_suburb_aggregates.py.
    Single-SA2 suburbs also get a row (sa2_count=1) so search always hits this table.
    """
    __tablename__ = "suburb_aggregates"

    suburb_id    = Column(Text, primary_key=True, comment="slug: 'keysborough-vic'")
    suburb_name  = Column(Text, nullable=False,   comment="Display name: 'Keysborough'")
    state        = Column(Text, nullable=False)
    sa2_codes    = Column(JSON, nullable=False,   comment="List of SA2 codes in this group")
    sa2_names    = Column(JSON, nullable=False,   comment="List of SA2 display names")
    sa2_count    = Column(Integer, nullable=False)
    population   = Column(Integer, nullable=True, comment="Total population across all SA2s")

    # Population-weighted average dimension scores (0–10)
    investment_score     = Column(Float, nullable=True)
    liveability_score    = Column(Float, nullable=True)
    education_score      = Column(Float, nullable=True)
    growth_score         = Column(Float, nullable=True)
    demographic_score    = Column(Float, nullable=True)
    housing_score        = Column(Float, nullable=True)
    infrastructure_score = Column(Float, nullable=True)
    gentrification_index = Column(Float, nullable=True)

    # Weighted census facts
    median_income   = Column(Float, nullable=True)
    median_age      = Column(Float, nullable=True)
    unemployment_pct = Column(Float, nullable=True)
    uni_degree_pct  = Column(Float, nullable=True)
    pop_growth_proj_pct = Column(Float, nullable=True)

    # Union of all constituent risk flags
    risk_flags = Column(JSON, nullable=True)

    score_version = Column(Text, nullable=True)
    updated_at    = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_suburb_agg_state",  "state"),
        Index("ix_suburb_agg_name",   "suburb_name"),
        Index("ix_suburb_agg_inv",    "investment_score"),
    )


class SA2Zoning(Base):
    """Land use zoning breakdown per SA2, derived from state planning portal data.

    Each pct column is the fraction of the SA2's area covered by that zone category (0–100).
    Null means the state's data has not been loaded for that SA2.
    Currently populated for NSW only; VIC/QLD/others to follow.
    """
    __tablename__ = "sa2_zoning"

    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), primary_key=True)
    state    = Column(Text, nullable=True, comment="State code whose zoning data was loaded")

    # Residential
    zone_pct_high_density_res  = Column(Float, nullable=True, comment="% SA2 area zoned High Density Residential")
    zone_pct_medium_density_res = Column(Float, nullable=True, comment="% SA2 area zoned Medium Density Residential")
    zone_pct_low_density_res   = Column(Float, nullable=True, comment="% SA2 area zoned Low/General Density Residential or Village")
    zone_pct_large_lot_res     = Column(Float, nullable=True, comment="% SA2 area zoned Large Lot Residential")
    zone_pct_residential_total = Column(Float, nullable=True, comment="% SA2 area zoned for any residential use")

    # Mixed use / commercial
    zone_pct_mixed_use         = Column(Float, nullable=True, comment="% SA2 area zoned Mixed Use")
    zone_pct_commercial        = Column(Float, nullable=True, comment="% SA2 area zoned commercial centre / local centre")

    # Industrial / employment
    zone_pct_industrial        = Column(Float, nullable=True, comment="% SA2 area zoned industrial or employment")

    # Open space
    zone_pct_public_recreation = Column(Float, nullable=True, comment="% SA2 area zoned Public Recreation or Open Space")
    zone_pct_environmental     = Column(Float, nullable=True, comment="% SA2 area zoned Environmental Conservation/Management")

    # Development pressure signal
    zone_pct_urban_development = Column(Float, nullable=True, comment="% SA2 area in transition/urban development zones")

    # Provenance
    zone_breakdown_json = Column(JSON, nullable=True, comment="Full zone class breakdown {class: pct} for audit/self-investigation")
    source              = Column(Text, nullable=True)
    source_date         = Column(Text, nullable=True)

    __table_args__ = (Index("ix_sa2_zoning_state", "state"),)


class PlanningZone(Base):
    __tablename__ = "planning_zones"

    zone_id       = Column(Text, primary_key=True, comment="'pda-<objectid>'")
    name          = Column(Text, nullable=False)
    zone_type     = Column(Text, nullable=True, comment="PDA | future zone types")
    status        = Column(Text, nullable=True, comment="eg. Declared | Superseded")
    lga_name      = Column(Text, nullable=True)
    gazetted_date = Column(Text, nullable=True, comment="ISO date string")
    state         = Column(Text, nullable=True)
    source        = Column(Text, nullable=True)
    geometry_geojson = Column(Text, nullable=True, comment="GeoJSON polygon (WGS84)")

    __table_args__ = (Index("ix_planning_zones_type", "zone_type"),)


class SA2PlanningLink(Base):
    __tablename__ = "sa2_planning_link"

    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False, primary_key=True)
    zone_id  = Column(Text, ForeignKey("planning_zones.zone_id"), nullable=False, primary_key=True)
    overlap_pct  = Column(Float, nullable=True, comment="Fraction of SA2 area covered by the planning zone (0–1)")
    impact_score = Column(Float, nullable=True, comment="Same as overlap_pct for now; capped at 1.0")


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
