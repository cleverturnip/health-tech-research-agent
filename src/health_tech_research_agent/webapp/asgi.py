"""ASGI entrypoint for deployment: `uvicorn health_tech_research_agent.webapp.asgi:app`.

Reads config from environment secrets (`WebConfig.from_env`). Phase-1 Step 1 wires the DEMO fixture source
(offline sample data); Step 2 swaps in the Google-backed source that runs `dashboard.build_dashboard`.
Importing this module requires `HTRA_SESSION_SECRET` + `HTRA_PASSWORD_HASH` to be set.
"""

from __future__ import annotations

from pathlib import Path

from .app import create_app
from .config import WebConfig
from .source import FixtureDashboardSource

# TODO(Step 2): replace with the Google-backed source (build_dashboard over the Sheet + Drive data).
_FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sample_ledger.jsonl"

app = create_app(WebConfig.from_env(), FixtureDashboardSource(_FIXTURE))
