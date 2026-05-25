"""
Data sources for suburb intelligence API.

Exports available data source classes:
- AustralianDataSources: Free Australian government APIs (ABS Census, AIHW)
- OSMOverpassDataSource: OpenStreetMap amenity density data (import directly from osm_overpass.py)
"""

from app.api.data_sources import AustralianDataSources  # ABS Census & other gov APIs

__all__ = ["AustralianDataSources"]

