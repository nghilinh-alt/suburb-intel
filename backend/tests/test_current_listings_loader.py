"""Tests for current_listings_loader's pure parsing functions, using the real
verified response shape (see that module's docstring — captured from a live
200 response against QLD/cleveland on 2026-07-10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import CurrentListing
from app.db.session import get_sync_session
from app.ingestion.current_listings_loader import (
    _fetched_this_month,
    _parse_listing,
    load_current_listings,
)

_REAL_LISTING_NO_PRICE = {
    "property_id": "170f9844",
    "address": "4 Capricorn Drive, Cleveland, QLD, 4163",
    "bedrooms": 4,
    "bathrooms": 2,
    "parking": 2,
    "property_type": "House",
    "asking_price_low": None,
    "asking_price_high": None,
    "sale_type": "Private Sale",
    "added_at": "2026-07-02T16:53:28.000Z",
}

_REAL_LISTING_WITH_PRICE = {
    "property_id": "85490ffc",
    "address": "15/150 Middle Street, Cleveland, QLD, 4163",
    "bedrooms": 2,
    "bathrooms": 2,
    "parking": 2,
    "property_type": "Apartment",
    "asking_price_low": 799000,
    "asking_price_high": 799000,
    "sale_type": "Private Sale",
    "added_at": "2026-07-01T14:58:50.000Z",
}


def test_parse_listing_reads_real_field_names():
    listing = _parse_listing(_REAL_LISTING_WITH_PRICE, sa2_code="303031064", state="QLD")

    assert listing is not None
    assert listing.id  # hashed from property_id
    assert listing.sa2_code == "303031064"
    assert listing.address == "15/150 Middle Street, Cleveland, QLD, 4163"
    assert listing.bedrooms == 2
    assert listing.bathrooms == 2
    assert listing.parking == 2
    assert listing.property_type == "apartment"
    assert listing.asking_price_low == 799000
    assert listing.asking_price_high == 799000
    assert listing.sale_type == "Private Sale"
    assert listing.listed_date == "2026-07-01"
    assert listing.source == "propradar"
    assert listing.suburb_name == "Cleveland"  # parsed from the address, ground truth
    assert listing.postcode == "4163"


def test_parse_listing_price_on_application_not_dropped():
    # Most listings have both asking_price fields null (price withheld) —
    # unlike /sold's required sold_price, this must still parse.
    listing = _parse_listing(_REAL_LISTING_NO_PRICE, sa2_code="303031064", state="QLD")

    assert listing is not None
    assert listing.asking_price_low is None
    assert listing.asking_price_high is None
    assert listing.address == "4 Capricorn Drive, Cleveland, QLD, 4163"


def test_parse_listing_none_when_missing_address():
    incomplete = {**_REAL_LISTING_WITH_PRICE, "address": None}
    assert _parse_listing(incomplete, sa2_code="303031064", state="QLD") is None


def _seed_listing(db, sa2_code, fetched_at):
    db.merge(CurrentListing(
        id=f"fresh-check-{sa2_code}",
        sa2_code=sa2_code,
        address="1 Test St, Test, QLD, 4000",
        source="propradar",
        fetched_at=fetched_at,
    ))
    db.commit()


def test_fetched_this_month_true_for_fetch_earlier_this_month():
    db = get_sync_session()
    now = datetime.now(timezone.utc)
    _seed_listing(db, "90000201", now.replace(day=1))
    assert _fetched_this_month(db, "90000201") is True
    db.close()


def test_fetched_this_month_false_for_fetch_last_month():
    db = get_sync_session()
    last_month = datetime.now(timezone.utc) - timedelta(days=45)
    _seed_listing(db, "90000202", last_month)
    assert _fetched_this_month(db, "90000202") is False
    db.close()


def test_fetched_this_month_false_when_no_data():
    db = get_sync_session()
    assert _fetched_this_month(db, "90000203") is False
    db.close()


def test_load_current_listings_rejects_unscoped_run():
    db = get_sync_session()
    with pytest.raises(ValueError, match="Must scope by"):
        load_current_listings(db, "fake-key")
    db.close()
