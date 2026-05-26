"""Tests for abs_datapack_loader.py.

Uses a minimal synthetic DataPack zip built in-memory — no real ABS download needed.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Generator

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import ABSCEntensMetrics, Base, SA2Region
from app.ingestion.abs_datapack_loader import (
    LoadReport,
    _compute_industry_profile,
    _compute_owners_pct,
    _compute_renters_pct,
    _compute_young_pct,
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


# Two fake SA2 codes and one out-of-scope state code
_SA2_VIC1 = "201011001"  # VIC
_SA2_VIC2 = "201011002"  # VIC
_SA2_NSW  = "101021007"  # NSW (should be filtered when states=["VIC"])

_ROWS = [_SA2_VIC1, _SA2_VIC2, _SA2_NSW]


def _make_g01() -> str:
    rows = []
    rows.append(
        "SA2_CODE_2021,Tot_P_M,Tot_P_F,Tot_P_P,"
        "Age_0_4_yr_P,Age_5_14_yr_P,Age_15_19_yr_P,Age_20_24_yr_P,"
        "Age_25_34_yr_P,Age_35_44_yr_P,Age_45_54_yr_P,Age_55_64_yr_P,"
        "Age_65_74_yr_P,Age_75_84_yr_P,Age_85ov_P"
    )
    # VIC1: 1000 total, 150 aged 15-34 → young_pct = 15%
    rows.append(f"{_SA2_VIC1},500,500,1000,50,100,50,50,50,200,200,150,100,50,0")
    # VIC2: 2000 total, 600 aged 15-34 → young_pct = 30%
    rows.append(f"{_SA2_VIC2},1000,1000,2000,100,200,100,200,300,400,300,200,150,50,0")
    # NSW: 500 total
    rows.append(f"{_SA2_NSW},250,250,500,20,50,30,30,40,100,80,70,50,20,10")
    return "\n".join(rows)


def _make_g02() -> str:
    rows = [
        "SA2_CODE_2021,Median_age_persons,Median_mortgage_repay_monthly,"
        "Median_tot_prsnl_inc_weekly,Median_rent_weekly,Median_tot_fam_inc_weekly,"
        "Average_num_psns_per_bedroom,Median_tot_hhd_inc_weekly,Average_household_size"
    ]
    rows.append(f"{_SA2_VIC1},34,1500,1000,400,2500,0.8,2000,2.5")   # 1000×52=52000 annual
    rows.append(f"{_SA2_VIC2},28,1800,1500,550,3200,0.9,2800,2.8")   # 1500×52=78000 annual
    rows.append(f"{_SA2_NSW},42,1200,900,350,2100,0.7,1800,2.2")
    return "\n".join(rows)


def _make_g37() -> str:
    # O_OR_Total, O_MTG_Total, R_Tot_Total, Total_Total
    rows = ["SA2_CODE_2021,O_OR_Total,O_MTG_Total,R_Tot_Total,Oth_ten_type_Total,Total_Total"]
    # VIC1: 200 owned outright, 250 with mortgage, 400 rented, 50 other → 900 total
    # renters_pct = 400/900*100 ≈ 44.4, owners_pct = 450/900*100 = 50.0
    rows.append(f"{_SA2_VIC1},200,250,400,50,900")
    # VIC2: 100 outright, 300 mortgage, 200 rented, 0 other → 600 total
    rows.append(f"{_SA2_VIC2},100,300,200,0,600")
    rows.append(f"{_SA2_NSW},150,200,100,10,460")
    return "\n".join(rows)


def _make_g53b() -> str:
    cols = (
        "SA2_CODE_2021,"
        "P_AgriForestFish_ToT,P_Min_ToT,P_Mnfg_ToT,P_EGW_WS_ToT,P_Cnstn_ToT,"
        "P_WTrade_ToT,P_RTrade_ToT,P_AccomFoodS_ToT,P_TransPostWhse_ToT,"
        "P_InfoMedTelecom_ToT,P_FinInsurS_ToT,P_RentHirREserv_ToT,"
        "P_ProScieTechServ_ToT,P_AdminSupServ_ToT,P_PubAdmiSafety_ToT"
    )
    rows = [cols]
    # VIC1: tech=100, finance=100, retail=100, rest=50 each (9 × 50=450)
    rows.append(f"{_SA2_VIC1},10,10,50,10,50,30,40,30,50,100,100,20,100,20,20")
    rows.append(f"{_SA2_VIC2},5,5,40,5,40,20,30,20,40,80,80,10,80,10,10")
    rows.append(f"{_SA2_NSW},5,5,30,5,30,15,20,15,30,60,60,8,60,8,8")
    return "\n".join(rows)


def _make_g53c() -> str:
    cols = (
        "SA2_CODE_2021,"
        "P_EducTrain_PD,P_EducTrain_GD_GC,P_EducTrain_BD,P_EducTrain_AdD_D,"
        "P_EducTrain_Cert,P_EducTrain_ID_NS,P_EducTrain_ToT,"
        "P_HealthCareSocA_PD,P_HealthCareSocA_GD_GC,P_HealthCareSocA_BD,"
        "P_HealthCareSocA_AdD_D,P_HealthCareSocA_Cert,P_HealthCareSocA_ID_NS,"
        "P_HealthCareSocA_ToT,"
        "P_ArtRecServ_PD,P_ArtRecServ_GD_GC,P_ArtRecServ_BD,P_ArtRecServ_AdD_D,"
        "P_ArtRecServ_Cert,P_ArtRecServ_ID_NS,P_ArtRecServ_ToT,"
        "P_OthServ_PD,P_OthServ_GD_GC,P_OthServ_BD,P_OthServ_AdD_D,"
        "P_OthServ_Cert,P_OthServ_ID_NS,P_OthServ_ToT,"
        "P_ID_NS_ToT,P_ToT_ToT"
    )
    rows = [cols]
    # VIC1: G53B total=640, G53C industry part=200, grand total=840
    rows.append(f"{_SA2_VIC1},10,15,30,15,10,0,80,10,15,30,15,10,0,80,5,5,5,3,2,0,20,5,3,5,3,2,2,20,0,840")
    # VIC2: G53B sum=475, G53C industry part=160, grand total=635
    rows.append(f"{_SA2_VIC2},8,12,24,12,8,0,64,8,12,24,12,8,0,64,4,4,4,2,2,0,16,4,2,4,2,2,2,16,0,635")
    # NSW: G53B sum=359, G53C industry part=106, grand total=465
    rows.append(f"{_SA2_NSW},5,8,16,8,5,0,42,5,8,16,8,5,0,42,3,3,3,1,1,0,11,3,2,3,1,1,1,11,0,465")
    return "\n".join(rows)


def _make_geog_excel() -> bytes:
    rows = [
        {"ASGS_Structure": "SA4", "Census_Code_2021": "201", "AGSS_Code_2021": "201", "Census_Name_2021": "Melbourne Inner", "Area sqkm": "37.1"},
        {"ASGS_Structure": "SA3", "Census_Code_2021": "20101", "AGSS_Code_2021": "20101", "Census_Name_2021": "Melbourne City", "Area sqkm": "10.2"},
        {"ASGS_Structure": "SA2", "Census_Code_2021": _SA2_VIC1, "AGSS_Code_2021": _SA2_VIC1, "Census_Name_2021": "Test Suburb VIC1", "Area sqkm": "5.3"},
        {"ASGS_Structure": "SA2", "Census_Code_2021": _SA2_VIC2, "AGSS_Code_2021": _SA2_VIC2, "Census_Name_2021": "Test Suburb VIC2", "Area sqkm": "8.7"},
        {"ASGS_Structure": "SA4", "Census_Code_2021": "101", "AGSS_Code_2021": "101", "Census_Name_2021": "Capital Region", "Area sqkm": "51896.2"},
        {"ASGS_Structure": "SA3", "Census_Code_2021": "10102", "AGSS_Code_2021": "10102", "Census_Name_2021": "Queanbeyan", "Area sqkm": "6511.4"},
        {"ASGS_Structure": "SA2", "Census_Code_2021": _SA2_NSW, "AGSS_Code_2021": _SA2_NSW, "Census_Name_2021": "Test Suburb NSW", "Area sqkm": "3418.4"},
    ]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


@pytest.fixture(scope="module")
def datapack_zip(tmp_path_factory) -> Path:
    """Build a minimal synthetic DataPack zip in memory and return its path."""
    tmp = tmp_path_factory.mktemp("datapack")
    zip_path = tmp / "2021_GCP_SA2_for_TEST_short-header.zip"
    subdir = "2021 Census GCP Statistical Area 2 for TEST"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{subdir}/2021Census_G01_TEST_SA2.csv", _make_g01())
        zf.writestr(f"{subdir}/2021Census_G02_TEST_SA2.csv", _make_g02())
        zf.writestr(f"{subdir}/2021Census_G37_TEST_SA2.csv", _make_g37())
        zf.writestr(f"{subdir}/2021Census_G53B_TEST_SA2.csv", _make_g53b())
        zf.writestr(f"{subdir}/2021Census_G53C_TEST_SA2.csv", _make_g53c())
        zf.writestr("Metadata/2021Census_geog_desc_test_release.xlsx", _make_geog_excel())

    return zip_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadDatapack:
    def test_all_regions_inserted(self, datapack_zip, db_session):
        report = load_datapack(datapack_zip, db_session, year=2021)
        assert report.regions_inserted + report.regions_updated == 3
        assert report.metrics_inserted + report.metrics_updated == 3

    def test_vic1_region_fields(self, db_session):
        region = db_session.get(SA2Region, _SA2_VIC1)
        assert region is not None
        assert region.sa2_name == "Test Suburb VIC1"
        assert region.state == "VIC"
        assert region.sa3_code == "20101"
        assert region.sa3_name == "Melbourne City"
        assert region.sa4_code == "201"
        assert region.sa4_name == "Melbourne Inner"
        assert region.area_sqkm == pytest.approx(5.3, rel=0.01)

    def test_vic1_metrics_values(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m is not None
        assert m.population == 1000
        assert m.median_age == pytest.approx(34.0)
        assert m.median_income == 1000 * 52  # 52000
        assert m.renters_pct == pytest.approx(400 / 900 * 100, rel=0.01)
        assert m.owners_pct == pytest.approx(450 / 900 * 100, rel=0.01)

    def test_young_population_pct(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        # age 15-34 = 50+50+50=150 out of 1000 → 15%
        assert m.young_population_pct == pytest.approx(15.0, rel=0.01)

    def test_industry_profile_sums_to_one(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m.industry_profile is not None
        total = sum(m.industry_profile.values())
        assert total == pytest.approx(1.0, abs=0.05)  # allow for rounding

    def test_industry_profile_has_expected_buckets(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert set(m.industry_profile.keys()).issubset(
            {"agriculture", "manufacturing", "construction", "retail",
             "tech", "finance", "education", "healthcare", "services"}
        )

    def test_state_filter_skips_nsw(self, datapack_zip, tmp_path):
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
        session = SessionFactory()
        try:
            report = load_datapack(datapack_zip, session, year=2021, states=["VIC"])
            vic_codes = [r.sa2_code for r in session.query(SA2Region).all()]
            assert _SA2_NSW not in vic_codes
            assert _SA2_VIC1 in vic_codes
            assert _SA2_VIC2 in vic_codes
        finally:
            session.close()
            engine.dispose()

    def test_idempotent_repeated_load(self, datapack_zip, db_session):
        before = db_session.query(SA2Region).count()
        report2 = load_datapack(datapack_zip, db_session, year=2021)
        after = db_session.query(SA2Region).count()
        assert after == before  # no duplicates
        assert report2.regions_inserted == 0  # all updated, none inserted
        assert report2.metrics_inserted == 0

    def test_vic2_metrics_young_pct(self, db_session):
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC2, 2021))
        # age 15-34 = 100+200+300=600 out of 2000 → 30%
        assert m.young_population_pct == pytest.approx(30.0, rel=0.01)

    def test_pop_growth_is_null(self, db_session):
        """pop_growth_5yr should be NULL until 2016 DataPack is loaded."""
        m = db_session.get(ABSCEntensMetrics, (_SA2_VIC1, 2021))
        assert m.pop_growth_5yr is None


class TestHelperFunctions:
    """Unit tests for the helper computation functions."""

    def _make_g01_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "Tot_P_P": [1000],
            "Age_15_19_yr_P": [50],
            "Age_20_24_yr_P": [50],
            "Age_25_34_yr_P": [50],
        })

    def _make_g37_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "O_OR_Total": [200],
            "O_MTG_Total": [250],
            "R_Tot_Total": [400],
            "Total_Total": [900],
        })

    def test_young_pct_calculation(self):
        df = self._make_g01_df()
        result = _compute_young_pct(df, _SA2_VIC1)
        assert result == pytest.approx(15.0)

    def test_young_pct_capped_at_100(self):
        df = pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "Tot_P_P": [100],
            "Age_15_19_yr_P": [50],
            "Age_20_24_yr_P": [50],
            "Age_25_34_yr_P": [50],  # 150 > 100 total
        })
        result = _compute_young_pct(df, _SA2_VIC1)
        assert result == pytest.approx(100.0)

    def test_renters_pct(self):
        df = self._make_g37_df()
        result = _compute_renters_pct(df, _SA2_VIC1)
        assert result == pytest.approx(400 / 900 * 100)

    def test_owners_pct(self):
        df = self._make_g37_df()
        result = _compute_owners_pct(df, _SA2_VIC1)
        assert result == pytest.approx(450 / 900 * 100)

    def test_industry_profile_fractions_sum(self):
        g53b_df = pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "P_AgriForestFish_ToT": [10],
            "P_Min_ToT": [10],
            "P_Mnfg_ToT": [50],
            "P_EGW_WS_ToT": [10],
            "P_Cnstn_ToT": [50],
            "P_WTrade_ToT": [30],
            "P_RTrade_ToT": [40],
            "P_AccomFoodS_ToT": [30],
            "P_TransPostWhse_ToT": [50],
            "P_InfoMedTelecom_ToT": [100],
            "P_FinInsurS_ToT": [100],
            "P_RentHirREserv_ToT": [20],
            "P_ProScieTechServ_ToT": [100],
            "P_AdminSupServ_ToT": [20],
            "P_PubAdmiSafety_ToT": [20],
        })
        g53c_df = pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "P_EducTrain_ToT": [80],
            "P_HealthCareSocA_ToT": [80],
            "P_ArtRecServ_ToT": [20],
            "P_OthServ_ToT": [20],
            "P_ToT_ToT": [840],  # sum of all above = 840
        })
        g53 = g53b_df.merge(g53c_df, on="SA2_CODE_2021")
        profile = _compute_industry_profile(g53, _SA2_VIC1)
        assert sum(profile.values()) == pytest.approx(1.0, abs=0.01)

    def test_industry_zero_total_returns_empty(self):
        g53 = pd.DataFrame({
            "SA2_CODE_2021": [_SA2_VIC1],
            "P_ToT_ToT": [0],
        })
        result = _compute_industry_profile(g53, _SA2_VIC1)
        assert result == {}

    def test_missing_sa2_returns_none(self):
        df = pd.DataFrame({"SA2_CODE_2021": ["999999999"], "Tot_P_P": [100]})
        assert _compute_young_pct(df, "000000000") is None
