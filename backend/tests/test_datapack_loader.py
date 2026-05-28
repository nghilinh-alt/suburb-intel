"""Tests for abs_datapack_loader.py.

Uses a minimal synthetic DataPack zip built in-memory — no real ABS download needed.
Each _make_* helper produces a minimal CSV with only the columns the loader actually reads.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import ABSCEntensMetrics, Base, SA2Region
from app.ingestion.abs_datapack_loader import (
    LoadReport,
    _compute_avg_household_size,
    _compute_commute,
    _compute_families_with_children_pct,
    _compute_high_mortgage_stress_pct,
    _compute_high_rent_stress_pct,
    _compute_moved_in_1yr_pct,
    _compute_moved_in_5yr_pct,
    _compute_overseas_born_pct,
    _compute_professionals_managers_pct,
    _compute_tenure,
    _compute_unemployment_pct,
    _compute_uni_degree_pct,
    _compute_zero_car_dwellings_pct,
    load_datapack,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_session():
    """Fresh in-memory SQLite session scoped to the test module."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionFactory()
    yield session
    session.close()
    engine.dispose()


# Three fake SA2 codes
_SA2_VIC1 = "201011001"  # VIC
_SA2_VIC2 = "201011002"  # VIC
_SA2_NSW  = "101021007"  # NSW (filtered out when states=["VIC"])

_ROWS = [_SA2_VIC1, _SA2_VIC2, _SA2_NSW]


# ---------------------------------------------------------------------------
# Synthetic CSV builders  (minimal columns the loader actually uses)
# ---------------------------------------------------------------------------

def _csv(rows: list[str]) -> str:
    return "\n".join(rows)


def _make_g02() -> str:
    return _csv([
        "SA2_CODE_2021,Median_age_persons,Median_mortgage_repay_monthly,"
        "Median_tot_prsnl_inc_weekly,Median_rent_weekly,"
        "Median_tot_fam_inc_weekly,Average_num_psns_per_bedroom,"
        "Median_tot_hhd_inc_weekly,Average_household_size",
        f"{_SA2_VIC1},34,1500,1000,400,2500,0.8,2000,2.5",   # income × 52 = 52 000
        f"{_SA2_VIC2},28,1800,1500,550,3200,0.9,2800,2.8",   # income × 52 = 78 000
        f"{_SA2_NSW},42,1200,900,350,2100,0.7,1800,2.2",
    ])


def _make_g09f() -> str:
    """G09F — Persons parts F-H merged (minimal columns the loader needs)."""
    return _csv([
        "SA2_CODE_2021,P_Australia_Tot,P_China_Tot,P_India_Tot,P_COB_NS_Tot,P_Tot_Tot",
        f"{_SA2_VIC1},800,100,100,0,1000",   # overseas=1000-800-0=200 → 20 %
        f"{_SA2_VIC2},600,300,100,0,1000",   # overseas=1000-600-0=400 → 40 %
        f"{_SA2_NSW},450,30,20,0,500",        # overseas=500-450-0=50  → 10 %
    ])


def _make_g29() -> str:
    return _csv([
        "SA2_CODE_2021,CF_ChU15_a_Total_F,OPF_ChU15_a_Total_F,Total_F",
        f"{_SA2_VIC1},100,30,300",   # (130/300)×100 = 43.33 %
        f"{_SA2_VIC2},60,20,200",    # 40 %
        f"{_SA2_NSW},80,20,200",     # 50 %
    ])


def _make_g34() -> str:
    return _csv([
        "SA2_CODE_2021,Num_MVs_per_dweling_0_MVs,Total_dwelings",
        f"{_SA2_VIC1},50,500",   # 10 %
        f"{_SA2_VIC2},100,400",  # 25 %
        f"{_SA2_NSW},20,200",    # 10 %
    ])


