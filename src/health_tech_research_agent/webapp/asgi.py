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


_config = WebConfig.from_env()
_source = build_source()
app = create_app(_config, _source)

# Startup auto-resume (Rule 4): if a research run was mid-flight when the process died/restarted, relaunch it —
# it resumes from the checkpoint (completed companies are reused, not re-researched). No-op if nothing was running.
from . import email as _email  # noqa: E402
from . import research as _research  # noqa: E402


def _resume_notify(status):
    _email.send_run_notification(status, api_key=_config.resend_api_key, to=_config.notify_email,
                                 from_addr=_config.resend_from, base_url=_config.base_url)


_research.resume_if_running(_source, work_dir=_config.jobs_dir, client_factory=_source.openai_client,
                            taxonomy_dir=getattr(_source, "taxonomy_dir", None), on_finish=_resume_notify)
