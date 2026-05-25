-- Migration Script for OSM Overpass Amenities Integration
-- Author: Suburb Intel MVP Team
-- Date: 2026-05-25

-- =========================================
-- MIGRATION: Add OSM Amenities Table
-- Purpose: Store OpenStreetMap amenity density data
-- Source: https://overpass-api.de/
-- =========================================

BEGIN;

-- Create table to store amenity counts by radius
CREATE TABLE IF NOT EXISTS osm_amenities (
    suburb_id VARCHAR(100) PRIMARY KEY,
    
    -- Amenity type (from Overpass API query)
    amenity_type VARCHAR(50),  -- cafe, grocery, supermarket, hospital, etc.
    
    -- Counts at each radius from suburb center
    count_500m INTEGER DEFAULT 0,        -- Within 500 meters
    count_1km INTEGER DEFAULT 0,         -- Within 1 km  
    count_2km INTEGER DEFAULT 0,         -- Within 2 km
    
    -- Calculated metrics
    amenity_density_score DECIMAL(4,2) CHECK (amenity_density_score >= 0 AND amenity_density_score <= 10),
    
    -- Store full Overpass API response for debugging/flexibility
    overpass_response JSONB DEFAULT '{}',
    
    -- Tracking metadata
    last_fetched TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'overpass_api',
    fetched_by VARCHAR(100),
    
    -- Indexes for common queries
    INDEX suburb_idx (suburb_id),
    INDEX amenity_idx (amenity_type),
    INDEX suburb_amenity_composite (suburb_id, amenity_type)
);

-- Create indexes for radius-based queries (improves performance)
CREATE INDEX IF NOT EXISTS osm_amenities_500m_idx ON osm_amenities(suburb_id, count_500m);
CREATE INDEX IF NOT EXISTS osm_amenities_1km_idx ON osm_amenities(suburb_id, count_1km);

-- Add foreign key to suburbs table (adjust name based on your schema)
ALTER TABLE osm_amenities ADD CONSTRAINT fk_osm_amenities_suburb 
    FOREIGN KEY (suburb_id) REFERENCES sa2_regions(sa2_name) ON DELETE CASCADE;

COMMIT;
