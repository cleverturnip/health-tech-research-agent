"""Phase 2 — in-app GATE-2 review.

Backend-agnostic helpers over the ledger, plus the review UI. The review card IS the dashboard detail card body
(`dashboard_html._detail_body`) + a priority decision control (Katelynd 2026-07-04). Decisions apply via
`ledger.apply_decisions` (priority-only + history — Rule 6/8) and finalize via `ledger.finalize_gate2_review`;
the app persists the updated ledger through the source's `write_entries` (Drive, or a local demo copy).
"""

from __future__ import annotations

import html
from datetime import date
from typing import Any

from .. import dashboard, dashboard_html, ledger

PRIORITY_TIERS = ("P0", "P1", "P2", "P3")


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


# --- logic ------------------------------------------------------------------

def pending(entries: list[dict]) -> list[dict]:
    """Entries awaiting GATE-2 review — the inverse of the §1a stamp (`ledger.is_reviewed`)."""
    return [e for e in entries if not ledger.is_reviewed(e)]


def review_records(entries: list[dict], research: Any = None, *, taxonomy_dir: Any = None) -> list[dict]:
    """Per-company records for the review — `require_reviewed=False` so un-finalized entries render."""
    return dashboard.build_company_records(entries, research=research, taxonomy_dir=taxonomy_dir,
                                           require_reviewed=False)


def apply_one(entries: list[dict], company: str, tier: str | None, reason: str) -> list[dict]:
    """Apply ONE priority decision on a copy: Accept (tier None -> clears/keeps model) or Override (tier). Priority
    + reason ONLY; scores/gates/model_priority never touched (Rule 6/8). History appended by `apply_decisions`."""
    decision = {"company": company, "human_override": tier or "", "override_reason": reason or ""}
    return ledger.apply_decisions(entries, [decision], decided_date=date.today().isoformat(),
                                  decided_at_gate="gate2_inapp")


def finalize(entries: list[dict]) -> list[dict]:
    """Stamp EVERY entry reviewed (§1a) — the one-time finalize after the batch is reviewed."""
    return ledger.finalize_gate2_review(entries, reviewed_date=date.today().isoformat(),
                                        reviewed_at_gate="gate2_inapp")


# --- rendering --------------------------------------------------------------

def _page(title: str, body: str) -> str:
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{_esc(title)}</title>'
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.17.0/dist/tabler-icons.min.css">'
        f'<style>{dashboard_html._CSS}{_REVIEW_CSS}</style></head><body><div class="wrap">{body}</div></body></html>'
    )


_REVIEW_CSS = """
.rvtop{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.rvrec{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;padding:3px 9px;border-radius:20px}
.rec-review_override{background:#FBEBCF;color:#7A4B06}.rec-accept{background:#DCF3E4;color:#1E7A3E}.rec-normal{background:#E8ECF1;color:#5E7280}
.decision{background:var(--surface-2);border:1px solid var(--border);border-top:3px solid var(--accent);border-radius:14px;padding:16px 18px;margin-top:14px;box-shadow:var(--shadow)}
.decision .dh{font-size:13px;font-weight:700;color:var(--navy);margin-bottom:4px}
.decision .dsub{font-size:12px;color:var(--text-secondary);margin-bottom:12px}
.dbtns{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.dbtn{font:inherit;font-size:13px;font-weight:600;border-radius:9px;padding:9px 15px;cursor:pointer;border:1px solid var(--border-strong);background:var(--surface-2);color:var(--navy)}
.dbtn:hover{border-color:var(--accent);color:var(--accent-ink)}
.dbtn.accept{background:var(--navy);color:#fff;border-color:var(--navy)}
.dbtn.ovr{min-width:44px}
.dsep{color:var(--text-muted);font-size:12px;padding:0 2px}
.dreason{font:inherit;font-size:13px;padding:9px 12px;border:1px solid var(--border-strong);border-radius:9px;flex:1;min-width:220px;margin-top:2px}
.rvtbl a{color:var(--accent-ink);text-decoration:none;font-weight:600}
"""


