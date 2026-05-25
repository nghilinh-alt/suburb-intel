-- Migration: Add OSM Amenities Table for amenity density scoring
-- Created: 2026-05-25
-- Purpose: Store OpenStreetMap Overpass API amenity count data

-- Enable foreign keys (PostgreSQL)
ALTER TABLE suburbs ENABLE ROW LEVEL SECURITY;

-- Create table to store amenity counts by radius
CREATE TABLE IF NOT EXISTS osm_amenities (
    suburb_id VARCHAR(100) PRIMARY KEY,
    
    -- Amenity type: one of cafe, grocery, supermarket, pharmacy, hospital, etc.
    amenity_type VARCHAR(50),
    
    -- Count of amenities found at each radius
    count_500m INTEGER DEFAULT 0,      -- Within 500 meters
    count_1km INTEGER DEFAULT 0,        -- Within 1 km  
    count_2km INTEGER DEFAULT 0,        -- Within 2 km
    
    -- Calculated metrics
    amenity_density_score DECIMAL(4,2) CHECK (amenity_density_score >= 0 AND amenity_density_score <= 10),
    
    -- Store full Overpass API response for debugging/flexibility
    overpass_response JSONB DEFAULT '{}',
    
    -- Tracking
    last_fetched TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'overpass_api',
    fetched_by VARCHAR(100),
    
    -- Indexes for common queries
    INDEX suburb_idx (suburb_id),
    INDEX amenity_idx (amenity_type),
    INDEX suburb_amenity_composite (suburb_id, amenity_type)
);

-- Create indexes for radius-based queries
CREATE INDEX IF NOT EXISTS osm_amenities_500m_idx ON osm_amenities(suburb_id, count_500m);
CREATE INDEX IF NOT EXISTS osm_amenities_1km_idx ON osm_amenities(suburb_id, count_1km);

-- Insert sample data (for South Yarra as example)
INSERT INTO osm_amenities (suburb_id, amenity_type, count_500m, count_1km, count_2km, amenity_density_score)
VALUES 
    ('South Yarra VIC', 'cafe', 42, 87, 156, 8.9),
    ('South Yarra VIC', 'grocery', 6, 12, 18, 7.2),
    ('South Yarra VIC', 'supermarket', 3, 6, 10, 5.8),
    ('South Yarra VIC', 'pharmacy', 4, 8, 14, 6.5),
    ('South Yarra VIC', 'hospital', 1, 2, 4, 9.5),
    ('South Yarra VIC', 'bank', 3, 7, 12, 6.8),
    ('South Yarra VIC', 'gym', 2, 5, 9, 5.2),
    ('South Yarra VIC', 'park', 4, 8, 15, 7.0),
    ('South Yarra VIC', 'bar', 3, 6, 11, 5.9),
    ('South Yarra VIC', 'restaurant', 28, 52, 89, 7.4);

-- Add foreign key to suburbs table (adjust table name if needed)
ALTER TABLE osm_amenities ADD CONSTRAINT fk_osm_amenities_suburb FOREIGN KEY (suburb_id) REFERENCES suburbs(suburb_name) ON DELETE CASCADE;
