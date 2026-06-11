"""Data quality audit — self-investigation & repair system (CLI tool).

Traces suburb scores to their raw source inputs, cross-checks plausibility,
and flags data issues. Run after any ingestion step to surface problems before
they affect scores.

Usage:
    cd backend
    python -m app.jobs.audit_data                     # full report
    python -m app.jobs.audit_data --state QLD         # one state
    python -m app.jobs.audit_data --suburb algester-qld  # one suburb
    python -m app.jobs.audit_data --fix-zeros         # list SA2s to re-ingest
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path

# Force UTF-8 stdout so box-drawing chars and emoji work on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from textwrap import indent

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Plausibility checks — each returns list of (sa2_code, sa2_name, state, detail)
# ─────────────────────────────────────────────────────────────────────────────

def _check_missing_census(db: Session, state_filter: str | None) -> list[dict]:
    """SA2s in sa2_regions that have no row in abs_census_metrics (year=2021)."""
    q = """
        SELECT r.sa2_code, r.sa2_name, r.state
        FROM sa2_regions r
        LEFT JOIN abs_census_metrics m ON m.sa2_code = r.sa2_code AND m.year = 2021
        WHERE m.sa2_code IS NULL
          AND r.sa2_name NOT LIKE '%Migratory%'
          AND r.sa2_name NOT LIKE '%No usual address%'
    """
    params: dict = {}
    if state_filter:
        q += " AND r.state = :state"
        params["state"] = state_filter
    q += " ORDER BY r.state, r.sa2_name"
    rows = db.execute(text(q), params).fetchall()
    return [{"sa2_code": r[0], "sa2_name": r[1], "state": r[2],
             "issue": "No census data loaded (abs_census_metrics missing)"}
            for r in rows]


def _check_zero_biz(db: Session, state_filter: str | None, pop_threshold: int = 5000) -> list[dict]:
    """Suburbs with population > threshold but zero ABS business register counts.

    biz_food_services=0 in a populous suburb almost certainly means the ABS
    Business Register loader didn't populate this SA2.
    """
    q = """
        SELECT r.sa2_code, r.sa2_name, r.state,
               m.population, m.biz_food_services, m.biz_total
        FROM abs_census_metrics m
        JOIN sa2_regions r ON r.sa2_code = m.sa2_code
        WHERE m.year = 2021
          AND m.population > :pop
          AND (m.biz_food_services IS NULL OR m.biz_food_services = 0)
          AND (m.biz_total IS NULL OR m.biz_total < 10)
          AND r.sa2_name NOT LIKE '%Migratory%'
          AND r.sa2_name NOT LIKE '%No usual address%'
          AND r.sa2_name NOT LIKE '%Industrial%'
          AND r.sa2_name NOT LIKE '%Airport%'
    """
    params: dict = {"pop": pop_threshold}
    if state_filter:
        q += " AND r.state = :state"
        params["state"] = state_filter
    q += " ORDER BY m.population DESC"
    rows = db.execute(text(q), params).fetchall()
    return [{"sa2_code": r[0], "sa2_name": r[1], "state": r[2],
             "population": r[3],
             "issue": f"biz_food_services={r[4] or 0}, biz_total={r[5] or 0} — ABS business data likely missing"}
            for r in rows]


def _check_zero_transit(db: Session, state_filter: str | None, pop_threshold: int = 3000) -> list[dict]:
    """Populous suburbs with absolutely no PT stops in any mode (likely GTFS gap)."""
    q = """
        SELECT r.sa2_code, r.sa2_name, r.state, m.population
        FROM abs_census_metrics m
        JOIN sa2_regions r ON r.sa2_code = m.sa2_code
        WHERE m.year = 2021
          AND m.population > :pop
          AND (m.pt_stop_train IS NULL OR m.pt_stop_train = 0)
          AND (m.pt_stop_tram  IS NULL OR m.pt_stop_tram  = 0)
          AND (m.pt_stop_bus   IS NULL OR m.pt_stop_bus   = 0)
          AND (m.pt_stop_ferry IS NULL OR m.pt_stop_ferry = 0)
          AND r.sa2_name NOT LIKE '%Migratory%'
          AND r.sa2_name NOT LIKE '%No usual address%'
    """
    params: dict = {"pop": pop_threshold}
    if state_filter:
        q += " AND r.state = :state"
        params["state"] = state_filter
    q += " ORDER BY m.population DESC LIMIT 50"
    rows = db.execute(text(q), params).fetchall()
    return [{"sa2_code": r[0], "sa2_name": r[1], "state": r[2],
             "population": r[3],
             "issue": "Zero PT stops in all modes — GTFS data may not cover this area"}
            for r in rows]


def _check_no_schools(db: Session, state_filter: str | None, pop_threshold: int = 2000) -> list[dict]:
    """Populous suburbs with no school links — likely a geo-matching gap."""
    q = """
        SELECT r.sa2_code, r.sa2_name, r.state, m.population
        FROM abs_census_metrics m
        JOIN sa2_regions r ON r.sa2_code = m.sa2_code
        LEFT JOIN sa2_school_link sl ON sl.sa2_code = r.sa2_code
        WHERE m.year = 2021
          AND m.population > :pop
          AND sl.sa2_code IS NULL
          AND r.sa2_name NOT LIKE '%Migratory%'
          AND r.sa2_name NOT LIKE '%No usual address%'
          AND r.sa2_name NOT LIKE '%Industrial%'
    """
    params: dict = {"pop": pop_threshold}
    if state_filter:
        q += " AND r.state = :state"
        params["state"] = state_filter
    q += " ORDER BY m.population DESC LIMIT 30"
    rows = db.execute(text(q), params).fetchall()
    return [{"sa2_code": r[0], "sa2_name": r[1], "state": r[2],
             "population": r[3],
             "issue": "No school links — school geo-match missed this SA2"}
            for r in rows]


def _check_missing_seifa(db: Session, state_filter: str | None) -> list[dict]:
    """SA2s with census data but no SEIFA decile (score will use 50th-pct fallback)."""
    q = """
        SELECT r.sa2_code, r.sa2_name, r.state, m.population
        FROM abs_census_metrics m
        JOIN sa2_regions r ON r.sa2_code = m.sa2_code
        WHERE m.year = 2021
          AND m.seifa_irsad_decile IS NULL
          AND m.population IS NOT NULL
          AND r.sa2_name NOT LIKE '%Migratory%'
          AND r.sa2_name NOT LIKE '%No usual address%'
    """
    params: dict = {}
    if state_filter:
        q += " AND r.state = :state"
        params["state"] = state_filter
    q += " ORDER BY m.population DESC LIMIT 20"
    rows = db.execute(text(q), params).fetchall()
    return [{"sa2_code": r[0], "sa2_name": r[1], "state": r[2],
             "population": r[3],
             "issue": "No SEIFA decile — demographic/housing scores use fallback (50th pct)"}
            for r in rows]


def _check_score_outliers(db: Session, state_filter: str | None) -> list[dict]:
    """SA2s where a dimension score is suspiciously perfect (10.0) or floor (0.0),
    which usually indicates a data anomaly rather than genuine extremity."""
    q = """
        SELECT r.sa2_code, r.sa2_name, r.state, m.population,
               s.liveability_score, s.growth_score, s.education_score,
               s.demographic_score, s.housing_score, s.infrastructure_score
        FROM suburb_scores s
        JOIN sa2_regions r ON r.sa2_code = s.sa2_code
        JOIN abs_census_metrics m ON m.sa2_code = s.sa2_code AND m.year = 2021
        WHERE (s.liveability_score >= 9.8 OR s.liveability_score <= 0.5
            OR s.growth_score      >= 9.8 OR s.growth_score      <= 0.5
            OR s.education_score   >= 9.8 OR s.education_score   <= 0.5
            OR s.housing_score     >= 9.8 OR s.housing_score     <= 0.5)
          AND m.population > 500
          AND r.sa2_name NOT LIKE '%Migratory%'
          AND r.sa2_name NOT LIKE '%No usual address%'
    """
    params: dict = {}
    if state_filter:
        q += " AND r.state = :state"
        params["state"] = state_filter
    q += " ORDER BY r.state, r.sa2_name"
    rows = db.execute(text(q), params).fetchall()
    issues = []
    for r in rows:
        dims = {
            "liveability": r[4], "growth": r[5], "education": r[6],
            "demographic": r[7], "housing": r[8], "infrastructure": r[9],
        }
        flagged = [f"{d}={v:.2f}" for d, v in dims.items() if v is not None and (v >= 9.8 or v <= 0.5)]
        if flagged:
            issues.append({"sa2_code": r[0], "sa2_name": r[1], "state": r[2],
                           "population": r[3], "issue": "Extreme score: " + ", ".join(flagged)})
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Coverage summary
# ─────────────────────────────────────────────────────────────────────────────

def _coverage_summary(db: Session) -> dict:
    """High-level data coverage stats across the whole DB."""
    r = db.execute(text("""
        SELECT
          COUNT(DISTINCT r.sa2_code) total_sa2,
          COUNT(DISTINCT m.sa2_code) has_census,
          COUNT(DISTINCT CASE WHEN m.biz_food_services > 0 THEN m.sa2_code END) has_biz,
          COUNT(DISTINCT CASE WHEN m.pt_stop_bus > 0 OR m.pt_stop_train > 0 THEN m.sa2_code END) has_transit,
          COUNT(DISTINCT sl.sa2_code) has_schools,
          COUNT(DISTINCT hl.sa2_code) has_health,
          COUNT(DISTINCT il.sa2_code) has_infra,
          COUNT(DISTINCT ss.sa2_code) has_scores
        FROM sa2_regions r
        LEFT JOIN abs_census_metrics m  ON m.sa2_code = r.sa2_code AND m.year = 2021
        LEFT JOIN sa2_school_link sl    ON sl.sa2_code = r.sa2_code
        LEFT JOIN sa2_health_link hl    ON hl.sa2_code = r.sa2_code
        LEFT JOIN sa2_project_link il   ON il.sa2_code = r.sa2_code
        LEFT JOIN suburb_scores ss      ON ss.sa2_code = r.sa2_code
        WHERE r.sa2_name NOT LIKE '%Migratory%'
          AND r.sa2_name NOT LIKE '%No usual address%'
    """)).fetchone()

    return {
        "total_sa2":    r[0],
        "has_census":   (r[1], r[1] / r[0] * 100),
        "has_biz":      (r[2], r[2] / r[0] * 100),
        "has_transit":  (r[3], r[3] / r[0] * 100),
        "has_schools":  (r[4], r[4] / r[0] * 100),
        "has_health":   (r[5], r[5] / r[0] * 100),
        "has_infra":    (r[6], r[6] / r[0] * 100),
        "has_scores":   (r[7], r[7] / r[0] * 100),
    }


def _state_score_summary(db: Session) -> list[dict]:
    """Per-state average scores and coverage."""
    rows = db.execute(text("""
        SELECT r.state,
               COUNT(DISTINCT r.sa2_code) sa2_count,
               ROUND(AVG(s.investment_score), 2)  avg_inv,
               ROUND(AVG(s.liveability_score), 2) avg_live,
               ROUND(AVG(s.growth_score), 2)      avg_grow,
               ROUND(AVG(s.education_score), 2)   avg_edu,
               ROUND(MIN(s.investment_score), 2)  min_inv,
               ROUND(MAX(s.investment_score), 2)  max_inv
        FROM sa2_regions r
        LEFT JOIN suburb_scores s ON s.sa2_code = r.sa2_code
        WHERE r.sa2_name NOT LIKE '%Migratory%'
          AND r.sa2_name NOT LIKE '%No usual address%'
          AND r.state NOT IN ('OT')
        GROUP BY r.state
        ORDER BY avg_inv DESC NULLS LAST
    """)).fetchall()
    return [dict(r._mapping) for r in rows]


def _single_suburb_trace(db: Session, suburb_id: str) -> dict | None:
    """Deep trace for one suburb: raw inputs → scores → what drove each dimension."""
    # Resolve suburb_id to SA2 codes via suburb_aggregates
    agg = db.execute(text(
        "SELECT sa2_codes, suburb_name, state FROM suburb_aggregates WHERE suburb_id = :sid"
    ), {"sid": suburb_id}).fetchone()
    if not agg:
        return None

    import json
    sa2_codes = json.loads(agg[0]) if isinstance(agg[0], str) else (agg[0] or [])
    suburb_name, state = agg[1], agg[2]

    results = []
    for code in sa2_codes:
        row = db.execute(text("""
            SELECT
                r.sa2_name,
                -- Census
                m.population, m.median_income, m.unemployment_pct,
                m.uni_degree_pct, m.professionals_managers_pct,
                m.high_mortgage_stress_pct, m.high_rent_stress_pct,
                m.renters_pct, m.median_rent_weekly,
                m.families_with_children_pct, m.social_housing_pct,
                -- PT
                m.pt_stop_train, m.pt_stop_tram, m.pt_stop_bus, m.pt_stop_ferry,
                -- Business
                m.biz_food_services, m.biz_health_social, m.biz_arts_recreation,
                m.biz_retail_trade, m.biz_construction, m.biz_total,
                -- Building & pop projections
                m.building_approvals_1yr, m.pop_growth_proj_pct,
                -- SEIFA
                m.seifa_irsad_decile, m.seifa_ieo_decile,
                -- Overture
                m.osm_parks, m.osm_cafes, m.osm_restaurants,
                -- Scores
                s.investment_score, s.liveability_score, s.education_score,
                s.growth_score, s.demographic_score, s.housing_score,
                s.infrastructure_score, s.gentrification_index,
                s.transit_score_raw, s.edu_avg_icsea, s.edu_top_school_count,
                s.health_hospital_score, s.infra_committed_aud, s.infra_project_count,
                s.risk_flags, s.score_version
            FROM sa2_regions r
            JOIN abs_census_metrics m ON m.sa2_code = r.sa2_code AND m.year = 2021
            LEFT JOIN suburb_scores s ON s.sa2_code = r.sa2_code
            WHERE r.sa2_code = :code
        """), {"code": code}).fetchone()
        if row:
            results.append(dict(row._mapping))

    return {
        "suburb_id":   suburb_id,
        "suburb_name": suburb_name,
        "state":       state,
        "sa2_codes":   sa2_codes,
        "sa2_data":    results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report formatting
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_issues(issues: list[dict], label: str, limit: int = 15) -> str:
    if not issues:
        return f"  ✅ {label}: none\n"
    lines = [f"  ⚠️  {label}: {len(issues)} issue(s)"]
    for item in issues[:limit]:
        pop = f"  pop={item.get('population', '?'):,}" if item.get('population') else ""
        lines.append(f"     • {item['sa2_name']} ({item['state']}){pop} — {item['issue']}")
    if len(issues) > limit:
        lines.append(f"     … and {len(issues) - limit} more")
    return "\n".join(lines) + "\n"


def _fmt_trace(trace: dict) -> str:
    lines = [f"\n{'═'*70}"]
    lines.append(f"  SUBURB TRACE: {trace['suburb_name']} {trace['state']}")
    lines.append(f"  suburb_id: {trace['suburb_id']}")
    lines.append(f"{'═'*70}\n")

    for sa2 in trace["sa2_data"]:
        lines.append(f"  SA2: {sa2['sa2_name']}")
        lines.append(f"  {'─'*50}")

        # Scores
        lines.append(f"\n  SCORES (v{sa2.get('score_version', '?')})")
        scores = [
            ("Investment",    sa2.get("investment_score")),
            ("Liveability",   sa2.get("liveability_score")),
            ("Growth",        sa2.get("growth_score")),
            ("Education",     sa2.get("education_score")),
            ("Demographics",  sa2.get("demographic_score")),
            ("Housing",       sa2.get("housing_score")),
            ("Infrastructure",sa2.get("infrastructure_score")),
            ("Gentrification",sa2.get("gentrification_index")),
        ]
        for name, v in scores:
            bar = "█" * int((v or 0) * 3) + "░" * (30 - int((v or 0) * 3))
            lines.append(f"    {name:<16} {f'{v:.2f}' if v is not None else 'null':>5}  {bar}")

        # Raw inputs
        lines.append(f"\n  RAW INPUTS")
        lines.append(f"    Population:          {sa2.get('population', 'null'):>8,}" if sa2.get('population') else "    Population:               null")
        lines.append(f"    Median income:     ${sa2.get('median_income', 0) or 0:>8,.0f}/yr")
        lines.append(f"    Unemployment:        {(sa2.get('unemployment_pct') or 0):>7.1f}%")
        lines.append(f"    Uni degree:          {(sa2.get('uni_degree_pct') or 0):>7.1f}%")
        lines.append(f"    Professionals:       {(sa2.get('professionals_managers_pct') or 0):>7.1f}%")
        lines.append(f"    Mortgage stress:     {(sa2.get('high_mortgage_stress_pct') or 0):>7.1f}%")
        lines.append(f"    Rent stress:         {(sa2.get('high_rent_stress_pct') or 0):>7.1f}%")
        lines.append(f"    Renters:             {(sa2.get('renters_pct') or 0):>7.1f}%")
        lines.append(f"    Median rent:         ${sa2.get('median_rent_weekly') or 0:>6.0f}/wk")
        lines.append(f"    SEIFA IRSAD:         {sa2.get('seifa_irsad_decile', 'null')!r:>6} (decile)")
        lines.append(f"    Pop growth proj:     {(sa2.get('pop_growth_proj_pct') or 0):>7.1f}%")
        lines.append(f"    Building approvals:  {sa2.get('building_approvals_1yr') or 0:>6} (1yr)")

        lines.append(f"\n  TRANSIT (weighted score: {sa2.get('transit_score_raw', 0) or 0:.0f})")
        lines.append(f"    Train stops: {sa2.get('pt_stop_train') or 0}  Tram: {sa2.get('pt_stop_tram') or 0}  Bus: {sa2.get('pt_stop_bus') or 0}  Ferry: {sa2.get('pt_stop_ferry') or 0}")

        lines.append(f"\n  AMENITY (ABS Business Register)")
        lines.append(f"    Food & beverage:  {sa2.get('biz_food_services') or 0:>5}   Health & social: {sa2.get('biz_health_social') or 0}")
        lines.append(f"    Arts & rec:       {sa2.get('biz_arts_recreation') or 0:>5}   Retail:          {sa2.get('biz_retail_trade') or 0}")
        lines.append(f"    Construction:     {sa2.get('biz_construction') or 0:>5}   Total biz:       {sa2.get('biz_total') or 0}")

        lines.append(f"\n  EDUCATION  avg ICSEA: {sa2.get('edu_avg_icsea') or 'null'}  top schools (ICSEA≥1100): {sa2.get('edu_top_school_count') or 0}")
        lines.append(f"  HEALTH     hospital score: {sa2.get('health_hospital_score') or 0:.1f}")
        lines.append(f"  INFRA      ${(sa2.get('infra_committed_aud') or 0)/1e6:.1f}M committed  {sa2.get('infra_project_count') or 0} projects")

        rf = sa2.get("risk_flags") or "[]"
        lines.append(f"\n  RISK FLAGS {rf}")
        lines.append("")

    return "\n".join(lines)


def run_audit(
    db: Session,
    *,
    state_filter: str | None = None,
    suburb_id: str | None = None,
    verbose: bool = False,
) -> str:
    """Run the full audit and return a formatted report string."""

    if suburb_id:
        trace = _single_suburb_trace(db, suburb_id)
        if not trace:
            return f"❌ Suburb '{suburb_id}' not found in suburb_aggregates."
        return _fmt_trace(trace)

    lines = ["\n" + "═" * 70]
    lines.append("  SUBURB INTEL — DATA QUALITY AUDIT")
    if state_filter:
        lines.append(f"  State filter: {state_filter}")
    lines.append("═" * 70 + "\n")

    # ── Coverage summary ──────────────────────────────────────────────────
    cov = _coverage_summary(db)
    total = cov["total_sa2"]
    lines.append("COVERAGE SUMMARY")
    lines.append(f"  Total SA2s (excl phantoms):  {total:>5}")
    for label, (count, pct) in [
        ("Census data loaded",       cov["has_census"]),
        ("ABS biz register data",    cov["has_biz"]),
        ("GTFS transit data",        cov["has_transit"]),
        ("School links",             cov["has_schools"]),
        ("Health facility links",    cov["has_health"]),
        ("Infrastructure links",     cov["has_infra"]),
        ("Scores computed",          cov["has_scores"]),
    ]:
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"  {label:<28} {count:>4} / {total}  {bar}  {pct:.0f}%")

    # ── Per-state score summary ───────────────────────────────────────────
    lines.append("\nSCORE SUMMARY BY STATE")
    lines.append(f"  {'State':<6}{'SA2s':>6}{'Avg Inv':>9}{'Avg Live':>10}{'Avg Grow':>10}{'Avg Edu':>10}{'Min':>7}{'Max':>7}")
    lines.append("  " + "─" * 64)
    for row in _state_score_summary(db):
        if state_filter and row["state"] != state_filter:
            continue
        lines.append(
            f"  {row['state']:<6}{row['sa2_count']:>6}"
            f"{row['avg_inv'] or 0:>9.2f}{row['avg_live'] or 0:>10.2f}"
            f"{row['avg_grow'] or 0:>10.2f}{row['avg_edu'] or 0:>10.2f}"
            f"{row['min_inv'] or 0:>7.2f}{row['max_inv'] or 0:>7.2f}"
        )

    # ── Plausibility checks ───────────────────────────────────────────────
    lines.append("\nPLAUSIBILITY CHECKS\n")

    checks = [
        ("Missing census data",          _check_missing_census(db, state_filter)),
        ("Zero biz data (pop > 5,000)",  _check_zero_biz(db, state_filter, pop_threshold=5000)),
        ("Zero transit (pop > 3,000)",   _check_zero_transit(db, state_filter, pop_threshold=3000)),
        ("No school links (pop > 2,000)",_check_no_schools(db, state_filter, pop_threshold=2000)),
        ("Missing SEIFA decile",         _check_missing_seifa(db, state_filter)),
        ("Extreme dimension scores",     _check_score_outliers(db, state_filter)),
    ]

    total_issues = 0
    for label, issues in checks:
        total_issues += len(issues)
        lines.append(_fmt_issues(issues, label, limit=10 if verbose else 5))

    lines.append(f"{'─'*70}")
    lines.append(f"  Total issues flagged: {total_issues}")
    lines.append(f"  Re-run with --verbose for full lists, --suburb <id> to trace one suburb.\n")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    p = argparse.ArgumentParser(description="Suburb Intel data quality audit")
    p.add_argument("--state",   help="Filter to one state, e.g. QLD")
    p.add_argument("--suburb",  help="Trace one suburb by slug, e.g. algester-qld")
    p.add_argument("--verbose", action="store_true", help="Show up to 10 items per check (default 5)")
    args = p.parse_args()

    from app.db.session import get_sync_session
    db = get_sync_session()
    try:
        report = run_audit(db, state_filter=args.state, suburb_id=args.suburb, verbose=args.verbose)
        print(report)
    finally:
        db.close()
