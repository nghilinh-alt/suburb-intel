"""PropRadar suburb market data loader — on-demand with 30-day cache.

Fetches suburb-level market data (median prices, yields, growth, days on market,
vacancy rate, heat score) from PropRadar API on first request for a suburb,
then caches for 30 days.

API: GET https://api.propradar.com.au/v1/suburbs/{state}/{suburb}
Key: PROPRADAR_API_KEY in backend/.env
Free tier: 100 calls/month. $39/month Hobby = 5,000 calls (covers full AU batch).

Suburb/state are derived directly from the suburb_id slug:
  'algester-qld'         → state='qld', suburb='algester'
  'camp-hill-qld'        → state='qld', suburb='camp-hill'
  'north-parramatta-nsw' → state='nsw', suburb='north-parramatta'
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

_FSQ_BASE    = "https://api.propradar.com.au/v1"
_CACHE_DAYS  = 30


def _suburb_and_state(suburb_id: str) -> tuple[str, str]:
    """Extract suburb slug and state code from suburb_id.
    'algester-qld'         → ('algester', 'qld')
    'north-parramatta-nsw' → ('north-parramatta', 'nsw')
    """
    parts = suburb_id.rsplit("-", 1)
    if len(parts) != 2:
        raise ValueError(f"Cannot parse suburb_id: {suburb_id}")
    return parts[0], parts[1]


def _parse_response(suburb_id: str, data: dict) -> dict:
    """Extract flat fields from PropRadar JSON response."""
    m  = data.get("medians", {})
    g  = data.get("growth", {})
    gh = g.get("house", {})
    gu = g.get("unit", {})
    y  = data.get("yields", {})
    md = data.get("market_dynamics", {})

    return {
        "suburb_id":              suburb_id,
        "house_median_price":     m.get("house_price"),
        "unit_median_price":      m.get("unit_price"),
        "house_weekly_rent":      m.get("house_weekly_rent"),
        "unit_weekly_rent":       m.get("unit_weekly_rent"),
        "house_gross_yield_pct":  y.get("house_gross_pct"),
        "unit_gross_yield_pct":   y.get("unit_gross_pct"),
        "house_1y_growth_pct":    _f(gh.get("1y_pct")),
        "unit_1y_growth_pct":     _f(gu.get("1y_pct")),
        "house_3y_growth_pct":    _f(gh.get("3y_pct")),
        "unit_3y_growth_pct":     _f(gu.get("3y_pct")),
        "house_5y_growth_pct":    _f(gh.get("5y_pct")),
        "unit_5y_growth_pct":     _f(gu.get("5y_pct")),
        "house_growth_confidence": gh.get("confidence"),
        "house_days_on_market":   md.get("house_days_on_market"),
        "unit_days_on_market":    md.get("unit_days_on_market"),
        "vacancy_rate_pct":       _f(md.get("vacancy_rate_pct")),
        "house_sales_12mo":       md.get("house_sales_12mo"),
        "unit_sales_12mo":        md.get("unit_sales_12mo"),
        "house_heat_score":       _f(md.get("house_heat_score")),
        "sold_vs_asking_pct":     _f(md.get("sold_vs_asking_pct")),
        "as_of":                  data.get("as_of"),
    }


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_or_fetch(suburb_id: str, api_key: str, db) -> dict | None:
    """Return PropRadar market data for a suburb, fetching if not cached or stale."""
    from app.db.models import PropRadarSuburbCache, Base
    from app.db.session import sync_engine
    Base.metadata.create_all(bind=sync_engine)

    if not api_key:
        return None

    cutoff   = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=_CACHE_DAYS)
    existing = db.get(PropRadarSuburbCache, suburb_id)

    if existing and existing.fetched_at and existing.fetched_at >= cutoff:
        return _row_to_dict(existing)

    # Fetch fresh from PropRadar
    try:
        suburb, state = _suburb_and_state(suburb_id)
    except ValueError as e:
        logger.warning("PropRadar: %s", e)
        return None

    import requests
    url = f"{_FSQ_BASE}/suburbs/{state}/{suburb}"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=12)
        if resp.status_code == 404:
            logger.info("PropRadar: suburb not found — %s/%s", state, suburb)
            return None
        if resp.status_code == 401:
            raise ValueError("Invalid PropRadar API key — check PROPRADAR_API_KEY in .env")
        if resp.status_code == 429:
            logger.warning("PropRadar rate limit hit for %s", suburb_id)
            return _row_to_dict(existing) if existing else None
        resp.raise_for_status()
        data = resp.json()
    except ValueError:
        raise
    except Exception as exc:
        logger.warning("PropRadar fetch failed for %s: %s", suburb_id, exc)
        return _row_to_dict(existing) if existing else None

    fields = _parse_response(suburb_id, data)
    now    = datetime.now(timezone.utc).replace(tzinfo=None)

    if existing:
        for k, v in fields.items():
            if k != "suburb_id":
                setattr(existing, k, v)
        existing.fetched_at = now
    else:
        db.add(PropRadarSuburbCache(**fields, fetched_at=now))

    db.commit()
    logger.info("PropRadar: cached %s — house $%s, yield %.1f%%",
                suburb_id,
                f"{fields.get('house_median_price'):,}" if fields.get("house_median_price") else "n/a",
                fields.get("house_gross_yield_pct") or 0)
    return fields


def _row_to_dict(row: "PropRadarSuburbCache | None") -> dict | None:
    if row is None:
        return None
    return {
        "suburb_id":              row.suburb_id,
        "house_median_price":     row.house_median_price,
        "unit_median_price":      row.unit_median_price,
        "house_weekly_rent":      row.house_weekly_rent,
        "unit_weekly_rent":       row.unit_weekly_rent,
        "house_gross_yield_pct":  row.house_gross_yield_pct,
        "unit_gross_yield_pct":   row.unit_gross_yield_pct,
        "house_1y_growth_pct":    row.house_1y_growth_pct,
        "unit_1y_growth_pct":     row.unit_1y_growth_pct,
        "house_3y_growth_pct":    row.house_3y_growth_pct,
        "unit_3y_growth_pct":     row.unit_3y_growth_pct,
        "house_5y_growth_pct":    row.house_5y_growth_pct,
        "unit_5y_growth_pct":     row.unit_5y_growth_pct,
        "house_growth_confidence": row.house_growth_confidence,
        "house_days_on_market":   row.house_days_on_market,
        "unit_days_on_market":    row.unit_days_on_market,
        "vacancy_rate_pct":       row.vacancy_rate_pct,
        "house_sales_12mo":       row.house_sales_12mo,
        "unit_sales_12mo":        row.unit_sales_12mo,
        "house_heat_score":       row.house_heat_score,
        "sold_vs_asking_pct":     row.sold_vs_asking_pct,
        "as_of":                  row.as_of,
    }
