# Suburb Intel API Endpoints Documentation

## 🎯 Real-Time Government Data Sources (ALL FREE)

### ABS Census Data Endpoints

#### Population & Demographics
```http
GET /api/suburb/{suburb_name}/population-by-age
```

**Description**: Get age distribution from ABS Census 2021  
**Parameters**: suburb_name - string  

**Response**:
```json
{
  "success": true,
  "data": {
    "age_groups": {
      "Under 5": 145,
      "5-14 years": 892,
      "15-24 years": 634,
      "25-34 years": 1102,
      ...
    }
  }
}
```

---

#### Household Income
```http
GET /api/suburb/{suburb_name}/income
```

**Description**: Get median household income data  
**Response**:
```json
{
  "success": true,
  "data": {
    "median_household_income_aud": 18500,
    "percentile_p85": 28000,
    "percentile_p25": 12000
  }
}
```

---

#### Housing Tenure (Ownership vs Renting)
```http
GET /api/suburb/{suburb_name}/housing-tenure
```

**Description**: Get tenure split data  
**Response**:
```json
{
  "success": true,
  "data": {
    "owned_free_hold": 420,
    "owned_mortgage": 785,
    "rented": 320,
    "other": 45
  }
}
```

---

### Education Capital Works (School Infrastructure)
```http
GET /api/suburb/{suburb_name}/education-capital-works
```

**Description**: Get school construction/refurbishment projects within 50km  
**Response**:
```json
{
  "success": true,
  "data": {
    "projects_count": 12,
    "total_investment_aud": 428000000,
    "projects": [
      {
        "name": "Eastern Primary School Refurbishment",
        "type": "Refurbishment",
        "state": "VIC",
        "value_aud": 12500000,
        "status": "planning",
        "expected_completion": "2027-06-30"
      }
    ]
  }
}
```

---

### Healthcare Access (Hospitals)
```http
GET /api/suburb/{suburb_name}/hospitals-nearby
```

**Description**: Get hospitals within 50km sorted by distance  
**Response**:
```json
{
  "success": true,
  "data": {
    "count": 8,
    "hospitals": [
      {
        "name": "Royal Melbourne Hospital",
        "state": "VIC",
        "beds": 725,
        "sector": "Public",
        "distance_km": 12.4
      },
      ...
    ]
  }
}
```

---

### Infrastructure Projects (National Pipeline)
```http
GET /api/suburb/{suburb_name}/infrastructure-projects
```

**Description**: Get nearby infrastructure projects from Transforming the Nation agenda  
**Response**:
```json
{
  "success": true,
  "data": {
    "count": 15,
    "total_estimated_cost_aud": 2800000000,
    "categories": {
      "Transport": {"count": 8, "cost_aud": 2200000000},
      "Health": {"count": 4, "cost_aud": 450000000},
      "Education": {"count": 3, "cost_aud": 150000000}
    },
    "projects": [
      {
        "name": "Metro Tunnel",
        "type": "Transport",
        "state": "NSW",
        "expected_completion": "2029-12-31",
        "estimated_cost_aud": 1740000000,
        "status": "under_construction"
      }
    ]
  }
}
```

---

### Combined Suburb Intelligence Score (Real-Time)
```http
GET /api/suburb/{suburb_name}/complete-data
```

**Description**: Get comprehensive data with real-time scoring  
**Response**:
```json
{
  "success": true,
  "data": {
    "name": "Carlton",
    "state": "VIC",
    "population_score": 85.2,
    "economic_score": 88.5,
    "investment_opportunity_score": 91.3,
    "scores_breakdown": {
      "population_growth": 0.82,
      "income_strength": 0.91,
      "job_diversity": 0.78,
      "affordability": 0.72,
      "infrastructure_investment": 0.65,
      "healthcare_access": 0.89,
      "education_quality": 0.71
    },
    "live_factors": {
      "nearby_schools_under_construction": 3,
      "total_infrastructure_pipeline_50km": 15,
      "hospital_beds_within_20km": 2450
    },
    "risk_indicators": []
  }
}
```

---

## 📡 Complete API Index

| Endpoint | Method | Real-Time Source | Auth Required? |
|----------|--------|------------------|----------------|
| `/api/search` | GET | - | ❌ |
| `/api/suburb/{suburb}/rankings` | GET | ABS Census | ❌ |
| `/api/suburb/{suburb}` | GET | Calculated Score | ❌ |
| **`/api/suburb/{suburb}/population-by-age`** | **GET** | **ABS Census 2021** | **❌ FREE** |
| **`/api/suburb/{suburb}/income`** | **GET** | **ABS Census 2021** | **❌ FREE** |
| **`/api/suburb/{suburb}/housing-tenure`** | **GET** | **ABS Census 2021** | **❌ FREE** |
| **`/api/suburb/{suburb}/education-capital-works`** | **GET** | **ABS Education API** | **❌ FREE** |
| **`/api/suburb/{suburb}/hospitals-nearby`** | **GET** | **AIHW Hospital Data** | **❌ FREE (with limit)** |
| **`/api/suburb/{suburb}/infrastructure-projects`** | **GET** | **Infrastructure Australia + Scraping** | **❌ FREE** |
| `/api/rankings` | GET | Calculated from above | ❌ |

---

## 🔧 Implementation Status

### ✅ Ready to Use:
- `population-by-age` - ABS Census 2021 live data
- `income` - ABS Census median household income
- `housing-tenure` - ABS housing tenure split

### 🟡 In Development:
- `education-capital-works` - ABS Education API endpoint
- `hospitals-nearby` - AIHW hospital data (needs geospatial join)
- `infrastructure-projects` - Web scraping + structured storage

### ⚪ Future Enhancements:
- Geocoding to SA2 boundaries (Geoscience Australia API)
- Real-time job market data (ABS Employment statistics)
- Local council planning permits (state-level APIs)

---

## 🎯 Testing Each Endpoint

```bash
# Test population endpoint
curl http://localhost:8000/api/suburb/Carlton/population-by-age

# Test income endpoint  
curl http://localhost:8000/api/suburb/Carlton/income

# Test housing tenure
curl http://localhost:8000/api/suburb/Carlton/housing-tenure

# Test all combined
curl http://localhost:8000/api/suburb/Carlton/complete-data
```

---

## 📚 Data Sources Reference

All endpoints pull from FREE Australian government sources:

1. **ABS Census 2021** - Population, income, age, housing (FREE)
   - No API key required
   - Update every 5 years

2. **ABS Education Capital Works** - School construction projects (FREE)  
   - Annual updates
   - State-level queries available

3. **AIHW Hospital Data** - Healthcare infrastructure (FREE with limits)
   - Limited to research/academic use
   - ~100 requests/day recommended

4. **Infrastructure Australia** - National project pipeline (FREE via scraping)
   - Annual reports + web data
   - Supplement with state portals

---

## 🚀 Next Steps for Full Real-Time Data

1. ✅ Add `education-capital-works` endpoint  
2. ⏳ Implement geospatial hospital queries  
3. ⏳ Build infrastructure project scraper (annual → database)  
4. ⏳ Add SA2 boundary lookup integration  

**Current status**: Core ABS endpoints working with live data! 🎉
