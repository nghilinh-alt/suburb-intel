"""Rule-based parser for the plain-English suburb search.

Scope: this is the lightweight first cut — it only fills in filter fields
backed by data we actually have today (state, distance_to_cbd_km from
`app.core.geo`, population, median_income, investment_score). Bedroom/price/
property-type filters need PropRadar sold-listing data (a separate,
API-key-gated ingestion source) and are intentionally not modeled here yet.

No LLM call — regex + a static city→state lookup is enough for the patterns
this search box is expected to see ("Brisbane suburbs within 10km of CBD",
"top 5 highest income suburbs in Sydney", etc).
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Capital city name -> state code. Suburb-level "city" isn't a concept in the
# SA2 schema (only `state` is), so a recognised city name maps straight to
# its state.
_CITY_TO_STATE: dict[str, str] = {
    "sydney": "NSW",
    "melbourne": "VIC",
    "brisbane": "QLD",
    "perth": "WA",
    "adelaide": "SA",
    "hobart": "TAS",
    "canberra": "ACT",
    "darwin": "NT",
}

_STATE_CODE_RE = re.compile(r"\b(NSW|VIC|QLD|WA|SA|TAS|ACT|NT)\b", re.IGNORECASE)
_DISTANCE_RE = re.compile(r"within\s+(\d+(?:\.\d+)?)\s*km", re.IGNORECASE)
_TOP_N_RE = re.compile(r"top\s+(\d+)", re.IGNORECASE)
_CLOSEST_TO_CBD_RE = re.compile(r"closest\s+to\s+(?:the\s+)?cbd", re.IGNORECASE)
_HIGHEST_INCOME_RE = re.compile(r"highest\s+income|richest|wealthiest", re.IGNORECASE)
_MOST_POPULOUS_RE = re.compile(r"most\s+populous|largest\s+population|biggest\s+population", re.IGNORECASE)
_BEST_INVESTMENT_RE = re.compile(r"best\s+investment|highest\s+investment\s+score|top\s+investment", re.IGNORECASE)

SortBy = Literal["distance_to_cbd", "investment_score", "population", "median_income"]


class SuburbSearchFilter(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    max_distance_to_cbd_km: Optional[float] = None
    sort_by: SortBy = "population"
    sort_dir: Literal["asc", "desc"] = "desc"
    limit: int = Field(10, ge=1, le=50)


def parse_with_rules(prompt: str) -> SuburbSearchFilter:
    """Regex/lookup-based parse of a plain-English suburb search prompt."""
    city: Optional[str] = None
    state: Optional[str] = None

    for name, code in _CITY_TO_STATE.items():
        if re.search(rf"\b{name}\b", prompt, re.IGNORECASE):
            city = name.capitalize()
            state = code
            break

    if state is None:
        state_match = _STATE_CODE_RE.search(prompt)
        if state_match:
            state = state_match.group(1).upper()

    max_distance_to_cbd_km: Optional[float] = None
    distance_match = _DISTANCE_RE.search(prompt)
    if distance_match:
        max_distance_to_cbd_km = float(distance_match.group(1))

    limit = 10
    top_n_match = _TOP_N_RE.search(prompt)
    if top_n_match:
        limit = min(int(top_n_match.group(1)), 50)

    sort_by: SortBy = "population"
    sort_dir: Literal["asc", "desc"] = "desc"

    if _CLOSEST_TO_CBD_RE.search(prompt) or max_distance_to_cbd_km is not None:
        sort_by, sort_dir = "distance_to_cbd", "asc"
    elif _HIGHEST_INCOME_RE.search(prompt):
        sort_by, sort_dir = "median_income", "desc"
    elif _MOST_POPULOUS_RE.search(prompt):
        sort_by, sort_dir = "population", "desc"
    elif _BEST_INVESTMENT_RE.search(prompt):
        sort_by, sort_dir = "investment_score", "desc"

    return SuburbSearchFilter(
        city=city,
        state=state,
        max_distance_to_cbd_km=max_distance_to_cbd_km,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
    )
