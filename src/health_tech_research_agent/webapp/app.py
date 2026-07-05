"""The FastAPI app — password login, session gate, and serving/refreshing the dashboard render.

`create_app(config, source)` is a factory (so tests inject a config + a fixture source); the deployed ASGI app
is built in `asgi.py` from `WebConfig.from_env()`. Routes:
- `GET  /healthz`  — unauthenticated health check (for Render).
- `GET  /login`    — the login form (redirects to `/` if already signed in).
- `POST /login`    — verify the password; on success set the session and redirect to `/`.
- `POST /logout`   — clear the session.
- `GET  /`         — gated; renders the dashboard (with a fixed Refresh / Log out control bar).
- `POST /refresh`  — gated; rebuilds the source, then redirects back to `/`.
"""

from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER, HTTP_401_UNAUTHORIZED

from datetime import date

from . import gate1 as gate1_mod
from . import review as review_mod
from .config import WebConfig
from .security import verify_password
from .source import DashboardSource

_SESSION_KEY = "authed"


class PursueIn(BaseModel):
    company: str
    pursue: bool


class DiscoverMessageIn(BaseModel):
    conversation: list[dict]


class DiscoverApproveIn(BaseModel):
    candidates: list[dict]


# Enables the (otherwise read-only) pursue checkboxes and wires each to POST /pursue → reload so the Pursuit tab
# reflects it. Injected ONLY when the source supports editing (the Google source); the demo source stays read-only.
_PURSUE_JS = (
    "<script>(function(){"
    "document.querySelectorAll('tr[data-company] td.mycol input[type=checkbox]').forEach(function(cb){"
    "cb.disabled=false;cb.style.cursor='pointer';cb.title='Pursue / un-pursue (saves to your Sheet)';"
    "cb.addEventListener('click',function(ev){ev.stopPropagation();"
    "var company=cb.closest('tr').getAttribute('data-company');var want=cb.checked;cb.disabled=true;"
    "fetch('/pursue',{method:'POST',headers:{'Content-Type':'application/json'},"
    "body:JSON.stringify({company:company,pursue:want})})"
    ".then(function(r){if(!r.ok)throw 0;return r.json();}).then(function(){location.reload();})"
    ".catch(function(){cb.checked=!want;cb.disabled=false;"
    "alert('Could not save pursue — does the app have edit access to your Sheet?');});});});})();</script>"
)

_BTN = ("font:inherit;font-size:12.5px;font-weight:600;background:#fff;border:1px solid rgba(20,60,90,.22);"
        "border-radius:8px;padding:7px 13px;cursor:pointer;color:#144C6F")
_BTN_PRIMARY = ("font:inherit;font-size:12.5px;font-weight:600;background:#144C6F;border:1px solid #144C6F;"
                "border-radius:8px;padding:7px 13px;cursor:pointer;color:#fff")
_CONTROLS = (
    '<div id="htra-ov" style="display:none;position:fixed;inset:0;z-index:99998;background:rgba(20,60,90,.42);'
    'align-items:center;justify-content:center;font-family:system-ui,sans-serif">'
    '<div style="background:#fff;padding:16px 24px;border-radius:12px;box-shadow:0 10px 34px rgba(0,0,0,.25);'
    'font-size:14px;color:#144C6F;font-weight:700">&#8635; Refreshing from Google…</div></div>'
    '<div style="position:fixed;top:12px;right:16px;z-index:99999;display:flex;gap:8px;'
    'font-family:system-ui,sans-serif">'
    '<form method="post" action="/refresh" style="margin:0" '
    'onsubmit="document.getElementById(\'htra-ov\').style.display=\'flex\'">'
    f'<button type="submit" style="{_BTN_PRIMARY}">&#8635; Refresh</button></form>'
    f'<a href="/discover" style="{_BTN};text-decoration:none;display:inline-block">GATE-1 Discovery</a>'
    f'<a href="/review" style="{_BTN};text-decoration:none;display:inline-block">GATE-2 Review</a>'
    f'<form method="post" action="/logout" style="margin:0"><button type="submit" style="{_BTN}">'
    'Log out</button></form></div>'
)


