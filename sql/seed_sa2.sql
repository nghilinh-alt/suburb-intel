-- Seed SA2 regions (example suburbs)
INSERT INTO sa2_regions (sa2_code, sa2_name, state) VALUES
('30150', 'Altona Gardens VIC', 'VIC'),
('34005', 'Ashtabula QLD', 'QLD'),
('48210', 'Brisbane Waters QLD', 'QLD'),
('47002', 'Chermside QLD', 'QLD'),
('22625', 'Cronulla Sydney NSW', 'NSW');

-- Seed census metrics for one year (2021)
INSERT INTO abs_census_metrics (sa2_code, year, population, median_income, median_age, renters_pct, owners_pct, industry_profile) VALUES
('30150', 2021, 8450, 95000, 34.2, 45.5, '{"healthcare": 0.15, "retail": 0.22, "finance": 0.18, "tech": 0.10, "education": 0.14}'),
('34005', 2021, 6230, 78000, 29.8, 52.3, '{"manufacturing": 0.12, "retail": 0.28, "finance": 0.12}'),
('48210', 2021, 12450, 87000, 42.1, 38.2, '{"tech": 0.25, "healthcare": 0.18, "retail": 0.15, "finance": 0.20}'),
('47002', 2021, 28900, 102000, 31.5, 48.9, '{"tech": 0.18, "finance": 0.22, "retail": 0.20, "education": 0.16}'),
('22625', 2021, 18750, 91000, 38.9, 44.1, '{"healthcare": 0.16, "retail": 0.25, "finance": 0.17, "tech": 0.12}');

-- Seed infrastructure projects
INSERT INTO infrastructure_projects (project_id, name, type, value_aud, status, lat, lon) VALUES
('INFRA-001', 'Brisbane Metro Tunnel Extension', 'transport', 2500000000, 'under_construction', -27.4700, 153.0300),
('INFRA-002', 'Chermside Hospital Upgrade', 'health', 450000000, 'approved', -27.4850, 153.0600),
('INFRA-003', 'Gold Coast School Complex', 'education', 120000000, 'under_construction', -28.0167, 153.4000),
('INFRA-004', 'Sydney West Rail Link', 'transport', 3200000000, 'planned', -33.9200, 151.1800);

-- Link SA2 regions to infrastructure projects
INSERT INTO sa2_project_link (sa2_code, project_id, impact_score) VALUES
('48210', 'INFRA-001', 85.0),
('47002', 'INFRA-002', 92.0),
('22625', 'INFRA-004', 78.0);
