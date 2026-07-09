"""Tests for propradar_sold_loader's pure parsing functions, using the real
verified response shape (see that module's docstring — captured from a live
200 response against QLD/rochedale on 2026-07-08)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import PropertySale
from app.db.session import get_sync_session
from app.ingestion.propradar_sold_loader import (
    _fetched_this_month,
    _next_offset,
    _parse_address,
    _parse_listing,
    _split_suburb_parts,
    load_propradar_sold,
)

_REAL_LISTING = {
    "property_id": "7dafef6d",
    "address": "32 Parolin Parade, Rochedale, QLD, 4123",
    "bedrooms": 6,
    "bathrooms": 5,
    "parking": 2,
    "property_type": "House",
    "sold_price": 2280000,
    "sold_date": "2026-06-29",
}


def test_parse_listing_reads_real_field_names():
    sale = _parse_listing(_REAL_LISTING, sa2_code="303031064", state="QLD")

    assert sale is not None
    assert sale.id  # hashed from property_id
    assert sale.sa2_code == "303031064"
    assert sale.address == "32 Parolin Parade, Rochedale, QLD, 4123"
    assert sale.bedrooms == 6
    assert sale.bathrooms == 5
    assert sale.parking == 2
    assert sale.property_type == "house"
    assert sale.sold_price == 2280000
    assert sale.sold_date == "2026-06-29"
    assert sale.land_size_sqm is None  # confirmed absent from this endpoint
    assert sale.source == "propradar"
    assert sale.suburb_name == "Rochedale"  # parsed from the address, ground truth
    assert sale.postcode == "4123"


def test_parse_listing_none_when_missing_price_or_date():
    incomplete = {**_REAL_LISTING, "sold_price": None}
    assert _parse_listing(incomplete, sa2_code="303031064", state="QLD") is None


def test_next_offset_reads_pagination_object():
    data = {
        "sold": [_REAL_LISTING],
        "pagination": {"offset": 0, "limit": 50, "next_offset": 50, "next_cursor": "abc"},
    }
    assert _next_offset(data) == 50


def test_next_offset_none_on_last_page():
    data = {"sold": [_REAL_LISTING], "pagination": {"offset": 50, "limit": 50, "next_offset": None}}
    assert _next_offset(data) is None


def test_next_offset_none_when_no_pagination_key():
    assert _next_offset({"sold": [_REAL_LISTING]}) is None


def _seed_sale(db, sa2_code, fetched_at):
    db.merge(PropertySale(
        id=f"fresh-check-{sa2_code}",
        sa2_code=sa2_code,
        sold_price=500_000,
        sold_date="2026-01-01",
        source="propradar",
        fetched_at=fetched_at,
    ))
    db.commit()


def test_fetched_this_month_true_for_fetch_earlier_this_month():
    db = get_sync_session()
    now = datetime.now(timezone.utc)
    _seed_sale(db, "90000101", now.replace(day=1))
    assert _fetched_this_month(db, "90000101") is True
    db.close()


def test_fetched_this_month_false_for_fetch_last_month():
    db = get_sync_session()
    last_month = datetime.now(timezone.utc) - timedelta(days=45)
    _seed_sale(db, "90000102", last_month)
    assert _fetched_this_month(db, "90000102") is False
    db.close()


def test_fetched_this_month_false_when_no_data():
    db = get_sync_session()
    assert _fetched_this_month(db, "90000103") is False
    db.close()


def test_load_propradar_sold_rejects_unscoped_run():
    db = get_sync_session()
    with pytest.raises(ValueError, match="Must scope by"):
        load_propradar_sold(db, "fake-key")
    db.close()


def test_split_suburb_parts_splits_combined_sa2_name():
    # The actual bug this fixes: previously only "Rochedale" (the first
    # part) was ever queried, so Burbank's sold listings were silently
    # never fetched at all.
    assert _split_suburb_parts("Rochedale - Burbank") == ["Rochedale", "Burbank"]


def test_split_suburb_parts_handles_three_way_combined_name():
    assert _split_suburb_parts("Woolner - Bayview - Winnellie") == ["Woolner", "Bayview", "Winnellie"]


def test_split_suburb_parts_single_suburb_unchanged():
    assert _split_suburb_parts("Chermside") == ["Chermside"]


def test_split_suburb_parts_strips_state_suffix():
    assert _split_suburb_parts("St Kilda (Vic.)") == ["St Kilda"]


def test_parse_address_extracts_suburb_and_postcode():
    assert _parse_address("32 Parolin Parade, Rochedale, QLD, 4123") == ("Rochedale", "4123")


def test_parse_address_handles_unit_number_prefix():
    assert _parse_address("209/9C Terry Road, Rouse Hill, NSW, 2155") == ("Rouse Hill", "2155")


def test_parse_address_none_when_format_unexpected():
    assert _parse_address("not a real address") == (None, None)


def test_parse_address_none_when_last_segment_not_a_postcode():
    assert _parse_address("1 Test St, Somewhere, QLD, Australia") == (None, None)


def test_parse_address_normalizes_all_caps_suburb():
    # Real data quality issue: PropRadar returns "CLEVELAND" for some
    # listings and "Cleveland" for others in the same suburb.
    assert _parse_address("1 Test St, CLEVELAND, QLD, 4163") == ("Cleveland", "4163")


def test_parse_address_leaves_mixed_case_suburb_untouched():
    # Guards against title-casing mangling names like "McMahons Point".
    assert _parse_address("1 Test St, McMahons Point, NSW, 2060") == ("McMahons Point", "2060")