def _make_g35() -> str:
    return _csv([
        "SA2_CODE_2021,"
        "Num_Psns_UR_1_Total,Num_Psns_UR_2_Total,Num_Psns_UR_3_Total,"
        "Num_Psns_UR_4_Total,Num_Psns_UR_5_Total,Num_Psns_UR_6mo_Total,Total_Total",
        # VIC1: (50+400+300+320+200+180)/500 = 1450/500 = 2.9
        f"{_SA2_VIC1},50,200,100,80,40,30,500",
        # VIC2: (100+300+240+200+75+30)/400 = 945/400 = 2.3625 → 2.36
        f"{_SA2_VIC2},100,150,80,50,15,5,400",
        f"{_SA2_NSW},30,100,50,30,10,5,225",
    ])


def _make_g36() -> str:
    return _csv([
        "SA2_CODE_2021,"
        "OPDs_Separate_house_Dwellings,OPDs_Flt_apart_Tot_Dwgs,OPDs_Tot_OPDs_Dwellings",
        f"{_SA2_VIC1},300,100,500",  # sep=60 %, flat=20 %
        f"{_SA2_VIC2},100,200,400",  # sep=25 %, flat=50 %
        f"{_SA2_NSW},150,20,200",    # sep=75 %, flat=10 %
    ])


def _make_g37() -> str:
    return _csv([
        "SA2_CODE_2021,"
        "O_OR_Total,O_MTG_Total,R_Tot_Total,"
        "R_ST_h_auth_Total,R_Com_Hp_Total,"
        "Oth_ten_type_Total,Total_Total",
        # renters=400/900=44.4 %, owners=450/900=50 %, social=70/900=7.78 %
        f"{_SA2_VIC1},200,250,400,50,20,0,900",
        f"{_SA2_VIC2},100,300,200,0,0,0,600",
        f"{_SA2_NSW},150,200,100,10,5,10,460",
    ])


def _make_g38() -> str:
    return _csv([
        "SA2_CODE_2021,M_3000_3999_Tot,M_4000_over_Tot,Tot_Tot",
        f"{_SA2_VIC1},50,30,450",   # (80/450)×100 = 17.78 %
        f"{_SA2_VIC2},30,20,300",
        f"{_SA2_NSW},10,5,200",
    ])


def _make_g40() -> str:
    return _csv([
        "SA2_CODE_2021,"
        "R_650_749_Tot,R_750_849_Tot,R_850_949_Tot,R_950_over_Tot,Tot_Tot",
        f"{_SA2_VIC1},40,30,20,10,400",   # (100/400)×100 = 25 %
        f"{_SA2_VIC2},20,10,5,5,200",
        f"{_SA2_NSW},5,3,2,0,100",
    ])


def _make_g41() -> str:
    return _csv([
        "SA2_CODE_2021,Total_NofB_1,Total_Total",
        f"{_SA2_VIC1},100,500",  # 20 %
        f"{_SA2_VIC2},120,400",  # 30 %
        f"{_SA2_NSW},20,200",    # 10 %
    ])


def _make_g44() -> str:
    return _csv([
        "SA2_CODE_2021,"
        "Dif_Us_ad_1_ago_Dif_SA2_Tot_P,Difnt_Usl_add_1_yr_ago_OS_P,Tot_P",
        # moved_in_1yr = (150+50)/1000 = 20 %; Tot_P used as population
        f"{_SA2_VIC1},150,50,1000",
        f"{_SA2_VIC2},80,20,800",
        f"{_SA2_NSW},30,20,500",
    ])


def _make_g45() -> str:
    return _csv([
        "SA2_CODE_2021,"
        "Dif_Us_ad_5_ago_Dif_SA2_Tot_P,Difnt_Usl_add_5_yr_ago_OS_P,Tot_P",
        # moved_in_5yr = (300+100)/1000 = 40 %
        f"{_SA2_VIC1},300,100,1000",
        f"{_SA2_VIC2},200,80,800",
        f"{_SA2_NSW},100,50,500",
    ])


