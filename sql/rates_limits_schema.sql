-- ============================================================================
-- Suburb Intel - Rate Limiting & Caching Database Schema
-- ============================================================================
-- This schema supports comprehensive API rate limiting, caching metadata,
-- request tracking, and analytics for the suburb-intel MVP platform.
--
-- Features:
--   - Request tracking per API endpoint
--   - Cache performance metrics
--   - Rate limit violation logging
--   - Suburb data freshness tracking
-- ============================================================================

-- Drop existing tables if they exist (for migration)
DROP TABLE IF EXISTS api_rate_limits;
DROP TABLE IF EXISTS cache_entries;
DROP TABLE IF EXISTS request_logs;
DROP TABLE IF EXISTS rate_limit_violations;
DROP TABLE IF EXISTS suburb_data_freshness;
DROP TABLE IF EXISTS background_job_queue;
DROP TABLE IF EXISTS job_results;

-- ============================================================================
-- Table 1: API Rate Limits Configuration
-- ============================================================================
-- Stores official rate limits for each external API source
CREATE TABLE api_rate_limits (
    id              SERIAL PRIMARY KEY,
    api_name        VARCHAR(255) NOT NULL,                    -- e.g., "overpass_api"
    api_description TEXT,                                     -- Human-readable description
    rate_limit_rpm  INTEGER NOT NULL,                         -- Requests per minute limit
    rate_limit_daily INTEGER DEFAULT NULL,                    -- Daily request limit (null = unlimited)
    burst_allowance DECIMAL(5,2) DEFAULT 3.0,                 -- Burst multiplier (e.g., 3x normal)
    cache_ttl_seconds INTEGER NOT NULL,                       -- Recommended cache TTL in seconds
    update_frequency VARCHAR(100),                            -- How often data updates
    response_time_avg_ms INTEGER,                             -- Average response time in ms
    daily_requests_limit_notes TEXT,                          -- Any special usage notes
    is_active       BOOLEAN DEFAULT TRUE,                     -- Can be disabled if API changes
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert current API rate limits
INSERT INTO api_rate_limits (api_name, rate_limit_rpm, cache_ttl_seconds, update_frequency) VALUES
    ('overpass_api', 10, 86400, 'static'),                    -- OSM amenities
    ('abs_data_api', 60, 3600, '5yr_census/annually_survey'), -- ABS Census data
    ('abs_education_api', 30, 172800, 'annually'),            -- Education capital works
    ('aihw_api', 30, 86400, 'quarterly'),                     -- AIHW hospital data
    ('infrastructure_australia', 30, 86400, 'annually'),      -- Infrastructure projects
    ('police_openstats_vic', 20, 21600, 'monthly'),           -- VIC police crime data
    ('bocsar_crime_nsw', 25, 21600, 'monthly'),               -- NSW BOCSAR crime data
    ('geoscience_australia', 50, NULL, 'static_download');    -- Geoscience boundaries

-- ============================================================================
-- Table 2: Cache Entry Metadata
-- ============================================================================
-- Tracks cached data with expiration times for proper cleanup
CREATE TABLE cache_entries (
    id              SERIAL PRIMARY KEY,
    cache_key       VARCHAR(512) NOT NULL UNIQUE,             -- Redis/InMemory key
    endpoint_path   VARCHAR(255) NOT NULL,                     -- Original API path
    suburb_name     VARCHAR(255) NOT NULL,                     -- Suburb for this query
    api_type        VARCHAR(100) NOT NULL,                     -- e.g., 'overpass_api'
    cache_category  VARCHAR(100),                              -- e.g., 'amenities', 'demographics'
    
    data            JSONB NOT NULL,                            -- Cached response data
    ttl_seconds     INTEGER NOT NULL,                          -- Cache TTL in seconds
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP,                                 -- Expiration time (NULL = default TTL)
    size_bytes      INTEGER,                                   -- Data size for memory management
    
    hit_count       INTEGER DEFAULT 0,                         -- How many times this was hit
    last_hit_at     TIMESTAMP,                                 -- Last cache hit time
    
    is_valid        BOOLEAN DEFAULT TRUE                       -- Mark as invalid before deletion
);

-- Indexes for efficient cache lookup
CREATE INDEX idx_cache_endpoint_suburb ON cache_entries(endpoint_path, suburb_name);
CREATE INDEX idx_cache_api_type ON cache_entries(api_type);
CREATE INDEX idx_cache_expires ON cache_entries(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_cache_hit_count ON cache_entries(hit_count DESC);

-- Trigger to automatically set expires_at
CREATE OR REPLACE FUNCTION update_expires_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.expires_at = CASE 
        WHEN NEW.ttl_seconds > 0 THEN NOW() + INTERVAL '1 second' * NEW.ttl_seconds
        ELSE NULL
    END;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_expires_at_trigger
    BEFORE INSERT OR UPDATE ON cache_entries
    FOR EACH ROW EXECUTE FUNCTION update_expires_at();


-- ============================================================================
-- Table 3: Request Logs (for analytics & rate limiting tracking)
-- ============================================================================
-- Records every API request for monitoring and pattern analysis
CREATE TABLE request_logs (
    id              BIGSERIAL PRIMARY KEY,
    client_ip       INET NOT NULL,                            -- Client IP address
    user_agent      TEXT,                                      -- Browser/client UA
    
    endpoint_path   VARCHAR(255) NOT NULL,                     -- API path
    query_params    JSONB DEFAULT '{}',                        -- Request parameters
    
    suburb_name     VARCHAR(255),                              -- Extracted suburb name
    api_type        VARCHAR(100) NOT NULL,                     -- e.g., 'overpass_api'
    
    response_time_ms INTEGER,                                  -- Actual response time
    cache_hit       BOOLEAN DEFAULT FALSE,                     -- Was this from cache?
    status_code     SMALLINT,                                  -- HTTP status
    
    request_size_bytes INTEGER,                                -- Request size
    response_size_bytes INTEGER,                               -- Response size
    
    rate_limit_remaining INTEGER,                              -- X-RateLimit-Remaining header
    retry_after_seconds INTEGER,                               -- Retry-After from API (if set)
    
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT response_time_check CHECK (response_time_ms >= 0),
    CONSTRAINT status_code_check CHECK (status_code = 0 OR status_code BETWEEN 200 AND 599)
);

-- Indexes for analytics queries
CREATE INDEX idx_request_client_ip ON request_logs(client_ip);
CREATE INDEX idx_request_api_type ON request_logs(api_type);
CREATE INDEX idx_request_created ON request_logs(created_at);
CREATE INDEX idx_request_suburb ON request_logs(suburb_name) WHERE suburb_name IS NOT NULL;


-- ============================================================================
-- Table 4: Rate Limit Violations (for alerting & monitoring)
-- ============================================================================
-- Logs all rate limit violations for analysis and alerting
CREATE TABLE rate_limit_violations (
    id              BIGSERIAL PRIMARY KEY,
    client_ip       INET NOT NULL,                            -- Client IP
    
    api_type        VARCHAR(100) NOT NULL,                     -- Which API triggered the violation
    endpoint_path   VARCHAR(255),                              -- Specific endpoint
    
    requests_in_window INTEGER NOT NULL,                       -- Requests in current window
    limit_exceeded_by INTEGER NOT NULL,                        -- How many over the limit
    
    error_message   TEXT,                                      -- API error message
    retry_after_seconds INTEGER,                               -- Seconds until reset
    
    action_taken    VARCHAR(50) DEFAULT 'blocked',             -- blocked / throttled / allowed_through
    
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT requests_in_window_check CHECK (requests_in_window > 0),
    CONSTRAINT limit_exceeded_by_check CHECK (limit_exceeded_by > 0)
);

-- Index for violation analysis
CREATE INDEX idx_violations_client_ip ON rate_limit_violations(client_ip);
CREATE INDEX idx_violations_api_type ON rate_limit_violations(api_type);
CREATE INDEX idx_violations_created ON rate_limit_violations(created_at);


-- ============================================================================
-- Table 5: Suburb Data Freshness Tracking
-- ============================================================================
-- Tracks when data was last fetched for each suburb (for cache invalidation)
CREATE TABLE suburb_data_freshness (
    id              SERIAL PRIMARY KEY,
    suburb_name     VARCHAR(255) NOT NULL,                     -- Suburb name
    
    osm_amenities   TIMESTAMP DEFAULT NULL,                    -- Last OSM amenity fetch
    osm_healthcare  TIMESTAMP DEFAULT NULL,                    -- Last healthcare data fetch
    osm_lifestyle   TIMESTAMP DEFAULT NULL,                    -- Last lifestyle venues fetch
    
    abs_population TIMESTAMP DEFAULT NULL,                     -- Last ABS population data
    abs_income      TIMESTAMP DEFAULT NULL,                    -- Last income data
    abs_tenure      TIMESTAMP DEFAULT NULL,                    -- Last tenure data
    
    education_capital TIMESTAMP DEFAULT NULL,                  -- Last school projects fetch
    aihw_hospitals  TIMESTAMP DEFAULT NULL,                    -- Last hospital data fetch
    infra_projects  TIMESTAMP DEFAULT NULL,                    -- Last infrastructure fetch
    
    crime_vic       TIMESTAMP DEFAULT NULL,                    -- Last VIC crime data
    crime_nsw       TIMESTAMP DEFAULT NULL,                    -- Last NSW crime data
    
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for freshness queries
CREATE INDEX idx_freshness_suburb ON suburb_data_freshness(suburb_name);


-- ============================================================================
-- Table 6: Background Job Queue (for processing heavy API calls)
-- ============================================================================
-- Manages queued jobs for background API processing
CREATE TABLE background_job_queue (
    id              BIGSERIAL PRIMARY KEY,
    
    job_type       VARCHAR(100) NOT NULL,                      -- 'api_call', 'scrape', 'cleanup'
    
    suburb_name     VARCHAR(255),                              -- Target suburb
    
    api_type       VARCHAR(100),                               -- e.g., 'overpass_api'
    endpoint_path   VARCHAR(255),                              -- API endpoint path
    
    priority       SMALLINT DEFAULT 5,                         -- 1=highest, 10=lowest
    attempt_count  INTEGER DEFAULT 0,                          -- Retry count
    
    payload        JSONB NOT NULL,                             -- Job parameters
    
    status         VARCHAR(50) DEFAULT 'pending',              -- pending / processing / completed / failed
    
    result_data    JSONB,                                      -- Result (if completed)
    error_message  TEXT,                                       -- Error on failure
    
    started_at     TIMESTAMP,                                  -- When processing started
    completed_at   TIMESTAMP,                                  -- When job finished
    
    created_by     VARCHAR(255) DEFAULT 'system',              -- Who/what created this
    
    CONSTRAINT status_check CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled'))
);

-- Indexes for queue operations
CREATE INDEX idx_queue_status ON background_job_queue(status);
CREATE INDEX idx_queue_suburb_api ON background_job_queue(suburb_name, api_type);
CREATE INDEX idx_queue_created ON background_job_queue(created_at) WHERE status = 'pending';


-- ============================================================================
-- Table 7: Job Results (for completed/failed jobs)
-- ============================================================================
-- Stores detailed results for completed or failed background jobs
CREATE TABLE job_results (
    id              BIGSERIAL PRIMARY KEY,
    
    suburb_name     VARCHAR(255),                              -- Target suburb
    
    api_type        VARCHAR(100) NOT NULL,                     -- Which API
    
    endpoint_path   VARCHAR(255),                              -- Endpoint used
    
    job_status      VARCHAR(50) NOT NULL,                      -- success / failed / partial
    response_time_ms INTEGER,                                  -- Total processing time
    status_code     SMALLINT,                                  -- HTTP status code
    
    raw_response    JSONB,                                      -- Full API response
    
    cache_key       VARCHAR(255),                              -- Cache key used
    
    processed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for job result queries
CREATE INDEX idx_job_status_api ON job_results(job_status, api_type);
CREATE INDEX idx_job_suburb_on_processed ON job_results(suburb_name) WHERE suburb_name IS NOT NULL;
CREATE INDEX idx_job_processed ON job_results(processed_at);


-- ============================================================================
-- Views & Functions for Analytics
-- ============================================================================

-- View: API Usage Summary by Hour
CREATE OR REPLACE VIEW api_usage_summary AS
SELECT 
    DATE_TRUNC('hour', created_at) AS hour,
    api_type,
    COUNT(*) AS request_count,
    COUNT(CASE WHEN cache_hit THEN 1 END) AS cache_hits,
    AVG(response_time_ms) AS avg_response_ms,
    MAX(response_time_ms) AS max_response_ms,
    MIN(status_code) AS min_status_code,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limit_errors
FROM request_logs
GROUP BY DATE_TRUNC('hour', created_at), api_type;


-- View: Suburb Data Freshness Status
CREATE OR REPLACE VIEW suburb_freshness_status AS
SELECT 
    s.suburb_name,
    LEAST(
        COALESCE(EXTRACT(EPOCH FROM NOW() - o.osm_amenities)::INTEGER, 86400) as osm_hours_since_update,
        COALESCE(EXTRACT(EPOCH FROM NOW() - a.abs_population)::INTEGER, 172800) as abs_hours_since_update,
        COALESCE(EXTRACT(EPOCH FROM NOW() - e.education_capital)::INTEGER, 432000) as education_hours_since_update,
        COALESCE(EXTRACT(EPOCH FROM NOW() - h.aihw_hospitals)::INTEGER, 86400) as aihw_hours_since_update,
        COALESCE(EXTRACT(EPOCH FROM NOW() - i.infra_projects)::INTEGER, 86400) as infra_hours_since_update,
        COALESCE(EXTRACT(EPOCH FROM NOW() - c.crime_vic)::INTEGER, 21600) as crime_vic_hours_since_update,
        COALESCE(EXTRACT(EPOCH FROM NOW() - cr.crime_nsw)::INTEGER, 21600) as crime_nsw_hours_since_update
    ) as hours_since_latest_update,
    CASE 
        WHEN LEAST(
            COALESCE(EXTRACT(EPOCH FROM NOW() - o.osm_amenities)::INTEGER, 86400),
            COALESCE(EXTRACT(EPOCH FROM NOW() - a.abs_population)::INTEGER, 172800)
        ) < 300 THEN 'STALE'
        ELSE 'FRESH'
    END as freshness_status
FROM suburb_data_freshness s
LEFT JOIN cache_entries o ON o.endpoint_path LIKE '%osm_amenity%' AND o.suburb_name = s.suburb_name
LEFT JOIN cache_entries a ON a.endpoint_path LIKE '%abs_population%' AND a.suburb_name = s.suburb_name
LEFT JOIN cache_entries e ON e.endpoint_path LIKE '%education_capital%' AND e.suburb_name = s.suburb_name
LEFT JOIN cache_entries h ON h.endpoint_path LIKE '%aihw_hospitals%' AND h.suburb_name = s.suburb_name
LEFT JOIN cache_entries i ON i.endpoint_path LIKE '%infra_projects%' AND i.suburb_name = s.suburb_name
LEFT JOIN cache_entries c ON c.endpoint_path LIKE '%crime_vic%' AND c.suburb_name = s.suburb_name
LEFT JOIN cache_entries cr ON cr.endpoint_path LIKE '%crime_nsw%' AND cr.suburb_name = s.suburb_name;


-- Function: Clean up expired cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_cache() RETURNS INTEGER AS $$
DECLARE
    count INTEGER;
BEGIN
    DELETE FROM cache_entries
    WHERE expires_at IS NOT NULL 
        AND expires_at < NOW() - INTERVAL '30 minutes'
        AND is_valid = TRUE;
    
    GET STACKED DIAGNOSTICS count = ROW_COUNT();
    RETURN count;
END;
$$ LANGUAGE plpgsql;


-- Function: Clean up old request logs (keep last 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_request_logs() RETURNS INTEGER AS $$
DECLARE
    count INTEGER;
BEGIN
    DELETE FROM request_logs
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    GET STACKED DIAGNOSTICS count = ROW_COUNT();
    RETURN count;
END;
$$ LANGUAGE plpgsql;


-- Function: Get rate limit remaining for API type
CREATE OR REPLACE FUNCTION get_rate_limit_remaining(api_type VARCHAR(100)) RETURNS INTEGER AS $$
DECLARE
    limit INTEGER;
BEGIN
    SELECT rate_limit_rpm * 3 INTO limit FROM api_rate_limits WHERE api_name = api_type;
    
    -- Return current minute counter (in real implementation, would track actual count)
    RETURN COALESCE(limit - 5, 90);  -- Example: returning ~85 remaining
END;
$$ LANGUAGE plpgsql;


-- Function: Mark cache entry as invalid (for data updates)
CREATE OR REPLACE FUNCTION invalidate_cache(suburb_name VARCHAR(255)) RETURNS INTEGER AS $$
DECLARE
    count INTEGER;
BEGIN
    UPDATE cache_entries
    SET is_valid = FALSE, last_hit_at = NOW()
    WHERE suburb_name = suburb_name AND is_valid = TRUE;
    
    GET STACKED DIAGNOSTICS count = ROW_COUNT();
    RETURN count;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- Sample Data for Development Testing
-- ============================================================================

INSERT INTO cache_entries (cache_key, endpoint_path, suburb_name, api_type, data, ttl_seconds, hit_count) VALUES
    ('osm:amenities:Carlton', '/api/search/Carlton/osm-amenity-density', 'Carlton', 'overpass_api', 
     '{"amenities": {"cafe": 15, "restaurant": 28, "shop": 42}, "total": 85}', 86400, 47),
    
    ('abs:population:Carlton', '/api/search/Carlton/population-by-age', 'Carlton', 'abs_data_api', 
     '{"age_groups": {"Under 5": 234, "5-14 years": 1456}, "total_population": 8500}', 3600, 12),
    
    ('aihw:hospitals:Carlton', '/api/search/Carlton/hospitals-nearby', 'Carlton', 'aihw_api', 
     '{"hospitals": [{"name": "Royal Melbourne Hospital", "beds": 725}], "count": 1}', 86400, 3);


-- ============================================================================
-- Index Summary
-- ============================================================================
/*
API Usage:
- api_type ON request_logs
- suburb_name ON request_logs

Analytics:
- client_ip ON request_logs
- created_at ON request_logs

Cache Performance:
- cache_key ON cache_entries (UNIQUE)
- endpoint_path, suburb_name ON cache_entries
- expires_at ON cache_entries

Rate Limiting:
- violations indexed by client_ip, api_type

Job Processing:
- status ON background_job_queue
- created_at ON background_job_queue (pending only)
*/

-- ============================================================================
-- Usage Notes
-- ============================================================================
/*
1. INSERT into api_rate_limits when adding new API sources
2. Cache entries auto-populate from middleware, but can also be manually cached
3. Background jobs use table 6 (background_job_queue) + table 7 (job_results)
4. Views provide analytics without custom queries
5. Functions help with maintenance tasks
*/
