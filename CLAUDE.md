# suburb-intel — Project Memory

## Data Refresh Schedule

| Dataset | Frequency | How |
|---------|-----------|-----|
| **ABS data** (census metrics, SA2 boundaries) | Yearly — check for new releases | Re-run ABS ingestion loaders |
| **Overture Maps** (amenity counts — `osm_*` columns) | Monthly — check for new releases | Update `_OVERTURE_RELEASE` in `backend/app/ingestion/overture_amenity_loader.py`, then run `python -m app.ingestion.overture_amenities --download` followed by `python -m app.ingestion.overture_amenities` |
| **GTFS** (PT stop counts) | Quarterly or when state feeds update | Re-run per-state GTFS loaders |
| **Building Approvals** (ABS SA2) | Yearly — new FY zip released ~May each year | Download new zip from ABS latest release page, re-run `python -m app.ingestion.building_approvals --zip <new_zip>` |
| **Population Projections** (ABS ArcGIS) | Yearly — ABS updates the feature service | Re-run `python -m app.ingestion.population_projections` |
| **Infrastructure Australia Priority List** (PDF) | Yearly — new IPL released each year | Download new PDF to `data/infrastructure/`, re-run `python -m app.ingestion.infrastructure --pdf ../data/infrastructure/<new_pdf>` |
| **iPAMS** (Commonwealth infrastructure projects) | Yearly — live ArcGIS feed, refresh annually | Re-run `python -m app.ingestion.ipams` (fetches directly from `spatial.infrastructure.gov.au`) |
| **QLD Priority Development Areas** | Yearly — QLD declares new PDAs periodically | Re-run `python -m app.ingestion.planning_zones` — fetches from `AdminBoundariesFramework/MapServer/196` (migrated from deprecated EDQ service June 2026) |
| **NSW Planning Zones** (`sa2_zoning`) | Yearly or when LEP amendments are significant | Re-run `python -m app.ingestion.nsw_zoning` (fetches from NSW Planning Portal ArcGIS) |
| **VIC Planning Zones** (`sa2_zoning`) | Yearly or when scheme amendments are significant | Re-run `python -m app.ingestion.vic_zoning` (fetches from VicPlan ArcGIS) |
| **WA Planning Zones** (`sa2_zoning`) | Yearly or when WAPC scheme amendments accumulate | Re-run `python -m app.ingestion.wa_zoning` (fetches from SLIP public ArcGIS) |
| **SA Planning Zones** (`sa2_zoning`) | Fortnightly updates available — refresh annually | Download new zip from `https://www.dptiapps.com.au/dataportal/PDCodeZones_geojson.zip` to `data/zoning/sa_zones_geojson.zip`, then `python -m app.ingestion.sa_zoning --zip ../data/zoning/sa_zones_geojson.zip` |
| **TAS Planning Zones** (`sa2_zoning`) | Yearly or when LPS amendments accumulate | Re-run `python -m app.ingestion.tas_zoning` (fetches from LIST PlanningOnline MapServer/13, max 1000 features/page) |
| **ACT Planning Zones** (`sa2_zoning`) | Yearly or when Territory Plan variations accumulate | Re-run `python -m app.ingestion.act_zoning` (fetches from ACTGOV ArcGIS Online ACTGOV_TP_LAND_USE_ZONE FeatureServer/1) |
