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
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER, HTTP_401_UNAUTHORIZED

from .config import WebConfig
from .security import verify_password
from .source import DashboardSource

_SESSION_KEY = "authed"

_BTN = ("font:inherit;font-size:12.5px;background:#fff;border:.5px solid rgba(0,0,0,.18);"
        "border-radius:8px;padding:6px 12px;cursor:pointer;color:#2C2C2A")
_CONTROLS = (
    '<div style="position:fixed;top:12px;right:16px;z-index:9999;display:flex;gap:8px;'
    'font-family:system-ui,sans-serif">'
    f'<form method="post" action="/refresh" style="margin:0"><button type="submit" style="{_BTN}">'
    '&#8635; Refresh</button></form>'
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


def _with_controls(html_doc: str) -> str:
    """Inject the fixed Refresh / Log out bar into the engine's HTML (the engine stays untouched)."""
    bar = _CONTROLS
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
        return HTMLResponse(_with_controls(source.html()))

    @app.post("/refresh")
    def refresh(request: Request):
        if not _authed(request):
            return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
        source.refresh()
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    return app
