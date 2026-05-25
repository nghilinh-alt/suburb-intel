# 🇦🇺 Free Australian Government Data Sources (FREE APIs)

## 📊 **Summary Table**

| Source | What It Provides | API Endpoint | Authentication | Update Frequency | Cost |
|--------|-----------------|--------------|-----------------|------------------|------|
| **ABS Census** | Population, income, age, employment, housing, households | https://api.abs.gov.au | None (free) | 5 years | FREE |
| **Infrastructure Australia** | Project pipeline (10yr), transport upgrades | Web portal + CSV exports | None | Annual reports | FREE |
| **AIHW** | Hospital beds, health investments | https://api.data.aihw.gov.au | Registration | Quarterly | FREE |
| **ABS Education** | School capital works | ABS API Hub | None | Annual | FREE |
| **Geoscience Australia** | SA2 boundaries, geocoding | WFS/WMS services | Registration | Static | FREE |
| **State Data Portals** | Transport projects (NSW/VIC/QLD) | Varies by state | None | Continuous | FREE |

---

## 1️⃣ AUSTRALIAN BUREAU OF STATISTICS (ABS)

### 🎯 What It Provides
- Population estimates & projections
- Household income distributions  
- Age structure & dependency ratios
- Employment sectors & unemployment rates
- Housing tenure (owned, rented, mortgage)
- Household size & composition

### 🔌 API Endpoints

#### Main ABS API Hub
```
https://api.abs.gov.au/
```

#### Census Data API
```
https://api.abs.gov.au/v1/geography/CSA/GeographicAreaList?CSA=3001
https://api.abs.gov.au/v1/data/Census2021/PopulationByAge
https://api.abs.gov.au/v1/data/Census2021/HouseholdIncome
```

#### Education Capital Works API
```
https://api.abs.gov.au/v1/data/EducationCapitalWorks
```

### 📥 Data Download Options
- **REST API**: Programmatic access (recommended)
- **CSV Downloads**: `https://www.abs.gov.au/statistics/`
- **Data Cube**: Multi-dimensional data via web interface

### 🔑 Join Keys
| Key Type | Format | Example | Uses |
|----------|--------|---------|------|
| **SA3** | 6 digits | `300111` | Suburb-level area |
| **SA2** | Variable | `31050-11` | Precise suburb boundary |
| **ABS Name Code** | Alphanumeric | `300111:PopulationEstimates` | Dataset lookup |

### ⚙️ Sample Python Request
```python
import requests
import pandas as pd

# Population by age for an SA3 area
response = requests.get(
    "https://api.abs.gov.au/v1/data/Census2021/PopulationByAge",
    params={"SA3": "300111"}  # Replace with target suburb's SA3
)
data = response.json()
df = pd.DataFrame(data["Series"])
print(df.head())  # Age groups with population counts
```

---

## 2️⃣ INFRASTRUCTURE AUSTRALIA

### 🎯 What It Provides
- Transforming the Nation Agenda projects (10-year pipeline)
- Transport infrastructure upgrades (rail, road, ports)
- Hospital & health facility investments
- School construction & refurbishment
- Government capital works programs

### 🔌 Access Methods

#### Primary: Web Portal (No API, but downloadable data)
```
https://www.infrastructureaustralia.gov.au/our-work/projects
```

#### Secondary: State-Level APIs (Better programmatic access)
```
# Victoria Transport Projects
https://data.vic.gov.au/api/v2.1/catalogue/c9a0f56d-3c8e-4b0f-b7a4-f5c8e2d1a3b4

# NSW Open Data API  
https://api.nswdata.net/transport/projects

# Queensland Transport Data
https://www.data.qld.gov.au/dataset/infrastructure-project-pipeline
```

### 📥 Infrastructure Australia Downloads
- **Annual Reports**: Excel spreadsheets with full project lists
- **Project Catalogs**: CSV exports from web portal
- **Outlook Publications**: 10-year pipeline data (PDF + Excel)

### 🔍 Key Datasets Available

| Dataset | Format | Update | Size |
|---------|--------|--------|------|
| National Priority Projects | Excel/CSV | Annual | ~500 projects |
| State Transport Upgrades | CSV from state portals | Continuous | Varies |
| Health Infrastructure Investment | PDF + Data tables | Quarterly | ~200 projects |
| Education Capital Works | CSV (via ABS) | Annual | ~300 projects |

