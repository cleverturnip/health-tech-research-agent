"""Web-layer configuration — read from environment secrets at real startup, or constructed directly in tests.

Nothing sensitive is defaulted or committed: the session secret and the password hash MUST come from the
environment (Render secrets) in a deployed run. `from_env` raises a clear error if either is missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

DEFAULT_TITLE = "Katelynd Career Research Dashboard"


@dataclass
class WebConfig:
    session_secret: str          # signs the session cookie (HTRA_SESSION_SECRET)
    password_hash: str           # encoded PBKDF2 hash of the app password (HTRA_PASSWORD_HASH)
    secure_cookie: bool = False  # True in prod (HTTPS on Render); False for local http dev
    title: str = DEFAULT_TITLE
    # Where research-job state (checkpoint / manifest / status) lives — MUST be on the Render persistent disk in
    # prod (HTRA_JOBS_DIR) so a run survives a restart and auto-resumes. Local default is a working dir.
    jobs_dir: str = "/tmp/htra_jobs"
    # Email notification on a finished/failed research run (Resend). All optional — if unset, email is skipped.
    resend_api_key: str = ""     # RESEND_API_KEY (Render secret)
    notify_email: str = ""       # HTRA_NOTIFY_EMAIL — where run notifications go
    resend_from: str = "onboarding@resend.dev"   # HTRA_RESEND_FROM — Resend shared sender by default
    base_url: str = ""           # HTRA_BASE_URL — public URL, for the link in the email

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "WebConfig":
        env = os.environ if env is None else env
        secret = env.get("HTRA_SESSION_SECRET")
        password_hash = env.get("HTRA_PASSWORD_HASH")
        missing = [name for name, val in
                   (("HTRA_SESSION_SECRET", secret), ("HTRA_PASSWORD_HASH", password_hash)) if not val]
        if missing:
            raise RuntimeError(
                "Missing required web config environment variable(s): " + ", ".join(missing)
                + ". Set them as Render secrets (never commit them)."
            )
        secure = str(env.get("HTRA_SECURE_COOKIE", "")).strip().lower() in {"1", "true", "yes"}
        return cls(session_secret=secret, password_hash=password_hash, secure_cookie=secure,
                   title=env.get("HTRA_APP_TITLE", DEFAULT_TITLE),
                   jobs_dir=env.get("HTRA_JOBS_DIR", "/tmp/htra_jobs"),
                   resend_api_key=env.get("RESEND_API_KEY", ""),
                   notify_email=env.get("HTRA_NOTIFY_EMAIL", ""),
                   resend_from=env.get("HTRA_RESEND_FROM", "onboarding@resend.dev"),
                   base_url=env.get("HTRA_BASE_URL", ""))
