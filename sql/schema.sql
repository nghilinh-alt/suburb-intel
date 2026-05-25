-- SA2 master table
CREATE TABLE sa2_regions (
    sa2_code TEXT PRIMARY KEY,
    sa2_name TEXT,
    state TEXT
);

-- Census data
CREATE TABLE abs_census_metrics (
    sa2_code TEXT,
    year INT,
    population INT,
    median_income INT,
    median_age FLOAT,
    renters_pct FLOAT,
    owners_pct FLOAT,
    industry_profile JSONB,
    PRIMARY KEY (sa2_code, year)
);

-- Infrastructure projects
CREATE TABLE infrastructure_projects (
    project_id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    value_aud BIGINT,
    status TEXT,
    lat FLOAT,
    lon FLOAT
);

-- SA2 mapping
CREATE TABLE sa2_project_link (
    sa2_code TEXT,
    project_id TEXT,
    impact_score FLOAT
);

-- Final scores (precomputed)
CREATE TABLE suburb_scores (
    sa2_code TEXT PRIMARY KEY,
    investment_score FLOAT,
    demographic_score FLOAT,
    economic_score FLOAT,
    housing_pressure_score FLOAT,
    resilience_score FLOAT,
    gov_investment_score FLOAT,
    risk_flags JSONB,
    updated_at TIMESTAMP
);
