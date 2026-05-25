"""Government investment scoring + risk/insight helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Union

# A census record may arrive as either an ORM model instance or a dict.
CensusLike = Union[Mapping[str, Any], Any]


def _census_get(metrics: CensusLike, key: str, default: Any = None) -> Any:
    """Read a field from either a dict or an attribute-bearing model instance."""
    if isinstance(metrics, Mapping):
        return metrics.get(key, default)
    return getattr(metrics, key, default)


def calculate_gov_score(projects: Iterable[Mapping[str, Any]]) -> float:
    """Government-investment score normalised to 0–100.

    Weightings:
        Type:   transport(1.0), health(0.9), education(0.7), civic(0.4)
        Stage:  under_construction(1.0), approved(0.7), planned(0.4),
                completed(0.2), cancelled(0.0)
    """
    type_weights = {"transport": 1.0, "health": 0.9, "education": 0.7, "civic": 0.4}
    stage_weights = {
        "under_construction": 1.0,
        "approved": 0.7,
        "planned": 0.4,
        "completed": 0.2,
        "cancelled": 0.0,
    }

    score = 0.0
    for p in projects:
        type_weight = type_weights.get(p.get("type", ""), 0.5)
        stage_weight = stage_weights.get(p.get("status", "planned"), 0.3)
        project_value = p.get("value_aud") or 1
        score += project_value * type_weight * stage_weight

    return round(min(score / 1_000_000, 100), 2)


def analyze_risk_flags(
    projects: Iterable[Mapping[str, Any]], census_metrics: CensusLike
) -> List[str]:
    """Return a list of human-readable risk flags for a suburb."""
    risk_flags: List[str] = []

    industry_profile = _census_get(census_metrics, "industry_profile", {}) or {}
    if industry_profile:
        max_industry_share = max(industry_profile.values())
        if max_industry_share > 0.3:
            dominant = max(industry_profile, key=industry_profile.get)
            risk_flags.append(
                f"HIGH dependency on {dominant} sector ({max_industry_share * 100:.0f}%)"
            )

    renter_pct = _census_get(census_metrics, "renters_pct", 0) or 0
    if renter_pct > 40:
        risk_flags.append(
            f"High rental pressure: {renter_pct:.1f}% of residents are renters"
        )

    owners_pct = _census_get(census_metrics, "owners_pct", 0) or 0
    if owners_pct and owners_pct < 50:
        risk_flags.append(
            f"Low homeownership rate: only {owners_pct:.1f}% own their home"
        )

    uncertain = [p for p in projects if p.get("status") in ("planned", "cancelled")]
    if uncertain:
        risk_flags.append(
            f"{len(uncertain)} government projects at uncertainty (planned/cancelled)"
        )

    return risk_flags


def generate_insight(
    scores: Mapping[str, Any],
    census_metrics: CensusLike,
    projects: Iterable[Mapping[str, Any]],  # noqa: ARG001 - reserved for future use
) -> str:
    """Produce a human-readable summary insight for the suburb."""
    investment_score = scores.get("investment_score", 0) or 0
    gov_score = scores.get("gov_investment_score", 0) or 0
    pop_growth = _census_get(census_metrics, "pop_growth", 0) or 0
    young_pct = _census_get(census_metrics, "young_population_pct", 0) or 0

    parts: List[str] = []

    if investment_score > 80:
        parts.append("Exceptional investment opportunity")
    elif investment_score > 70:
        parts.append("Strong investment profile")
    elif investment_score > 60:
        parts.append("Moderate investment potential")
    else:
        parts.append("Caution recommended - lower scores")

    if gov_score > 80:
        parts.append("Major infrastructure tailwind in pipeline")
    elif gov_score > 50:
        parts.append("Supportive government investment trajectory")

    if pop_growth > 30 and young_pct > 25:
        parts.append("Demographic momentum accelerating")

    industry_profile = _census_get(census_metrics, "industry_profile", {}) or {}
    if not industry_profile:
        parts.append("Limited industry data")
    elif len(industry_profile) < 3 or max(industry_profile.values()) > 0.35:
        parts.append("Diversification needed across sectors")
    else:
        parts.append("Well-diversified employment base")

    return "; ".join(parts) if parts else "Mixed investment characteristics"
