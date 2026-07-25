"""Tests for app.core.config's env-var-backed settings."""

from __future__ import annotations

from app.core.config import Settings


def test_show_census_sections_defaults_true():
    assert Settings().SHOW_CENSUS_SECTIONS is True


def test_show_census_sections_respects_env_override(monkeypatch) -> None:
    monkeypatch.setenv("SHOW_CENSUS_SECTIONS", "false")
    assert Settings().SHOW_CENSUS_SECTIONS is False
