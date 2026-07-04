"""ASGI entrypoint for deployment: `uvicorn health_tech_research_agent.webapp.asgi:app`.

Reads config from environment secrets (`WebConfig.from_env`). Source selection:
- If `HTRA_DRIVE_FOLDER_ID` is set -> the Google-backed source (real Sheet + Drive data, `build_dashboard`).
- Otherwise -> the offline DEMO fixture source (sample data), so the app still runs before Google is configured.

Importing this module requires `HTRA_SESSION_SECRET` + `HTRA_PASSWORD_HASH`; the Google source additionally
requires `HTRA_DRIVE_FOLDER_ID` + credentials (see `gsource.GoogleSourceConfig.from_env`).
"""

from __future__ import annotations

import os
from pathlib import Path

from .app import create_app
from .config import WebConfig
from .source import DashboardSource

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "sample_ledger.jsonl"
_TAXONOMY_DIR = _REPO_ROOT / "taxonomy"


def build_source(env: dict | None = None) -> DashboardSource:
    env = os.environ if env is None else env
    if env.get("HTRA_DRIVE_FOLDER_ID"):
        from .gsource import GoogleDashboardSource, GoogleSourceConfig
        taxonomy = str(_TAXONOMY_DIR) if _TAXONOMY_DIR.exists() else None
        return GoogleDashboardSource(GoogleSourceConfig.from_env(env), taxonomy_dir=taxonomy)
    from .source import FixtureDashboardSource
    return FixtureDashboardSource(_FIXTURE)


app = create_app(WebConfig.from_env(), build_source())