def _make_g46b() -> str:
    return _csv([
        "SA2_CODE_2021,P_Tot_Emp_Tot,P_Tot_Unemp_Tot,P_Tot_LF_Tot",
        # unemployment = 70/770 = 9.09 %
        f"{_SA2_VIC1},700,70,770",
        f"{_SA2_VIC2},500,25,525",
        f"{_SA2_NSW},300,20,320",
    ])


def _make_g49b() -> str:
    return _csv([
        "SA2_CODE_2021,"
        "P_PGrad_Deg_Total,P_GradDip_and_GradCert_Total,P_BachDeg_Total,P_Tot_Total",
        # uni_degree = (50+30+120)/800 = 25 %
        f"{_SA2_VIC1},50,30,120,800",
        f"{_SA2_VIC2},20,10,50,600",
        f"{_SA2_NSW},10,5,30,400",
    ])


def _make_g60b() -> str:
    return _csv([
        "SA2_CODE_2021,P_Tot_Managers,P_Tot_Professionals,P_Tot_Tot",
        # prof_mgr = (80+120)/500 = 40 %
        f"{_SA2_VIC1},80,120,500",
        f"{_SA2_VIC2},40,60,400",
        f"{_SA2_NSW},30,40,300",
    ])


def _make_g62() -> str:
    return _csv([
        "SA2_CODE_2021,"
        "One_method_Train_P,One_method_Bus_P,One_method_Ferry_P,"
        "One_met_Tram_or_lt_rail_P,"
        "One_method_Car_as_driver_P,One_method_Car_as_passenger_P,"
        "Worked_home_P,Tot_P",
        # pt=(100+50+5+45)/1000=20 %, car=(300+50)/1000=35 %, wfh=100/1000=10 %
        f"{_SA2_VIC1},100,50,5,45,300,50,100,1000",
        f"{_SA2_VIC2},30,20,0,10,200,30,50,600",
        f"{_SA2_NSW},5,10,0,0,150,20,30,400",
    ])


def _make_geog_excel() -> bytes:
    rows = [
        {"ASGS_Structure": "SA4", "Census_Code_2021": "201", "AGSS_Code_2021": "201",
         "Census_Name_2021": "Melbourne Inner", "Area sqkm": "37.1"},
        {"ASGS_Structure": "SA3", "Census_Code_2021": "20101", "AGSS_Code_2021": "20101",
         "Census_Name_2021": "Melbourne City", "Area sqkm": "10.2"},
        {"ASGS_Structure": "SA2", "Census_Code_2021": _SA2_VIC1, "AGSS_Code_2021": _SA2_VIC1,
         "Census_Name_2021": "Test Suburb VIC1", "Area sqkm": "5.3"},
        {"ASGS_Structure": "SA2", "Census_Code_2021": _SA2_VIC2, "AGSS_Code_2021": _SA2_VIC2,
         "Census_Name_2021": "Test Suburb VIC2", "Area sqkm": "8.7"},
        {"ASGS_Structure": "SA4", "Census_Code_2021": "101", "AGSS_Code_2021": "101",
         "Census_Name_2021": "Capital Region", "Area sqkm": "51896.2"},
        {"ASGS_Structure": "SA3", "Census_Code_2021": "10102", "AGSS_Code_2021": "10102",
         "Census_Name_2021": "Queanbeyan", "Area sqkm": "6511.4"},
        {"ASGS_Structure": "SA2", "Census_Code_2021": _SA2_NSW, "AGSS_Code_2021": _SA2_NSW,
         "Census_Name_2021": "Test Suburb NSW", "Area sqkm": "3418.4"},
    ]
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    return buf.getvalue()


