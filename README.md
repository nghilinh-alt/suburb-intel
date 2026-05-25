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