### ⚙️ Sample Extraction (Python)
```python
import pandas as pd

# Download infrastructure project data
url = "https://www.infrastructureaustralia.gov.au/sites/default/files/projects.xlsx"
projects = pd.read_excel(url)

# Filter for transport in Melbourne area
transport_projects = projects[
    (projects['ProjectType'].str.contains('Transport', na=False)) &
    (projects['StateLocation'] == 'VIC')
]

print(transport_projects[['ProjectName', 'ExpectedCompletion', 'EstimatedCost']].head())
```

---

## 3️⃣ AUSTRALIAN INSTITUTE OF HEALTH AND WELFARE (AIHW)

### 🎯 What It Provides
- Hospital bed counts & occupancy
- Health workforce statistics
- Health infrastructure investment
- Medical equipment and technology data

### 🔌 API Endpoint
```
https://api.data.aihw.gov.au/
```

#### Available Endpoints
```
GET /hospital-data           # Hospital lists with bed counts
GET /bed-stats               # Bed occupancy statistics
GET /health-infrastructure   # Infrastructure projects
```

### 📥 Data Products
- **Hospital Minimum Dataset**: All Australian hospitals
- **Bed Availability Data**: Quarterly updates
- **Health Workforce Statistics**: Annual releases
- **Infrastructure Reports**: Investment tracking

### ⚙️ Sample Python Request
```python
import requests

# Get hospital list with bed counts
response = requests.get(
    "https://api.data.aihw.gov.au/hospital-data",
    params={"state": "VIC"}  # Or NSW, QLD, etc.
)
hospitals = response.json()

for h in hospitals['hospitals'][:5]:
    print(f"{h['name']}: {h['beds']} beds")
```

---

## 4️⃣ GEOSCIENCE AUSTRALIA (SA2 Boundaries)

### 🎯 What It Provides
- SA2 boundary files (GeoJSON, shapefile)
- Administrative area codes (GALAA)
- Place name geocoding services
- Reverse geocoding to administrative areas

### 🔌 API Endpoints

#### WFS/WMS Services
```
# Boundary data via Web Feature Service
https://wfs.geoscience.gov.au/

# Geocoding API
https://gaapi.geoscience.gov.au/geocode
```

#### ABS Geography Integration
```
# SA2 boundary layers (via ABS Geography)
http://data.abs.gov.au/atlas/services/wms
```

### 📥 Boundary Files Available

| Format | Source | License | Download Location |
|--------|--------|---------|-------------------|
| GeoJSON | ABS Geography API | Creative Commons | https://www.abs.gov.au/websitedbs/CATMAVS01/abs.nsf/geography |
| Shapefile | Geoscience Australia | Creative Commons | https://ga.gov.au/data/boundary-files |

### 🔑 Join Key System

```
Suburb → SA3 → SA2
       ↓
  ABSA Code (6-digit)
       ↓
  Matches to SA2 boundary layer
```

### ⚙️ Sample Python - Get Suburb Boundaries
```python
import requests
import json

# Query ABS geography for suburb boundaries
response = requests.get(
    "http://data.abs.gov.au/atlas/services/wms?",
    params={
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYER": "SA2_Levels",
        "TYPENAME": "statistical_divisions:StatisticalDivisionLevel2",
        "BBOX": "-149,65,-140,70",  # Bounding box in decimal degrees
        "QUERY_LAYERS": "SA2_Levels",
        "INFO_FORMAT": "application/json"
    }
)

sa2_data = response.json()
# Parse SA2 codes for suburb-level analysis
```

---

## 🚀 **Recommended Integration Strategy**

### Phase 1: Start with ABS Census (Easiest - No Auth Required)
```python
# Backend API enhancement
@router.get("/suburb/{suburb_name}/abs-data")
async def get_abs_data(suburb_name: str):
    """Get latest ABS census data for suburb"""
    # Convert suburb name to SA3/SA2 code
    sa3_code = await geocode_to_sa3(suburb_name)  # Use Geoscience API
    
    # Fetch population, income, age from ABS API
    response = requests.get(
        f"https://api.abs.gov.au/v1/data/Census2021/{metric}",
        params={"SA3": sa3_code}
    )
    
    return parse_abs_response(response.json())
```

