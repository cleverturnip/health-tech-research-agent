"""Email notification for a finished/failed research run (Resend transactional API).

Dependency-free (stdlib urllib) and injectable: the HTTP POST is a `poster` seam so offline tests capture the
payload without sending. A missing API key / recipient is a silent no-op (local dev + demo run without email).
"""

from __future__ import annotations

import html as _html
import json
import logging
import urllib.request
from typing import Any, Callable

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "onboarding@resend.dev"   # Resend's shared sender — no domain setup needed
# Cloudflare (in front of the Resend API) blocks the default "Python-urllib" agent with a 403 (error 1010),
# so a normal User-Agent is REQUIRED — verified 2026-07-05.
_USER_AGENT = "health-tech-research-agent/1.0"


def _http_post(url: str, headers: dict, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=20) as resp:   # noqa: S310 — fixed https endpoint
        return resp.status, resp.read().decode("utf-8", "replace")


def send_email(*, api_key: str, to: str, subject: str, html: str, from_addr: str = DEFAULT_FROM,
               poster: Callable = _http_post) -> bool:
    """POST one email to Resend. Returns True on a 2xx. A missing key/recipient is a no-op (returns False),
    and any transport error is logged and swallowed — a notification failure must never crash the worker."""
    if not api_key or not to:
        logger.info("Email skipped — no Resend API key or recipient configured.")
        return False
    try:
        status, body = poster(RESEND_URL,
                              {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                               "User-Agent": _USER_AGENT},
                              {"from": from_addr, "to": [to], "subject": subject, "html": html})
    except Exception:   # noqa: BLE001
        logger.exception("Resend email send failed")
        return False
    if not 200 <= status < 300:
        logger.warning("Resend returned %s: %s", status, str(body)[:300])
        return False
    return True


def build_run_email(status: dict, base_url: str = "") -> tuple[str, str]:
    """(subject, html) for a finished/failed run."""
    link = (base_url.rstrip("/") + "/research") if base_url else "/research"
    open_link = f'<p><a href="{_html.escape(link)}">Open the research page</a></p>'
    if status.get("state") == "done":
        added = status.get("added", 0)
        subject = f"Research run complete — {added} companies scored"
        html = (f"<p>Your research run finished. <b>{added}</b> newly-scored "
                f"{'company is' if added == 1 else 'companies are'} ready for GATE-2 review.</p>"
                f"<p>{status.get('completed', 0)} researched · {status.get('reused', 0)} reused · "
                f"{status.get('failed', 0)} failed.</p>{open_link}")
        return subject, html
    subject = "Research run failed"
    html = ("<p>Your research run hit a problem and stopped:</p>"
            f"<p><b>{_html.escape(str(status.get('error', '')))}</b></p>"
            "<p>Completed companies were saved; starting a new run re-attempts only what didn't finish.</p>"
            f"{open_link}")
    return subject, html


def send_run_notification(status: dict, *, api_key: str, to: str, from_addr: str = DEFAULT_FROM,
                          base_url: str = "", poster: Callable = _http_post) -> bool:
    """Email the outcome of a finished/failed run. No-op for any other state."""
    if status.get("state") not in ("done", "failed"):
        return False
    subject, html = build_run_email(status, base_url)
    return send_email(api_key=api_key, to=to, subject=subject, html=html, from_addr=from_addr, poster=poster)
