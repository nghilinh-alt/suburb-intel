# Development Guide - Suburb Intelligence Engine

## Quick Start for Developers

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Initialize database (creates tables and seeds sample data)
python app/db/init_db.py

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**API Test:** `curl http://localhost:8000/suburb/47002`

### 2. Frontend Setup

```bash
cd ../frontend
npm install
npm run dev
```

**UI Test:** Open `http://localhost:3000` in browser


## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌──────────┐
│  ABS API    │────▶│ Ingestion    │────▶│ Postgres │
│ (Census)    │     │ Scripts      │     │  DB      │
└─────────────┘     └──────────────┘     └──────────┘
                                      ↓
                              ┌──────────────┐
                              │ Scoring      │
                              │ Engine       │
                              └──────────────┘
                                      ↓
                              ┌──────────────┐
                              │ FastAPI      │
                              │ Backend      │
                              └──────────────┘
                                      ↓
                              ┌──────────────┐
                              │ Next.js      │
                              │ Frontend     │
                              └──────────────┘
```

### Data Flow:

1. **ETL Layer** (`app/ingestion/`): Downloads ABS Census and Infrastructure data
2. **Scoring Engine** (`app/core/`): Calculates investment scores
3. **Database** (`app/db/`): Stores precomputed scores for fast serving
4. **API Layer** (`app/api/`): REST endpoints for frontend consumption


## Core Components Explained

### Scoring Algorithm (Production-Ready)

Located: `backend/app/core/scoring.py`

```python
# Main formula - production ready
Investment Score = 
    25% × Demographic Momentum +
    20% × Economic Strength +
    20% × Housing Pressure +
    15% × Employment Resilience +
    20% × Government Investment Uplift
```

**Component breakdown:**
- `calculate_demographic_score()`: Population growth + young population %
- `calculate_economic_score()`: Income index + employment diversity  
- `calculate_housing_pressure_score()`: Renter percentage analysis
- `calculate_resilience_score()`: Industry diversification metric
- `calculate_gov_investment_score()`: Infrastructure pipeline valuation

**All functions are pure (no DB dependencies)** - perfect for testing.


### Government Investment Module

Located: `backend/app/core/gov_score.py`

Calculates impact from Infrastructure Australia's project pipeline:

```python
score += project_value × type_weightage × stage_weightage
```

Weightings:
- **Transport projects:** 1.0× (highest value)
- **Health projects:** 0.9×
- **Education projects:** 0.7×
- **Civic projects:** 0.4×

Stages:
- Under construction: 1.0×
- Approved: 0.7×
- Planned: 0.4×


### Database Schema

Located: `backend/app/db/`

**Core Tables:**

```sql
-- SA2 master (suburb identifiers)
sa2_regions
├── sa2_code TEXT PRIMARY KEY
├── sa2_name TEXT
└── state TEXT

-- Census metrics
abs_census_metrics  
├── sa2_code TEXT
├── year INT
├── population INT
├── median_income INT
├── median_age FLOAT
├── renters_pct FLOAT
├── owners_pct FLOAT
└── industry_profile JSONB

-- Infrastructure projects  
infrastructure_projects
├── project_id TEXT PRIMARY KEY
├── name TEXT
├── type TEXT (transport, health, education, civic)
├── value_aud BIGINT
├── status TEXT (under_construction, approved, planned)
└── lat, lon FLOAT

-- Links projects to regions
sa2_project_link
├── sa2_code TEXT
├── project_id TEXT
└── impact_score FLOAT

-- Final computed scores
suburb_scores
├── sa2_code TEXT PRIMARY KEY
├── investment_score FLOAT
├── demographic_score FLOAT
├── economic_score FLOAT
├── housing_pressure_score FLOAT
├── resilience_score FLOAT
├── gov_investment_score FLOAT
├── risk_flags JSONB
└── updated_at TIMESTAMP
```


### API Endpoints

**Located:** `backend/app/api/`

#### Suburb Report (`suburb.py`)

```python
GET /suburb/{sa2_code}

Response:
{
  "sa2_code": "47002",
  "suburb_name": "Chermside QLD",
  "scores": {
    "investment_score": 85.3,
    "demographic_score": 82.1,
    "economic_score": 74.5,
    "housing_pressure_score": 69.2,
    "resilience_score": 71.0,
    "gov_investment_score": 85.0
  },
  "insight": "...",
  "risk_flags": [...],
  "tags": [...]
}
```

#### Search (`search.py`)

```python
GET /search?query={suburb_name}&limit=10&state=NSW

