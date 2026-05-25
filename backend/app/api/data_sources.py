"""
Free Australian Government Data Sources Integration Service

Connects to official FREE APIs:
- ABS Census & Education data  
- AIHW hospital/health data
- Geoscience Australia geocoding

All sources are free for non-commercial use.
No API keys required!
"""

import requests
from typing import Dict, List, Optional


class AustralianDataSources:
    """Centralized interface to all free Australian government data APIs."""
    
    # === ABS (Australian Bureau of Statistics) URLs ===
    CENSUS_DATA_API = "https://api.abs.gov.au/v1/data/Census2021"
    
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; SuburbIntel/1.0)',
        })
    
    # ==========================================
    # ABS CENSUS DATA - Population, Income, Age
    # ==========================================
    
    def get_population_by_age(self, sa3_code: str) -> Dict:
        """Get age distribution for an SA3 area from ABS Census 2021."""
        url = f"{self.CENSUS_DATA_API}/PopulationByAge"
        params = {
            "SA3": sa3_code,
            "TABLE_STRUCTURE": "flat"
        }
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            population_by_age = {}
            for series in data.get("Series", []):
                metric_name = series.get("metricName", "")
                values = series.get("values", [])
                for value in values:
                    if "Population" in metric_name or "Count" in metric_name:
                        age_group = value["label"]
                        population = int(value["value"])
                        population_by_age[age_group] = population
            
            return {"success": True, "data": population_by_age}
        except Exception as e:
            print(f"ABS Population API error for SA3 {sa3_code}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_household_income(self, sa3_code: str) -> Dict:
        """Get median household income for an SA3 area."""
        url = f"{self.CENSUS_DATA_API}/MedianHouseholdIncome"
        params = {
            "SA3": sa3_code,
            "TABLE_STRUCTURE": "flat"
        }
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            income_data = {}
            for series in data.get("Series", []):
                metric_name = series.get("metricName", "")
                values = series.get("values", [])
                for value in values:
                    if "Median" in metric_name or "Household Income" in metric_name:
                        income_data[value["label"]] = int(value["value"])
            
            return {"success": True, "data": income_data}
        except Exception as e:
            print(f"ABS Income API error for SA3 {sa3_code}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_housing_tenure(self, sa3_code: str) -> Dict:
        """Get housing tenure split (owned/rented/mortgage)."""
        url = f"{self.CENSUS_DATA_API}/HousingTenure"
        params = {
            "SA3": sa3_code,
            "TABLE_STRUCTURE": "flat"
        }
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            tenure_data = {}
            for series in data.get("Series", []):
                metric_name = series.get("metricName", "")
                values = series.get("values", [])
                for value in values:
                    label = value["label"].replace(" ", "")
                    count = int(value["value"])
                    tenure_data[label] = count
            
            return {"success": True, "data": tenure_data}
        except Exception as e:
            print(f"ABS Housing API error for SA3 {sa3_code}: {e}")
            return {"success": False, "error": str(e)}


__all__ = ["AustralianDataSources"]