def render_index(records: list[dict], entry_by_company: dict) -> str:
    """The pending-review list: one row per un-finalized company, sorted with review_override first."""
    order = {"review_override": 0, "normal": 1, "accept": 2}

    def key(rec):
        e = entry_by_company.get(rec["company"].lower(), {})
        return (order.get(e.get("recommended_action"), 9), rec["company"])

    rows = ""
    for rec in sorted(records, key=key):
        e = entry_by_company.get(rec["company"].lower(), {})
        rec_action = _esc(e.get("recommended_action") or "normal")
        override = (e.get("decision") or {}).get("human_override")
        decided = f'<span class="pill {dashboard_html._TIER_CLASS.get(override, "p3")}">{_esc(override)}</span>' if override else '<span class="muted">—</span>'
        rows += (
            f'<tr data-co="x"><td>{_esc(rec["company"])}</td>'
            f'<td>{dashboard_html._pill(rec["model_priority"])}</td>'
            f'<td><span class="rvrec rec-{rec_action}">{rec_action.replace("_", " ")}</span></td>'
            f'<td>{decided}</td><td>{_esc(rec["model"])}</td><td>{_esc(rec["stage"])}</td>'
            f'<td><a href="/review/{_esc(rec["company"])}">Review &rarr;</a></td></tr>')

    total = len(records)
    if total == 0:
        body_inner = '<div class="src" style="margin-top:8px">Nothing pending review — every company in the ledger is finalized. New companies appear here after the next research batch.</div>'
    else:
        head = ('<tr><th>Company</th><th>Model priority</th><th>Recommendation</th><th>Your decision</th>'
                '<th>Model</th><th>Stage</th><th></th></tr>')
        body_inner = (f'<div class="sheet"><div class="tablewrap rvtbl"><table class="gtbl">{head}{rows}</table></div></div>'
                      '<form method="post" action="/review/finalize" style="margin-top:16px">'
                      '<button type="submit" class="dbtn accept">Finalize review &rarr; send to dashboard</button>'
                      '<span class="dsub" style="margin-left:10px">Stamps every company reviewed and moves them into the dashboard.</span></form>')

    header = (f'<div class="rvtop"><div class="apptitle" style="color:var(--navy)">GATE-2 Review</div>'
              f'<div><a class="dbtn" href="/">&larr; Dashboard</a></div></div>'
              f'<div class="dsub">{total} companc{"y" if total == 1 else "ies"} pending review — accept the model\'s '
              f'priority or override it, then finalize.</div>')
    return _page("GATE-2 Review", header + body_inner)


def render_card(record: dict, entry: dict) -> str:
    """A single review card: the dashboard detail body + the priority decision control."""
    model = entry.get("model_priority")
    rec_action = entry.get("recommended_action") or "normal"
    current = (entry.get("decision") or {}).get("human_override")
    reason = (entry.get("decision") or {}).get("override_reason") or ""
    company = record["company"]

    def _ovr(t):
        sel = ' style="border-color:var(--accent);color:var(--accent-ink)"' if current == t else ''
        return f'<button type="submit" name="action" value="{t}" class="dbtn ovr"{sel}>{t}</button>'

    ovr = "".join(_ovr(t) for t in PRIORITY_TIERS)
    control = (
        f'<form method="post" action="/review/decision" class="decision">'
        f'<input type="hidden" name="company" value="{_esc(company)}">'
        f'<div class="dh">Your decision — priority only</div>'
        f'<div class="dsub">Model priority <b>{_esc(model)}</b> · recommendation '
        f'<span class="rvrec rec-{_esc(rec_action)}">{_esc(rec_action).replace("_", " ")}</span>'
        f'{" · currently overridden to <b>" + _esc(current) + "</b>" if current else ""}</div>'
        f'<div class="dbtns"><button type="submit" name="action" value="accept" class="dbtn accept">'
        f'Accept {_esc(model)}</button><span class="dsep">or override &rarr;</span>{ovr}</div>'
        f'<input class="dreason" name="reason" placeholder="reason (strongly encouraged, not required)" '
        f'value="{_esc(reason)}"></form>')

    crumb = ('<div class="rvtop"><div class="crumb"><a href="/review">'
             '<i class="ti ti-arrow-left"></i> GATE-2 Review</a> / '
             f'<span style="color:var(--text-primary)">{_esc(company)}</span></div>'
             '<div><a class="dbtn" href="/review">All pending</a></div></div>')
    return _page(f"Review — {company}", crumb + dashboard_html._detail_body(record) + control)
