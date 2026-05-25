"""Australian government free data sources (ABS Census 2021, AIHW, etc.).

All endpoints below are free and require no API key.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class AustralianDataSources:
    """Centralized client for the free Australian government data APIs."""

    CENSUS_DATA_API = "https://api.abs.gov.au/v1/data/Census2021"

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (compatible; SuburbIntel/1.0)"}
        )

    # ------------------------------------------------------------------
    # ABS Census endpoints
    # ------------------------------------------------------------------
    def get_population_by_age(self, sa3_code: str) -> Dict[str, Any]:
        return self._fetch_metric(
            f"{self.CENSUS_DATA_API}/PopulationByAge",
            {"SA3": sa3_code, "TABLE_STRUCTURE": "flat"},
            keep_when=("Population", "Count"),
            log_label="Population",
            sa_code=sa3_code,
        )

    def get_household_income(self, sa3_code: str) -> Dict[str, Any]:
        return self._fetch_metric(
            f"{self.CENSUS_DATA_API}/MedianHouseholdIncome",
            {"SA3": sa3_code, "TABLE_STRUCTURE": "flat"},
            keep_when=("Median", "Household Income"),
            log_label="Income",
            sa_code=sa3_code,
        )

    def get_housing_tenure(self, sa3_code: str) -> Dict[str, Any]:
        return self._fetch_metric(
            f"{self.CENSUS_DATA_API}/HousingTenure",
            {"SA3": sa3_code, "TABLE_STRUCTURE": "flat"},
            keep_when=None,
            log_label="Housing",
            sa_code=sa3_code,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _fetch_metric(
        self,
        url: str,
        params: Dict[str, str],
        *,
        keep_when: Optional[tuple[str, ...]],
        log_label: str,
        sa_code: str,
    ) -> Dict[str, Any]:
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            output: Dict[str, int] = {}
            for series in data.get("Series", []):
                metric_name = series.get("metricName", "")
                if keep_when and not any(token in metric_name for token in keep_when):
                    continue
                for value in series.get("values", []):
                    label = str(value.get("label", "")).strip()
                    try:
                        output[label] = int(value.get("value", 0))
                    except (TypeError, ValueError):
                        continue
            return {"success": True, "data": output}
        except Exception as e:  # noqa: BLE001 - external API failure surface
            logger.warning("ABS %s API error for %s: %s", log_label, sa_code, e)
            return {"success": False, "error": str(e)}


__all__ = ["AustralianDataSources"]