@pytest.fixture(scope="module")
def datapack_zip(tmp_path_factory) -> Path:
    """Build a minimal synthetic DataPack zip and return its path."""
    tmp = tmp_path_factory.mktemp("datapack")
    zip_path = tmp / "2021_GCP_SA2_for_TEST_short-header.zip"
    sub = "2021 Census GCP Statistical Area 2 for TEST"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{sub}/2021Census_G02_TEST_SA2.csv",  _make_g02())
        zf.writestr(f"{sub}/2021Census_G09F_TEST_SA2.csv", _make_g09f())
        zf.writestr(f"{sub}/2021Census_G29_TEST_SA2.csv",  _make_g29())
        zf.writestr(f"{sub}/2021Census_G34_TEST_SA2.csv",  _make_g34())
        zf.writestr(f"{sub}/2021Census_G35_TEST_SA2.csv",  _make_g35())
        zf.writestr(f"{sub}/2021Census_G36_TEST_SA2.csv",  _make_g36())
        zf.writestr(f"{sub}/2021Census_G37_TEST_SA2.csv",  _make_g37())
        zf.writestr(f"{sub}/2021Census_G38_TEST_SA2.csv",  _make_g38())
        zf.writestr(f"{sub}/2021Census_G40_TEST_SA2.csv",  _make_g40())
        zf.writestr(f"{sub}/2021Census_G41_TEST_SA2.csv",  _make_g41())
        zf.writestr(f"{sub}/2021Census_G44_TEST_SA2.csv",  _make_g44())
        zf.writestr(f"{sub}/2021Census_G45_TEST_SA2.csv",  _make_g45())
        zf.writestr(f"{sub}/2021Census_G46B_TEST_SA2.csv", _make_g46b())
        zf.writestr(f"{sub}/2021Census_G49B_TEST_SA2.csv", _make_g49b())
        zf.writestr(f"{sub}/2021Census_G60B_TEST_SA2.csv", _make_g60b())
        zf.writestr(f"{sub}/2021Census_G62_TEST_SA2.csv",  _make_g62())
        zf.writestr("Metadata/2021Census_geog_desc_test_release.xlsx", _make_geog_excel())

    return zip_path


# ---------------------------------------------------------------------------
# Integration tests — TestLoadDatapack
# ---------------------------------------------------------------------------