def _login_page(*, error: str = "", title: str = "Health-tech dashboard") -> str:
    err = f'<p class="err">{error}</p>' if error else ""
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Sign in</title><style>'
        'body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:#faf9f5;color:#2C2C2A;'
        'display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}'
        '.box{background:#fff;border:.5px solid rgba(0,0,0,.12);border-radius:12px;padding:28px 30px;width:300px;'
        'box-shadow:0 1px 3px rgba(0,0,0,.06)}'
        'h1{font-size:16px;margin:0 0 4px}p.sub{font-size:12.5px;color:#5F5E5A;margin:0 0 18px}'
        'input{width:100%;box-sizing:border-box;font:inherit;padding:9px 11px;'
        'border:.5px solid rgba(0,0,0,.18);border-radius:8px;margin-bottom:12px}'
        'button{width:100%;font:inherit;background:#2C2C2A;color:#fff;border:none;border-radius:8px;padding:9px;'
        'cursor:pointer}.err{color:#791F1F;font-size:12.5px;margin:0 0 12px}'
        '</style></head><body><form class="box" method="post" action="/login">'
        f'<h1>{title}</h1><p class="sub">Private &mdash; sign in to continue.</p>{err}'
        '<input type="password" name="password" placeholder="Password" autofocus '
        'autocomplete="current-password">'
        '<button type="submit">Sign in</button></form></body></html>'
    )


def _with_controls(html_doc: str, *, editable: bool = False) -> str:
    """Inject the fixed Refresh / Log out bar (and, when the source is editable, the pursue-checkbox script) into
    the engine's HTML. The engine's render stays untouched — the interactivity is added here, at the app layer."""
    bar = _CONTROLS + (_PURSUE_JS if editable else "")
    if "</body>" in html_doc:
        return html_doc.replace("</body>", bar + "</body>", 1)
    return html_doc + bar