Response: List of matching suburbs with basic stats
```

#### Rankings (`rankings.py`)

```python
GET /rankings?limit=25&by=investment_score

Response: Top suburbs ranked by selected metric
```


### Frontend Pages

**Located:** `frontend/src/pages/`

#### SearchPage (`SearchPage.tsx`)
- Suburb search input (name or SA2 code)
- Quick-access buttons for popular suburbs
- State filter dropdown

#### SuburbPage (`SuburbPage.tsx`)
- Full investment score breakdown (6 component scores)
- Key insight statement
- Risk flags with visual indicators
- Tags classification
- Paywall CTA for full report
- Historical trends placeholder

#### RankingsPage (`RankingsPage.tsx`)
- Top 50 suburbs by investment score
- Sortable columns (score, population, income)
- Quick-view links to individual suburb pages
- Comparative analysis view


### Components

Located: `frontend/src/components/`

- **Layout:** Main app shell with navigation
- **ScoreCard:** Individual score display component  
- **Breakdown:** Visual bar charts for score weights
- **Paywall:** Premium content unlock UI


## Adding Real ABS Data

Replace mock data in production:

### 1. ABS Census API Integration

Edit `backend/app/ingestion/abs_loader.py`:

```python
# Add real API call
async def fetch_census_data(year, sa2_codes):
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        # Use ABS C-5029 Census data product
        for code in sa2_codes:
            url = f"https://api.abs.gov.au/census/v1/data?sa2={code}&year={year}"
            async with session.get(url, headers={"API-Key": ABS_API_KEY}) as resp:
                data = await resp.json()
                # Parse and transform to internal schema
                # Insert into database via init_db.py patterns
```

### 2. Infrastructure Australia API Integration

Edit `backend/app/ingestion/infrastructure_loader.py`:

```python
# Add real API call  
async def fetch_infrastructure_projects():
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        # Use Infrastructure Australia pipeline API
        url = "https://api.infrastructure.gov.au/pipeline/v1/projects"
        response = await session.get(url)
        projects = await response.json()
        
        # Filter, enrich with geographic data
        # Insert via infrastructure_loader.py patterns
```


## Scoring Engine Testing

Test scoring algorithms independently:

```python
from app.core.scoring import calculate_investment_score

features = {
    "pop_growth": 35.0,
    "young_population_pct": 32.0,
    "income_index": 120.0,
    "employment_diversity": 65.0,
    "renter_pct": 40.0,
    "household_pressure": 34.0,
    "industry_diversity": 70.0,
    "projects": [
        {"type": "transport", "value_aud": 2500000000, "status": "under_construction"}
    ]
}

scores = calculate_investment_score(features)
print(scores)
# Output: {'investment_score': 85.3, 'demographic_score': 81.0, ...}
```


## Production Deployment

### Docker Compose Example

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: suburb_intel
      POSTGRES_USER: sa2
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./sql/schema.sql:/docker-entrypoint-initdb.d/schema.sql
  
  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://sa2:${DB_PASSWORD}@postgres/suburb_intel
    ports:
      - "8000:8000"
  
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on: [backend]

volumes:
  pgdata:
```


## Key Design Decisions

### Why Vite + React (not Next.js)?

- **Faster iterative development** with hot module replacement
- **Simpler routing** for SPA-style suburb pages
- **Better TypeScript integration** for type-safe API calls


### Why Async Postgres?

- High concurrency support (future growth)
- Streaming queries for large datasets  
- Async/await patterns match Python codebase naturally


### Why Precompute Scores?

- Instant API responses (no calculation on every request)
- Database indexes optimize lookups
- Historical score tracking enabled


## Security Considerations

- [ ] Add authentication for paywall protection
- [ ] Rate limit `/suburb` endpoints  
- [ ] Sanitize user input (prevent SQL injection via SA2 codes)
- [ ] Add API key validation for ABS data calls


## Future Enhancements

### Phase 2 (Subscription Tiers)
- Monthly score updates on new census releases
- Historical trend charts (last 5 years)
- Peer suburb comparisons
- Investment calculator with ROI projections

### Phase 3 (B2B Features)  
- Bulk suburb export (CSV/Excel)
- Custom scoring weights per investor type
- Developer API with rate limits
- White-label reports for real estate agencies


## Support & Contribution

For issues, questions, or contributions:
1. Check existing docs in this repo
2. Review scoring algorithms in `app/core/scoring.py`
3. Test with seeded data first (`backend/app/db/init_db.py`)

---

*Last updated: May 2026*  
*Built entirely on free government data sources*
