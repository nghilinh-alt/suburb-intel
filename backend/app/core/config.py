"""App-wide config flags, backed by env vars.

Small and deliberately minimal — most settings in this codebase are
module-scoped (see app/db/session.py's DatabaseSettings). This one is
app-wide because it's read from the API layer (app/api/suburb.py), not an
ingestion script.
"""

from __future__ import annotations

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    SHOW_CENSUS_SECTIONS: bool = Field(
        default=True,
        description=(
            "Reversible visibility flag for the 2021-Census-sourced sections of the "
            "suburb report (Demographics, Economy, Housing, regional comparison, and "
            "the census-derived fields within Investment Outlook/Transport — see "
            "app/api/suburb.py's _census_field_ids). Defaults True (matches current "
            "behaviour, nothing hidden) so adding this flag doesn't silently change "
            "what's shown — flip to False once the 2021 Census is judged too stale to "
            "lead with. Flipping it back to True restores everything; no data is ever "
            "deleted, this only controls what the frontend renders."
        ),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