class TestLoadDatapack:

    def test_all_rows_loaded(self, datapack_zip, db_session):
        report = load_datapack(datapack_zip, db_session, year=2021)
        assert report.regions_inserted + report.regions_updated == 3
        assert report.metrics_inserted + report.metrics_updated == 3
        assert report.rows_skipped == 0

    def test_vic1_region_fields(self, db_session):
        r = db_session.get(SA2Region, _SA2_VIC1)
        assert r is not None
        assert r.sa2_name == "Test Suburb VIC1"
        assert r.state == "VIC"
        assert r.sa3_code == "20101"
        assert r.sa3_name == "Melbourne City"
        assert r.sa4_code == "201"
        assert r.sa4_name == "Melbourne Inner"
        assert r.area_sqkm == pytest.approx(5.3, rel=0.01)

    def test_vic1_demographics(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m is not None
        assert m.population == 1000              # G44 Tot_P
        assert m.median_age == pytest.approx(34.0)
        assert m.median_income == 1000 * 52      # 52 000
        assert m.median_mortgage_monthly == pytest.approx(1500.0)
        assert m.median_rent_weekly == pytest.approx(400.0)

    def test_vic1_overseas_born(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        # (800 AU + 100 CN + 100 IN) = 1000 total, 200 overseas → 20 %
        assert m.overseas_born_pct == pytest.approx(20.0, rel=0.01)

    def test_vic1_families(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m.families_with_children_pct == pytest.approx(130 / 300 * 100, rel=0.01)

    def test_vic1_tenure(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m.renters_pct  == pytest.approx(400 / 900 * 100, rel=0.01)
        assert m.owners_pct   == pytest.approx(450 / 900 * 100, rel=0.01)
        assert m.social_housing_pct == pytest.approx(70 / 900 * 100, rel=0.01)

    def test_vic1_property(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m.avg_household_size    == pytest.approx(2.9, rel=0.01)
        assert m.separate_house_pct    == pytest.approx(60.0, rel=0.01)
        assert m.flat_apartment_pct    == pytest.approx(20.0, rel=0.01)
        assert m.high_mortgage_stress_pct == pytest.approx(80 / 450 * 100, rel=0.01)
        assert m.high_rent_stress_pct  == pytest.approx(100 / 400 * 100, rel=0.01)

    def test_vic1_growth(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m.moved_in_1yr_pct         == pytest.approx(20.0, rel=0.01)
        assert m.moved_in_5yr_pct         == pytest.approx(40.0, rel=0.01)
        assert m.uni_degree_pct           == pytest.approx(200 / 800 * 100, rel=0.01)
        assert m.professionals_managers_pct == pytest.approx(200 / 500 * 100, rel=0.01)

    def test_vic1_lifestyle(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m.zero_car_dwellings_pct == pytest.approx(10.0, rel=0.01)
        assert m.pt_commute_pct         == pytest.approx(20.0, rel=0.01)
        assert m.car_commute_pct        == pytest.approx(35.0, rel=0.01)
        assert m.work_from_home_pct     == pytest.approx(10.0, rel=0.01)

    def test_vic1_risk(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m.one_bedroom_pct  == pytest.approx(20.0, rel=0.01)
        assert m.unemployment_pct == pytest.approx(70 / 770 * 100, rel=0.01)

    def test_legacy_fields_are_null(self, db_session):
        """Fields from out-of-scope tables must be NULL (not errors)."""
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m.industry_profile   is None
        assert m.young_population_pct is None
        assert m.pop_growth_5yr     is None

    def test_state_filter_skips_nsw(self, datapack_zip, tmp_path):
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        try:
            load_datapack(datapack_zip, session, year=2021, states=["VIC"])
            codes = [r.sa2_code for r in session.query(SA2Region).all()]
            assert _SA2_NSW  not in codes
            assert _SA2_VIC1 in codes
            assert _SA2_VIC2 in codes
        finally:
            session.close()
            engine.dispose()

    def test_idempotent_repeated_load(self, datapack_zip, db_session):
        before = db_session.query(SA2Region).count()
        report2 = load_datapack(datapack_zip, db_session, year=2021)
        after = db_session.query(SA2Region).count()
        assert after == before          # no duplicate rows
        assert report2.regions_inserted == 0
        assert report2.metrics_inserted == 0

    def test_g60b_absent_yields_null(self, tmp_path):
        """If G60B is missing from the zip, professionals_managers_pct is NULL (not an error)."""
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        zip_path = tmp_path / "no_g60b.zip"
        sub = "2021 Census GCP Statistical Area 2 for TEST"
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Write all tables except G60B
            for fname, content in [
                (f"{sub}/2021Census_G02_TEST_SA2.csv",  _make_g02()),
                (f"{sub}/2021Census_G09F_TEST_SA2.csv", _make_g09f()),
                (f"{sub}/2021Census_G29_TEST_SA2.csv",  _make_g29()),
                (f"{sub}/2021Census_G34_TEST_SA2.csv",  _make_g34()),
                (f"{sub}/2021Census_G35_TEST_SA2.csv",  _make_g35()),
                (f"{sub}/2021Census_G36_TEST_SA2.csv",  _make_g36()),
                (f"{sub}/2021Census_G37_TEST_SA2.csv",  _make_g37()),
                (f"{sub}/2021Census_G38_TEST_SA2.csv",  _make_g38()),
                (f"{sub}/2021Census_G40_TEST_SA2.csv",  _make_g40()),
                (f"{sub}/2021Census_G41_TEST_SA2.csv",  _make_g41()),
                (f"{sub}/2021Census_G44_TEST_SA2.csv",  _make_g44()),
                (f"{sub}/2021Census_G45_TEST_SA2.csv",  _make_g45()),
                (f"{sub}/2021Census_G46B_TEST_SA2.csv", _make_g46b()),
                (f"{sub}/2021Census_G49B_TEST_SA2.csv", _make_g49b()),
                (f"{sub}/2021Census_G62_TEST_SA2.csv",  _make_g62()),
            ]:
                zf.writestr(fname, content)
            zf.writestr("Metadata/2021Census_geog_desc_test_release.xlsx", _make_geog_excel())
        try:
            report = load_datapack(zip_path, session, year=2021)
            assert report.rows_skipped == 0
            m = session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
            assert m.professionals_managers_pct is None
        finally:
            session.close()
            engine.dispose()


# ---------------------------------------------------------------------------
# Unit tests — TestHelperFunctions
# ---------------------------------------------------------------------------

class TestHelperFunctions:

    # ── G09 ──────────────────────────────────────────────────────────────────

    def test_overseas_born_pct(self):
        df = pd.DataFrame({
            "SA2_CODE_2021":    [_SA2_VIC1],
            "P_Australia_Tot":  [800],
            "P_China_Tot":      [100],
            "P_India_Tot":      [100],
            "P_COB_NS_Tot":     [0],
            "P_Tot_Tot":        [1000],
        })
        result = _compute_overseas_born_pct(df, _SA2_VIC1)
        assert result == pytest.approx(20.0)

    def test_overseas_born_none_on_none_df(self):
        assert _compute_overseas_born_pct(None, _SA2_VIC1) is None

    # ── G29 ──────────────────────────────────────────────────────────────────

    def test_families_with_children_pct(self):
        df = pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "CF_ChU15_a_Total_F":  [100],
            "OPF_ChU15_a_Total_F": [30],
            "Total_F": [300],
        })
        assert _compute_families_with_children_pct(df, _SA2_VIC1) == pytest.approx(130 / 300 * 100)

    # ── G34 ──────────────────────────────────────────────────────────────────

    def test_zero_car_dwellings_pct(self):
        df = pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "Num_MVs_per_dweling_0_MVs": [50],
            "Total_dwelings": [500],
        })
        assert _compute_zero_car_dwellings_pct(df, _SA2_VIC1) == pytest.approx(10.0)

    # ── G35 ──────────────────────────────────────────────────────────────────

    def test_avg_household_size(self):
        df = pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "Num_Psns_UR_1_Total": [50],
            "Num_Psns_UR_2_Total": [200],
            "Num_Psns_UR_3_Total": [100],
            "Num_Psns_UR_4_Total": [80],
            "Num_Psns_UR_5_Total": [40],
            "Num_Psns_UR_6mo_Total": [30],
            "Total_Total": [500],
        })
        # (50 + 400 + 300 + 320 + 200 + 180) / 500 = 1450/500 = 2.9
        assert _compute_avg_household_size(df, _SA2_VIC1) == pytest.approx(2.9)

    # ── G37 ──────────────────────────────────────────────────────────────────

    def test_tenure(self):
        df = pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "O_OR_Total":        [200],
            "O_MTG_Total":       [250],
            "R_Tot_Total":       [400],
            "R_ST_h_auth_Total": [50],
            "R_Com_Hp_Total":    [20],
            "Total_Total":       [900],
        })
        renters, owners, social = _compute_tenure(df, _SA2_VIC1)
        assert renters == pytest.approx(400 / 900 * 100)
        assert owners  == pytest.approx(450 / 900 * 100)
        assert social  == pytest.approx(70  / 900 * 100)

    # ── G38 ──────────────────────────────────────────────────────────────────

    def test_high_mortgage_stress(self):
        df = pd.DataFrame({
            "SA2_CODE_2021":    [_SA2_VIC1],
            "M_3000_3999_Tot":  [50],
            "M_4000_over_Tot":  [30],
            "Tot_Tot":          [450],
        })
        assert _compute_high_mortgage_stress_pct(df, _SA2_VIC1) == pytest.approx(80 / 450 * 100)

    # ── G40 ──────────────────────────────────────────────────────────────────

    def test_high_rent_stress(self):
        df = pd.DataFrame({
            "SA2_CODE_2021":  [_SA2_VIC1],
            "R_650_749_Tot":  [40],
            "R_750_849_Tot":  [30],
            "R_850_949_Tot":  [20],
            "R_950_over_Tot": [10],
            "Tot_Tot":        [400],
        })
        assert _compute_high_rent_stress_pct(df, _SA2_VIC1) == pytest.approx(25.0)

    # ── G44 / G45 ────────────────────────────────────────────────────────────

    def test_moved_in_1yr_pct(self):
        df = pd.DataFrame({
            "SA2_CODE_2021":                    [_SA2_VIC1],
            "Dif_Us_ad_1_ago_Dif_SA2_Tot_P":   [150],
            "Difnt_Usl_add_1_yr_ago_OS_P":      [50],
            "Tot_P":                            [1000],
        })
        assert _compute_moved_in_1yr_pct(df, _SA2_VIC1) == pytest.approx(20.0)

    def test_moved_in_5yr_pct(self):
        df = pd.DataFrame({
            "SA2_CODE_2021":                    [_SA2_VIC1],
            "Dif_Us_ad_5_ago_Dif_SA2_Tot_P":   [300],
            "Difnt_Usl_add_5_yr_ago_OS_P":      [100],
            "Tot_P":                            [1000],
        })
        assert _compute_moved_in_5yr_pct(df, _SA2_VIC1) == pytest.approx(40.0)

    # ── G46B ─────────────────────────────────────────────────────────────────

    def test_unemployment_pct(self):
        df = pd.DataFrame({
            "SA2_CODE_2021":    [_SA2_VIC1],
            "P_Tot_Emp_Tot":    [700],
            "P_Tot_Unemp_Tot":  [70],
            "P_Tot_LF_Tot":     [770],
        })
        assert _compute_unemployment_pct(df, _SA2_VIC1) == pytest.approx(70 / 770 * 100)

    # ── G49B ─────────────────────────────────────────────────────────────────

    def test_uni_degree_pct(self):
        df = pd.DataFrame({
            "SA2_CODE_2021":                    [_SA2_VIC1],
            "P_PGrad_Deg_Total":               [50],
            "P_GradDip_and_GradCert_Total":    [30],
            "P_BachDeg_Total":                 [120],
            "P_Tot_Total":                     [800],
        })
        assert _compute_uni_degree_pct(df, _SA2_VIC1) == pytest.approx(200 / 800 * 100)

    # ── G60B ─────────────────────────────────────────────────────────────────

    def test_professionals_managers_pct(self):
        df = pd.DataFrame({
            "SA2_CODE_2021":       [_SA2_VIC1],
            "P_Tot_Managers":      [80],
            "P_Tot_Professionals": [120],
            "P_Tot_Tot":           [500],
        })
        assert _compute_professionals_managers_pct(df, _SA2_VIC1) == pytest.approx(40.0)

    def test_professionals_managers_none_on_none_df(self):
        assert _compute_professionals_managers_pct(None, _SA2_VIC1) is None

    # ── G62 ──────────────────────────────────────────────────────────────────

    def test_commute(self):
        df = pd.DataFrame({
            "SA2_CODE_2021":                [_SA2_VIC1],
            "One_method_Train_P":           [100],
            "One_method_Bus_P":             [50],
            "One_method_Ferry_P":           [5],
            "One_met_Tram_or_lt_rail_P":   [45],
            "One_method_Car_as_driver_P":   [300],
            "One_method_Car_as_passenger_P":[50],
            "Worked_home_P":                [100],
            "Tot_P":                        [1000],
        })
        pt, car, wfh = _compute_commute(df, _SA2_VIC1)
        assert pt  == pytest.approx(20.0)
        assert car == pytest.approx(35.0)
        assert wfh == pytest.approx(10.0)
