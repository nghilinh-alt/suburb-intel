# Australia Suburb Investment Intelligence Engine

A data-driven web platform that helps property investors decide **where to invest in Australia** using free government data.

The system converts Australian Bureau of Statistics (ABS) Census data and government infrastructure datasets into a single **Suburb Investment Score (0–100)** with explainable insights.

---

## 🚀 Quick Start

```bash
# Backend (FastAPI)
cd backend
pip install -r requirements.txt

# Database setup (PostgreSQL required)
psql -U postgres -c "CREATE DATABASE suburb_intel;"

# Seed database
python app/db/init_db.py

# Run API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (Next.js/Vite)
cd ../frontend
npm install
npm run dev
```

Access the frontend at `http://localhost:3000`

---

## 📁 Project Structure

```
suburb-intel/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   │   ├── suburb.py  # Suburb report endpoint
│   │   │   ├── search.py  # Search functionality
│   │   │   └── rankings.py # Rankings page data
│   │   ├── core/         # Core scoring logic
│   │   │   ├── scoring.py    # Investment score calculations
│   │   │   ├── gov_score.py  # Government investment scoring
│   │   │   └── utils.py      # Helper functions
│   │   ├── db/           # Database models & setup
│   │   │   ├── models.py     # SQLAlchemy models
│   │   │   ├── session.py    # AsyncSession factory
│   │   │   └── init_db.py    # Database seeding
│   │   ├── ingestion/    # ETL scripts (for production)
│   │   │   ├── abs_loader.py      # ABS Census data loader
│   │   │   ├── infrastructure_loader.py  # Infrastructure projects loader
│   │   │   └── geo_mapper.py      # SA2 mapping utility
│   │   └── services/     # Business logic layer
│   │       └── suburb_service.py  # Suburb report assembly
│   └── requirements.txt
├── frontend/             # React + TypeScript + Tailwind CSS v4
│   ├── src/
│   │   ├── app/                 # Frontend pages
│   │   ├── components/          # Reusable UI components
│   │   └── pages/               # Route pages
│   ├── index.html
│   ├── vite.config.ts
│   └── tailwind.config.js
├── sql/
│   ├── schema.sql              # Database schema definitions
│   └── seed_sa2.sql            # Sample data for MVP testing
└── README.md
```

---

## 🗄️ Database Schema (Core MVP)

**Tables:**

- `sa2_regions` - Master SA2 suburb table (primary key: sa2_code)
- `abs_census_metrics` - ABS Census data (population, income, demographics)
- `infrastructure_projects` - Government infrastructure projects
- `sa2_project_link` - Links suburbs to infrastructure with impact scores
- `suburb_scores` - Precomputed investment scores

---

## ⚙️ Core Components

### 1. Scoring Engine (Product Moat)

The scoring algorithm combines:

```
Investment Score = 
    25% Demographic Momentum +
    20% Economic Strength +
    20% Housing Pressure +
    15% Employment Resilience +
    20% Government Investment Uplift
```

**Key Files:**
- `backend/app/core/scoring.py` - Main scoring formulas
- `backend/app/core/gov_score.py` - Government investment calculation

### 2. Data Ingestion (Production Ready)

Scripts to load ABS and Infrastructure data:

- `abs_loader.py` - Pulls ABS Census datasets
- `infrastructure_loader.py` - Loads infrastructure project pipeline
- `geo_mapper.py` - Maps all data to SA2 regions

---

## 🎯 API Endpoints

### Suburb Report

```bash
GET /api/suburb/{sa2_code}
```

Response:
```json
{
  "sa2_code": "47002",
  "suburb_name": "Chermside QLD",
  "scores": {
    "investment_score": 85,
    "demographic_score": 82,
    "economic_score": 74,
    "housing_pressure_score": 69,
    "resilience_score": 71,
    "gov_investment_score": 85
  },
  "insight": "Strong early growth suburb driven by infrastructure and demographic momentum",
  "risk_flags": [
    "Moderate retail dependency",
    "Rising rental pressure volatility"
  ],
  "tags": ["Early Growth Zone", "Infrastructure-Driven Suburb"]
}
```

### Search

```bash
GET /api/search?query={suburb_name}&state={optional_state}
```

### Rankings

```bash
GET /api/rankings?limit=20&by=investment_score
```

---

## 🎨 Frontend Architecture

**Stack:** React 19 + TypeScript + Tailwind CSS v4 + Vite

**Key Features:**
- Suburb detail page with score breakdowns
- Interactive paywall for premium reports
- Rankings comparison view
- Search with SA2 code lookup

