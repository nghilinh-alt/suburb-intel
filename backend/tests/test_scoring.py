"""Tests for the pure scoring helpers in app.core.scoring and gov_score."""

from __future__ import annotations

import pytest

from app.core.gov_score import (
    analyze_risk_flags,
    calculate_gov_score,
    generate_insight,
)
from app.core.scoring import (
    calculate_demographic_score,
    calculate_economic_score,
    calculate_gov_investment_score,
    calculate_investment_score,
    normalize,
)
from app.core.utils import (
    calculate_employment_diversity,
    calculate_household_pressure,
    get_industry_diversity,
)


def test_normalize_handles_zero_range() -> None:
    """Regression: division-by-zero would explode the scoring pipeline."""
    assert normalize(5, 10, 10) == 0


def test_calculate_investment_score_weighted_sum() -> None:
    """The composite score should be a weighted sum of the five sub-scores."""
    features = {
        "pop_growth": 80,
        "young_population_pct": 60,
        "income_index": 90,
        "employment_diversity": 70,
        "renter_pct": 40,
        "household_pressure": 50,
        "industry_diversity": 75,
        "projects": [],
    }
    scores = calculate_investment_score(features)

    demographic = (80 + 60) / 2
    economic = 90 * 0.6 + 70 * 0.4
    housing = (40 + 50) / 2
    resilience = 75
    gov = 50.0  # no projects → default from sub-helper is 0; investment uses 0 here

    # The investment_score function calls calculate_gov_investment_score (returns 0)
    # not the default-50 fallback in the route layer, so use 0 in the assertion.
    expected = (
        demographic * 0.25
        + economic * 0.20
        + housing * 0.20
        + resilience * 0.15
        + 0 * 0.20
    )
    assert scores["investment_score"] == pytest.approx(expected, rel=1e-3)
    assert scores["demographic_score"] == pytest.approx(demographic)
    assert scores["economic_score"] == pytest.approx(economic)
    assert scores["resilience_score"] == pytest.approx(resilience)


def test_calculate_gov_investment_score_weights_status_and_type() -> None:
    projects = [
        {"type": "transport", "status": "under_construction", "value_aud": 1_000_000},
        {"type": "civic", "status": "planned", "value_aud": 1_000_000},
    ]
    expected = (1.0 * 1.0 * 1_000_000 + 0.4 * 0.4 * 1_000_000) / 1_000_000
    assert calculate_gov_investment_score(projects) == pytest.approx(expected, rel=1e-3)


def test_calculate_gov_score_handles_none_value_aud() -> None:
    """Regression: a project missing `value_aud` used to short-circuit to a fixed 1
    which silently underweighted real records. The current contract is to treat
    missing values as 1 explicitly; this test pins that behaviour."""
    score = calculate_gov_score([{"type": "transport", "status": "approved"}])
    # 1.0 (transport) * 0.7 (approved) * 1 (fallback) / 1_000_000 ≈ 0
    assert score == pytest.approx(0.0, abs=1e-3)


# ---------------------------------------------------------------------------
# Risk flags + insights — these used to assume `census_metrics` was a dict,
# but the routes pass a SQLAlchemy model instance. The functions now accept
# either; verify both work.
# ---------------------------------------------------------------------------

class _FakeCensus:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_analyze_risk_flags_accepts_dict() -> None:
    flags = analyze_risk_flags(
        projects=[{"status": "planned"}],
        census_metrics={
            "industry_profile": {"retail": 0.5, "tech": 0.5},
            "renters_pct": 55.0,
            "owners_pct": 30.0,
        },
    )
    assert any("retail" in f.lower() for f in flags)
    assert any("rental pressure" in f.lower() for f in flags)
    assert any("homeownership" in f.lower() for f in flags)
    assert any("uncertainty" in f.lower() for f in flags)


def test_analyze_risk_flags_accepts_model_instance() -> None:
    """Regression: routes pass an ORM instance, which crashed `.get()` calls."""
    metrics = _FakeCensus(
        industry_profile={"tech": 0.4, "finance": 0.3, "retail": 0.3},
        renters_pct=20.0,
        owners_pct=70.0,
    )
    flags = analyze_risk_flags(projects=[], census_metrics=metrics)
    # 0.4 max share > 0.3 → expect dependency flag, no rental/own flags.
    assert any("tech" in f.lower() for f in flags)
    assert not any("rental" in f.lower() for f in flags)
    assert not any("homeownership" in f.lower() for f in flags)


def test_generate_insight_handles_empty_industry_profile() -> None:
    """Regression: `max({}, key=...)` raised ValueError on empty profile."""
    insight = generate_insight(
        scores={"investment_score": 75, "gov_investment_score": 30},
        census_metrics={"industry_profile": {}, "pop_growth": 0, "young_population_pct": 0},
        projects=[],
    )
    assert "Strong investment profile" in insight
    assert "Limited industry data" in insight


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def test_diversity_helpers_return_default_on_empty() -> None:
    assert get_industry_diversity(None) == 50.0
    assert calculate_employment_diversity({}) == 50.0


def test_household_pressure_caps_at_100() -> None:
    assert calculate_household_pressure(200) == 100
    assert calculate_household_pressure(0) == 0


def test_calculate_demographic_score_is_simple_average() -> None:
    assert calculate_demographic_score(40, 60) == 50


def test_calculate_economic_score_weights_income_at_60pct() -> None:
    assert calculate_economic_score(100, 0) == pytest.approx(60.0)
    assert calculate_economic_score(0, 100) == pytest.approx(40.0)