### Phase 2: Add Infrastructure Pipeline (Web Scraping → Structured Data)
```python
# Create scraper for Infrastructure Australia projects
async def fetch_infrastructure_projects():
    """Scrape IA portal for project pipeline data"""
    from bs4 import BeautifulSoup
    
    # Download annual reports (Excel format)
    url = "https://www.infrastructureaustralia.gov.au/annual-reports"
    report = download_excel(url)
    
    # Parse to structured format
    projects = []
    for row in report.to_dict('records'):
        projects.append({
            'name': row['ProjectName'],
            'type': row['ProjectType'],
            'location': row['StateLocation'],
            'expected_completion': row['ExpectedCompletionYear'],
            'estimated_cost': row['EstimatedCostM$']
        })
    
    return projects  # Save to backend database
```

### Phase 3: Add Hospital/School Data (AIHW + ABS Education)
```python
@router.get("/suburb/{suburb_name}/health-education")
async def get_health_education_data(suburb_name: str):
    """Get nearby hospitals and schools with funding data"""
    
    # Get suburb coordinates
    lat, lon = geocode_suburb(suburb_name)
    
    # Find hospitals within 50km (via AIHW API)
    hospitals = get_hospitals_nearby(lat, lon, radius_km=50)
    
    # Get school capital works from ABS Education API
    schools = get_school_capital_works(lat, lon)
    
    return {
        "hospitals": hospitals,
        "schools": schools
    }
```

---

## 📊 **Data Update Schedule**

| Dataset | Source | Update Frequency | Best Use Case |
|---------|--------|------------------|---------------|
| ABS Population/Income | Census 2021 | Every 5 years | Macro indicators (stable) |
| ABS Employment/Housing | Survey data | Annual | Current conditions |
| Infrastructure Pipeline | IA Reports | Annual + updates | Major projects (>$5M) |
| Transport Upgrades | State portals | Continuous | Local transport impact |
| Hospital Beds | AIHW | Quarterly | Healthcare access |
| School Investment | ABS Education | Annual | Education facilities |

---

## 🎯 **Implementation Priority**

### ⭐ **Tier 1: Immediate (No Auth, Free)**
1. ✅ ABS Census data (population, income, demographics)
2. ✅ ABS Education capital works (schools data)

### ⭐⭐ **Tier 2: Short-term (Simple integration)**
3. ⭐ AIHW hospital data (healthcare access metrics)
4. ⭐ Infrastructure Australia projects (web scraping → structured)

### ⭐⭐⭐ **Tier 3: Medium-term (Requires setup)**
5. ⭐ State transport APIs (NSW/VIC/QLD specific data)
6. ⭐ Geoscience Australia geocoding (SA2 boundaries)

---

## 🔧 **Migration Path from Static Data**

### Current State (Static Seeds):
```python
# backend/app/db/init_db.py currently uses hard-coded sample suburbs
seed_suburbs = [
    {'name': 'South Yarra', 'state': 'VIC', 'score': 87, ...},
]
```

### New Architecture (Real API Data):
```python
# backend/app/db/init_db.py - Enhanced
async def seed_real_time_data():
    """Populate database with real government data"""
    
    # Get suburb locations from ABR or Geoscience
    suburbs = await get_suburbs_from_geoapi()
    
    for suburb in suburbs:
        # 1. ABS Census Data (Population, income, age)
        census_data = await abs_api.get_census(suburb.absa_code)
        
        # 2. Infrastructure Projects
        infra_projects = await infrastructure_api.get_projects(
            state=suburb.state,
            location_radius=50km
        )
        
        # 3. Nearby Hospitals (AIHW)
        hospital_data = await aiwh_api.get_hospitals_nearby(suburb.latlon)
        
        # 4. School Capital Works
        school_data = await abs_education_api.get_capital_works(
            state=suburb.state,
            radius=50km
        )
        
        # Calculate suburb score from real data
        suburb.score = calculate_investment_score(
            population=census_data.population,
            income_growth=calculate_income_growth(census_data),
            infrastructure_pipelines=infra_projects,
            healthcare_access=len(hospital_data),
            education_quality=school_data.avg_rating
        )
        
        # Save to database
        await db.save_suburb(suburb)
```

---

## 📝 **Next Steps**

1. ✅ Create backend API endpoints for ABS data queries
2. ✅ Set up infrastructure project scraper → structured storage  
3. ✅ Integrate AIHW hospital data
4. ✅ Add SA2 boundary lookup (Geoscience Australia API)
5. ✅ Implement real-time score calculation from live data
6. ✅ Remove static seeds from database

---

**All sources are FREE for non-commercial use!** 🎉