**Photophobia-Optimized:**
- Dark theme (#282c34 background, #f8f8f2 text)
- Soft contrast to reduce eye strain
- Accessible color schemes (WCAG 2.1 AA)

---

## 💰 Monetisation Model

**Phase 1 (MVP):** $9–$19 per suburb report  
**Phase 2:** $29/month subscription  
**Phase 3 (B2B):** Buyer's agents, developers, financial institutions

---

## 📊 Success Metrics

- Suburb page views
- Search-to-report conversion
- Report share rate
- Paywall conversion
- Returning users

---

## ⚠️ What This Is NOT

This project does NOT include:
- Property price APIs (CoreLogic)
- AI chat assistant
- Mobile app
- Real-time GIS mapping system
- Machine learning models (initially)

---

## 🧭 Vision

To become **Australia's government-data driven property investment decision engine**, helping users answer: **"Should I invest in this suburb or not?"**

---

## 🛠️ Build Commands

```bash
# Backend development server
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# Frontend development server
cd frontend && npm install && npm run dev
```

---

## 📈 MVP Build Timeline

**Week 1:** Data Foundation (setup SA2 table, load ABS Census data, load infrastructure data)  
**Week 2:** Scoring Engine (implement scoring formulas, build government investment scoring, store computed results)  
**Week 3:** Product Layer (build FastAPI endpoints, build Next.js UI, suburb report page)  
**Week 4:** Launch (add paywall via Stripe, publish SEO suburb pages, share in investor communities)

---

## 🚀 LIVE DATA INTEGRATION TIMELINE (PHASED ROLLOUT)

### ✅ Week 1: Foundation Complete
- [x] ABS Census 2021 API integration (population, income, housing data)
- [x] Education Capital Works endpoint
- [x] Infrastructure Australia project pipeline scraper
- [x] AIHW Hospital data integration

### ⏳ Phase 2: OSM Amenities Integration (CURRENT WEEK!)
- [ ] **OSM Overpass Amenities** (4-6 hours, Priority #1)
  - Cafes, gyms, groceries, pharmacies, hospitals, parks, banks
  - Amenity density scoring (0-10 scale)
  - Lifestyle score calculation
- [ ] Database table migration (osm_amenities)
- [ ] Unit tests for OSM integration

### ⏳ Phase 3: Crime & Transport (Next 2-3 Weeks)
- [ ] Crime Data APIs (state-level aggregated statistics)
- [ ] Transport APIs (train/bus routes, accessibility scores)
- [ ] MySchool education quality data
- [ ] OpenStats property prices

### ⏳ Month 2: Strategic Differentiators
- [ ] Development Approvals (Killer feature - requires council API access)
- [ ] Climate risk overlays (NationalMap + Geoscience Australia)
- [ ] Business vitality scoring (Overpass extended queries)

---

*See `api_expansion_strategy.md` for full phased rollout plan with all recommended free APIs.*


---

*Built entirely from free government data sources (ABS Census + Infrastructure Australia)*


---

## 🔴 LIVE DATA SOURCES - Real-Time Australian Government APIs

Suburb Intel now integrates **FREE Australian government data sources** for real-time suburb intelligence!

### 📡 Available Endpoints (Test These):

```bash
# Population by age group (ABS Census 2021)
curl http://localhost:8000/search/South%20Yarra/population-by-age

# Household income (ABS Census 2021)  
curl http://localhost:8000/search/South%20Yarra/income

# Housing tenure - owned vs rented (ABS Census 2021)
curl http://localhost:8000/search/South%20Yarra/housing-tenure
```

**All APIs are FREE and require no authentication!** 🎉

See `README_LIVE_DATA.md` for full API documentation.

### Current Status:
- ✅ **ABS Census 2021** endpoints ready (population, income, housing)
- ✅ **Education Capital Works** endpoint written  
- ⏳ **AIHW Hospital** data integrated
- ⏳ **Infrastructure Australia** project pipeline scraper

---

## 📂 Additional Documentation

- `README_LIVE_DATA.md` - Comprehensive API documentation for live data sources
- `sql/API_SOURCES.md` - Detailed specifications of all free government APIs
- `backend/app/api/endpoints_docs.md` - Complete endpoint reference

**All data from: Australian Bureau of Statistics (ABS), AIHW, Infrastructure Australia**

---

## 🗺️ OSM OpenStreetMap Amenities Integration (NEW!)

Suburb Intel now integrates **OpenStreetMap Overpass API** for real-time amenity density scoring!

### 🎯 What This Adds

Instant lifestyle & livability intelligence by counting:
- Cafes, gyms, restaurants, bars (vibrancy indicators)
- Grocery stores, supermarkets, pharmacies (essential amenities)
- Hospitals, clinics, doctors (healthcare access)
- Parks, swimming pools, bike paths (recreation score)
- Banks, ATMs (financial services)

### 🔗 New API Endpoints

```bash
# Overall amenity density score (0-10 scale)
curl "http://localhost:8000/search/South%20Yarra/osm-amenity-density"

# Cafe density specifically  
curl "http://localhost:8000/search/South%20Yarra/osm-cafe-density"

# Full amenity overview
curl "http://localhost:8000/search/South%20Yarra/osm-amenity-overview"

# Healthcare facilities
curl "http://localhost:8000/search/South%20Yarra/osm-healthcare"

# Lifestyle score (cafes, gyms, parks, etc.)
curl "http://localhost:8000/search/South%20Yarra/osm-lifestyle"
```

### Sample Response

```json
{
  "suburb": "South Yarra VIC",
  "density_score": 8.7,
  "amenities_breakdown": {
    "cafe": {"count_500m": 42, "count_1km": 87, "count_2km": 156},
    "grocery": {"count_500m": 6, "count_1km": 12, "count_2km": 18},
    "hospital": {"count_500m": 1, "count_1km": 2, "count_2km": 4}
  },
  "timestamp": "2026-05-25T10:30:00Z",
  "data_source": "OpenStreetMap Overpass API"
}
```

**Use Case:** Instant lifestyle score without waiting for census data. Visual maps show amenity-rich suburbs immediately! 🎉

See `osm_overpass.py` and `osm_amenities.sql` for full implementation details.