def create_app(config: WebConfig, source: DashboardSource) -> FastAPI:
    app = FastAPI(title=config.title)
    app.add_middleware(
        SessionMiddleware, secret_key=config.session_secret,
        https_only=config.secure_cookie, same_site="lax",
    )

    def _authed(request: Request) -> bool:
        return bool(request.session.get(_SESSION_KEY))

    @app.get("/healthz", response_class=PlainTextResponse)
    def healthz() -> str:
        return "ok"

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request) -> HTMLResponse:
        if _authed(request):
            return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
        return HTMLResponse(_login_page(title=config.title))

    @app.post("/login")
    def login_submit(request: Request, password: str = Form(default="")):
        if verify_password(password, config.password_hash):
            request.session[_SESSION_KEY] = True
            return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
        return HTMLResponse(_login_page(error="Incorrect password.", title=config.title),
                            status_code=HTTP_401_UNAUTHORIZED)

    @app.post("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        if not _authed(request):
            return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
        return HTMLResponse(_with_controls(source.html(), editable=hasattr(source, "set_pursue")))

    @app.post("/refresh")
    def refresh(request: Request):
        if not _authed(request):
            return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
        source.refresh()
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    @app.post("/pursue")
    def pursue(request: Request, body: PursueIn):
        if not _authed(request):
            return JSONResponse({"error": "unauthorized"}, status_code=HTTP_401_UNAUTHORIZED)
        setter = getattr(source, "set_pursue", None)
        if setter is None:
            return JSONResponse({"error": "editing not available for this source"}, status_code=400)
        if not setter(body.company, body.pursue):
            return JSONResponse({"error": "save failed read-back validation"}, status_code=500)
        return JSONResponse({"ok": True, "company": body.company, "pursue": body.pursue})

    # --- GATE-2 review (Phase 2) — reads pending entries; decisions write the ledger back to the store ---
    def _review_ok() -> bool:
        return hasattr(source, "read_review_data") and hasattr(source, "write_entries")

    def _norm(name) -> str:
        return str("" if name is None else name).strip().lower()

    @app.get("/review", response_class=HTMLResponse)
    def review_index(request: Request):
        if not _authed(request):
            return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
        if not _review_ok():
            return HTMLResponse("Review is not available for this data source.", status_code=400)
        entries, research = source.read_review_data()
        recs = review_mod.review_records(review_mod.pending(entries), research=research,
                                         taxonomy_dir=getattr(source, "taxonomy_dir", None))
        return HTMLResponse(review_mod.render_index(recs, {_norm(e.get("company")): e for e in entries}))

    @app.get("/review/{company}", response_class=HTMLResponse)
    def review_card(request: Request, company: str):
        if not _authed(request):
            return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
        if not _review_ok():
            return HTMLResponse("Review is not available for this data source.", status_code=400)
        entries, research = source.read_review_data()
        entry = next((e for e in entries if _norm(e.get("company")) == _norm(company)), None)
        if entry is None:
            return RedirectResponse("/review", status_code=HTTP_303_SEE_OTHER)
        recs = review_mod.review_records([entry], research=research,
                                         taxonomy_dir=getattr(source, "taxonomy_dir", None))
        return HTMLResponse(review_mod.render_card(recs[0], entry))

    @app.post("/review/decision")
    def review_decision(request: Request, company: str = Form(default=""), action: str = Form(default=""),
                        reason: str = Form(default="")):
        if not _authed(request):
            return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
        if not _review_ok() or action not in ("accept",) + review_mod.PRIORITY_TIERS:
            return HTMLResponse("Invalid decision.", status_code=400)
        tier = None if action == "accept" else action
        merged = review_mod.apply_one(source.read_review_data()[0], company, tier, reason)
        if not source.write_entries(merged):
            return HTMLResponse("Save failed read-back validation — decision NOT saved.", status_code=500)
        return RedirectResponse("/review", status_code=HTTP_303_SEE_OTHER)

    @app.post("/review/finalize")
    def review_finalize(request: Request):
        if not _authed(request):
            return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
        if not _review_ok():
            return HTMLResponse("Review is not available for this data source.", status_code=400)
        finalized = review_mod.finalize(source.read_review_data()[0])
        if not source.write_entries(finalized):
            return HTMLResponse("Save failed read-back validation — finalize NOT saved.", status_code=500)
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    # --- GATE-1 discovery (Phase 3) — grounded, conversational candidate discovery; approve writes candidates.csv ---
    def _discover_ok() -> bool:
        return all(hasattr(source, m) for m in ("read_entries", "read_thesis", "write_thesis",
                                                "write_candidates", "openai_client"))

    @app.get("/discover", response_class=HTMLResponse)
    def discover_page(request: Request):
        if not _authed(request):
            return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
        if not _discover_ok():
            return HTMLResponse("Discovery is not available for this data source.", status_code=400)
        entries = source.read_entries()
        return HTMLResponse(gate1_mod.render_page(source.read_thesis(), roster_count=len(entries)))

    @app.post("/discover/thesis")
    def discover_thesis(request: Request, thesis: str = Form(default="")):
        if not _authed(request):
            return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
        if not _discover_ok() or not source.write_thesis(thesis):
            return HTMLResponse("Thesis save failed — not saved.", status_code=500)
        return RedirectResponse("/discover", status_code=HTTP_303_SEE_OTHER)

    @app.post("/discover/message")
    def discover_message(request: Request, body: DiscoverMessageIn):
        if not _authed(request):
            return JSONResponse({"error": "unauthorized"}, status_code=HTTP_401_UNAUTHORIZED)
        if not _discover_ok():
            return JSONResponse({"error": "discovery not available for this source"}, status_code=400)
        conversation = [{"role": "assistant" if t.get("role") == "assistant" else "user",
                         "content": str(t.get("content", ""))}
                        for t in body.conversation if str(t.get("content", "")).strip()][-40:]
        if not conversation:
            return JSONResponse({"error": "empty conversation"}, status_code=400)
        entries = source.read_entries()
        prompt = gate1_mod.build_system_prompt(entries, source.read_thesis(),
                                               taxonomy_dir=getattr(source, "taxonomy_dir", None))
        try:
            out = gate1_mod.discover(source.openai_client(), prompt, conversation)
        except Exception:  # OpenAI/network failure — surface a retryable error, never 500-crash the chat
            return JSONResponse({"error": "assistant call failed"}, status_code=502)
        # Rule 7: deterministically drop any already-researched company the model re-proposed anyway.
        kept, dropped = gate1_mod.drop_researched(out["candidates"], entries)
        out["candidates"] = kept
        if dropped:
            out["reply"] += (f"\n\n(Removed {len(dropped)} already-researched: {', '.join(dropped)}.)")
        return JSONResponse(out)

    @app.post("/discover/approve")
    def discover_approve(request: Request, body: DiscoverApproveIn):
        if not _authed(request):
            return JSONResponse({"error": "unauthorized"}, status_code=HTTP_401_UNAUTHORIZED)
        if not _discover_ok():
            return JSONResponse({"error": "discovery not available for this source"}, status_code=400)
        rows = [{"company": str(c.get("company", "")).strip(), "why": str(c.get("why", "")).strip(),
                 "signal": str(c.get("signal", "")).strip()}
                for c in body.candidates if str(c.get("company", "")).strip()]
        if not rows:
            return JSONResponse({"error": "no candidates"}, status_code=400)
        try:
            filename = source.write_candidates(rows, date_str=date.today().isoformat())
        except Exception:
            return JSONResponse({"error": "save failed read-back validation"}, status_code=500)
        return JSONResponse({"ok": True, "filename": filename, "count": len(rows)})

    return app
