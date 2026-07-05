"""Shared app chrome — the unified top nav (tabs), the research status strip, and the dashboard Refresh control.

Injected by the app layer into every authenticated page (all pages share `<div class="wrap">`), so the three
tabs, the "Research running…" strip, and Log out are consistent everywhere. Option A (light header) — a white
bar with the active tab underlined in the brand cyan; distinct from the navy content blocks below it.
"""

from __future__ import annotations

import html as _html
from typing import Any

_TABS = (("dashboard", "/", "Career Dashboard"),
         ("discovery", "/discover", "Company Discovery"),
         ("review", "/review", "Review Pipeline"))

_TABLER = ('<link rel="stylesheet" '
           'href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.17.0/dist/tabler-icons.min.css">')

NAV_CSS = """
.navbar{background:#fff;border:1px solid rgba(20,60,90,.11);border-radius:14px;margin:2px 0 14px;padding:0 6px 0 8px;
display:flex;align-items:center;justify-content:space-between;box-shadow:var(--shadow);
font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
.navtabs{display:flex}
.navtab{position:relative;display:flex;align-items:center;padding:17px 16px;font-size:14px;font-weight:600;
color:#54636f;text-decoration:none}
.navtab:hover{color:#144C6F}
.navtab.active{color:#144C6F}
.navtab.active::after{content:'';position:absolute;left:12px;right:12px;bottom:-1px;height:3px;
border-radius:3px 3px 0 0;background:#06C4BD}
.navlogout{font:inherit;font-size:12.5px;font-weight:600;background:#fff;border:1px solid rgba(20,60,90,.20);
border-radius:8px;padding:7px 13px;color:#54636f;cursor:pointer}
.navlogout:hover{color:#144C6F;border-color:rgba(20,60,90,.35)}
.refreshbar{display:flex;justify-content:flex-end;margin:0 0 14px}
.refreshbtn{font:inherit;font-size:12.5px;font-weight:600;background:#144C6F;border:1px solid #144C6F;
border-radius:8px;padding:8px 14px;color:#fff;cursor:pointer}
.runstrip{display:flex;align-items:center;gap:8px;border-radius:11px;margin:0 0 14px;padding:10px 14px;
font-size:12.5px;font-weight:600;text-decoration:none}
.runstrip.running{background:#D6F4F2;color:#0A8F89}
.runstrip.done{background:#DCF3E4;color:#1E7A3E}
.runstrip.failed{background:#FBEBEB;color:#791F1F}
.runstrip .arrow{margin-left:auto}
"""

# Overlay + the Refresh form (dashboard only — folded out of the global nav into the dashboard section).
REFRESH_BAR = (
    '<div id="htra-ov" style="display:none;position:fixed;inset:0;z-index:99998;background:rgba(20,60,90,.42);'
    'align-items:center;justify-content:center;font-family:system-ui,sans-serif">'
    '<div style="background:#fff;padding:16px 24px;border-radius:12px;box-shadow:0 10px 34px rgba(0,0,0,.25);'
    'font-size:14px;color:#144C6F;font-weight:700">&#8635; Refreshing from Google…</div></div>'
    '<div class="refreshbar"><form method="post" action="/refresh" style="margin:0" '
    'onsubmit="document.getElementById(\'htra-ov\').style.display=\'flex\'">'
    '<button type="submit" class="refreshbtn">&#8635; Refresh</button></form></div>')


def _esc(value: Any) -> str:
    return _html.escape("" if value is None else str(value))


def _run_strip(run_status: dict | None) -> str:
    """The slim 'Research running…' / last-run strip shown under the tabs on every page while relevant."""
    state = (run_status or {}).get("state")
    if state == "running":
        current = _esc(run_status.get("current_company") or "starting…")
        done = int(run_status.get("completed", 0) or 0) + int(run_status.get("reused", 0) or 0)
        total = _esc(run_status.get("total", 0))
        return (f'<a class="runstrip running" href="/research"><i class="ti ti-loader-2"></i> '
                f'Research running — {current} ({done}/{total}) <span class="arrow">View &rarr;</span></a>')
    if state == "done":
        return ('<a class="runstrip done" href="/research"><i class="ti ti-circle-check"></i> '
                'Last research run complete <span class="arrow">View &rarr;</span></a>')
    if state == "failed":
        return ('<a class="runstrip failed" href="/research"><i class="ti ti-alert-triangle"></i> '
                'Last research run failed <span class="arrow">View &rarr;</span></a>')
    return ""


def nav_bar(active: str | None, run_status: dict | None = None) -> str:
    tabs = "".join(
        f'<a class="navtab{" active" if key == active else ""}" href="{href}">{label}</a>'
        for key, href, label in _TABS)
    header = (f'<header class="navbar"><nav class="navtabs">{tabs}</nav>'
              '<form method="post" action="/logout" style="margin:0">'
              '<button class="navlogout" type="submit">Log out</button></form></header>')
    return header + _run_strip(run_status)


def inject(doc: str, *, active: str | None, run_status: dict | None = None, after_nav: str = "") -> str:
    """Insert the nav CSS (+ icon font) into <head> and the nav bar (+ optional dashboard Refresh) at the top of
    the page's `.wrap`. Works uniformly for every page — they all open `<body><div class="wrap">`."""
    head = f"<style>{NAV_CSS}</style>"
    if "tabler-icons" not in doc:
        head = _TABLER + head
    doc = doc.replace("</head>", head + "</head>", 1)
    return doc.replace('<div class="wrap">',
                       '<div class="wrap">' + nav_bar(active, run_status) + after_nav, 1)
