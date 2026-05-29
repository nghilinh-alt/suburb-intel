# suburb-intel — Project Memory

## Data Refresh Schedule

| Dataset | Frequency | How |
|---------|-----------|-----|
| **ABS data** (census metrics, SA2 boundaries) | Yearly — check for new releases | Re-run ABS ingestion loaders |
| **Overture Maps** (amenity counts — `osm_*` columns) | Monthly — check for new releases | Update `_OVERTURE_RELEASE` in `backend/app/ingestion/overture_amenity_loader.py`, then run `python -m app.ingestion.overture_amenities --download` followed by `python -m app.ingestion.overture_amenities` |
| **GTFS** (PT stop counts) | Quarterly or when state feeds update | Re-run per-state GTFS loaders |
| **Building Approvals** (ABS SA2) | Yearly — new FY zip released ~May each year | Download new zip from ABS latest release page, re-run `python -m app.ingestion.building_approvals --zip <new_zip>` |
| **Population Projections** (ABS ArcGIS) | Yearly — ABS updates the feature service | Re-run `python -m app.ingestion.population_projections` |
