"""Tests for geometry_loader's adaptive simplification tolerance — added
after discovering a fixed 100 m tolerance collapsed small suburbs like
Algester to ~11 vertices, clipping off real parts of the suburb and
silently undercounting amenities in every downstream point-in-polygon join."""

from __future__ import annotations

from shapely.geometry import Polygon

from app.ingestion.geometry_loader import (
    _MAX_TOLERANCE,
    _MIN_TOLERANCE,
    _TOLERANCE_DIVISOR,
    _adaptive_tolerance,
)


def _square(width_deg: float) -> Polygon:
    return Polygon([(0, 0), (width_deg, 0), (width_deg, width_deg), (0, width_deg)])


def test_small_suburb_gets_fine_tolerance():
    # A ~2km-wide suburb (roughly Algester's scale) should get a tolerance
    # far finer than the old fixed 100m default.
    small = _square(0.02)
    tolerance = _adaptive_tolerance(small)
    assert tolerance < 0.0001  # well under the old ~100m fixed tolerance
    assert tolerance >= _MIN_TOLERANCE


def test_huge_rural_sa2_gets_clamped_to_max():
    huge = _square(5.0)  # a sprawling outback-scale SA2
    tolerance = _adaptive_tolerance(huge)
    assert tolerance == _MAX_TOLERANCE


def test_tiny_polygon_gets_clamped_to_min():
    tiny = _square(0.0001)
    tolerance = _adaptive_tolerance(tiny)
    assert tolerance == _MIN_TOLERANCE


def test_tolerance_scales_with_diagonal():
    small = _square(0.01)
    bigger = _square(0.1)
    assert _adaptive_tolerance(bigger) > _adaptive_tolerance(small)


def test_tolerance_matches_diagonal_divisor_formula_in_unclamped_range():
    width = 0.05  # chosen so the result lands between min and max
    diagonal = (width**2 + width**2) ** 0.5
    expected = diagonal / _TOLERANCE_DIVISOR
    assert _MIN_TOLERANCE < expected < _MAX_TOLERANCE
    assert _adaptive_tolerance(_square(width)) == expected
