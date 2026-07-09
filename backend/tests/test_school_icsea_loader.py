"""Tests for school_icsea_loader's suburb-name SA2 matching — added after
discovering Algester's own ACARA-rated schools were being silently
misattributed to neighbouring Parkinson - Drewvale (the postcode's dominant
SA2 under the old postcode-only matching), since both suburbs share
postcode 4115."""

from __future__ import annotations

from app.db.models import SA2Region
from app.db.session import get_sync_session
from app.ingestion.school_icsea_loader import build_suburb_sa2_lookup, resolve_school_sa2


def _seed_sa2(db, sa2_code, sa2_name, state):
    db.merge(SA2Region(sa2_code=sa2_code, sa2_name=sa2_name, state=state))
    db.commit()


def test_suburb_lookup_resolves_unambiguous_name():
    db = get_sync_session()
    _seed_sa2(db, "92000001", "Algestertest", "QLD")
    _seed_sa2(db, "92000002", "Parkinsontest - Drewvaletest", "QLD")

    lookup = build_suburb_sa2_lookup(db)
    db.close()

    assert lookup[("QLD", "algestertest")] == "92000001"
    assert lookup[("QLD", "parkinsontest")] == "92000002"
    assert lookup[("QLD", "drewvaletest")] == "92000002"


def test_suburb_lookup_excludes_ambiguous_name_split_across_sa2s():
    db = get_sync_session()
    _seed_sa2(db, "92000003", "Bathursttest", "NSW")
    _seed_sa2(db, "92000004", "Bathursttest - Region", "NSW")

    lookup = build_suburb_sa2_lookup(db)
    db.close()

    # "Bathursttest" resolves to two different SA2s — ambiguous, must be excluded
    assert ("NSW", "bathursttest") not in lookup
    # The unique "Region" part is unambiguous and still resolves
    assert lookup[("NSW", "region")] == "92000004"


def test_resolve_school_sa2_prefers_suburb_match_over_postcode():
    suburb_to_sa2 = {("QLD", "algestertest"): "92000001"}
    postcode_to_sa2 = {"4115": "92000002"}  # postcode's dominant SA2 is the wrong neighbour

    resolved = resolve_school_sa2("Algestertest", "QLD", "4115", suburb_to_sa2, postcode_to_sa2)

    assert resolved == "92000001"


def test_resolve_school_sa2_falls_back_to_postcode_when_suburb_unmatched():
    suburb_to_sa2 = {("QLD", "algestertest"): "92000001"}
    postcode_to_sa2 = {"4115": "92000002"}

    resolved = resolve_school_sa2("Somewhere Else", "QLD", "4115", suburb_to_sa2, postcode_to_sa2)

    assert resolved == "92000002"


def test_resolve_school_sa2_falls_back_when_suburb_or_state_missing():
    suburb_to_sa2 = {("QLD", "algestertest"): "92000001"}
    postcode_to_sa2 = {"4115": "92000002"}

    assert resolve_school_sa2(None, "QLD", "4115", suburb_to_sa2, postcode_to_sa2) == "92000002"
    assert resolve_school_sa2("Algestertest", None, "4115", suburb_to_sa2, postcode_to_sa2) == "92000002"


def test_resolve_school_sa2_none_when_neither_matches():
    assert resolve_school_sa2("Nowhere", "QLD", "9999", {}, {}) is None
