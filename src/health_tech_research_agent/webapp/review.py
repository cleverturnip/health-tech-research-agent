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
from urllib.parse import quote

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
    + reason ONLY; scores/gates/model_priority never touched (Rule 6/8). History appended by `apply_decisions`.
    Also stamps `decision.decided_date` on THIS company (even an unchanged Accept) so the list can mark it done
    (green). `decided_date` = 'you reviewed this'; the §1a `reviewed_date` is still stamped only by `finalize`."""
    today = date.today().isoformat()
    decision = {"company": company, "human_override": tier or "", "override_reason": reason or ""}
    merged = ledger.apply_decisions(entries, [decision], decided_date=today, decided_at_gate="gate2_inapp")
    key = str(company).strip().lower()
    for entry in merged:
        if str(entry.get("company", "")).strip().lower() == key:
            entry.setdefault("decision", {})["decided_date"] = today
            entry["decision"]["decided_at_gate"] = "gate2_inapp"
    return merged


def _recommendation_html(entry: dict) -> str:
    """The 'why this recommendation' write-up — assembled from the deterministic drivers already in the ledger:
    `recommended_action` + each flag's `note` + the floor-rule reason (Rule 7: the recommendation is deterministic,
    so the explanation is these signals, not a separate prose field). See specs/FRONT_END_PHASE2_GATE2_REVIEW.md §2a."""
    rec = _esc(entry.get("recommended_action") or "normal").replace("_", " ")
    floor = entry.get("scoring", {}).get("floor_rule", {})
    lines = []
    if not floor.get("passed") and floor.get("reason"):
        lines.append("Floor rule — " + str(floor["reason"]))
    lines += [f'{f.get("type")}: {f.get("note")}' for f in entry.get("flags", []) if f.get("note")]
    items = "".join(f"<li>{_esc(line)}</li>" for line in lines) or "<li>No flags fired — a routine confirm.</li>"
    return (f'<div class="reccard"><div class="dh">Recommendation: <b>{rec}</b> '
            f'<span class="src">— why the model routed it here (from its flags + floor rule)</span></div>'
            f'<ul class="reclist">{items}</ul></div>')


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
.rvtbl a{color:var(--accent-ink);text-decoration:none;font-weight:600}
.gtbl tr.done td{background:#E4F2E0}.gtbl tr.done td:first-child{box-shadow:inset 3px 0 0 #4CA32B}
.reccard{background:var(--surface-1);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:var(--radius);padding:12px 15px;margin-top:14px}
.reccard .dh{font-size:12.5px;color:var(--navy);font-weight:600}
.reclist{margin:8px 0 0;padding-left:18px;font-size:12.5px;color:var(--text-secondary);line-height:1.6}
.decision{background:var(--surface-2);border:1px solid var(--border);border-top:3px solid var(--accent);border-radius:14px;padding:16px 18px;margin-top:14px;box-shadow:var(--shadow)}
.decision .dh{font-size:13px;font-weight:700;color:var(--navy);margin-bottom:4px}
.decision .dsub{font-size:12px;color:var(--text-secondary);margin-bottom:12px}
.dbtns{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.dbtn{font:inherit;font-size:13px;font-weight:600;border-radius:9px;padding:9px 15px;cursor:pointer;border:1px solid var(--border-strong);background:var(--surface-2);color:var(--navy);transition:.1s}
.dbtn:hover{border-color:var(--accent);color:var(--accent-ink)}
.dbtn.accept{background:var(--navy);color:#fff;border-color:var(--navy)}
.dbtn.ovr{min-width:46px}
.dbtn.opt.sel{background:var(--navy);color:#fff;border-color:var(--navy)}
.dbtn[disabled]{opacity:.45;cursor:not-allowed}
.dsep{color:var(--text-muted);font-size:12px;padding:0 2px}
.dreason{font:inherit;font-size:13px;padding:10px 12px;border:1px solid var(--border-strong);border-radius:9px;width:100%;min-height:72px;resize:vertical;display:block;margin-top:12px;box-sizing:border-box;line-height:1.5}
"""


def render_index(records: list[dict], entry_by_company: dict) -> str:
    """The review list: one row per un-finalized company, SORTED BY FINAL SCORE (desc), with the score as a
    column; a row turns green once you've decided it (`decision.decided_date`)."""
    def score_key(rec):
        rank = rec.get("final_priority_rank")
        return rank if isinstance(rank, (int, float)) else -1.0

    rows, done = "", 0
    for rec in sorted(records, key=score_key, reverse=True):
        e = entry_by_company.get(rec["company"].lower(), {})
        rec_action = _esc(e.get("recommended_action") or "normal")
        decision = e.get("decision") or {}
        override = decision.get("human_override")
        decided = bool(decision.get("decided_date"))
        done += 1 if decided else 0
        if override:
            dcell = f'<span class="pill {dashboard_html._TIER_CLASS.get(override, "p3")}">{_esc(override)}</span>'
        else:
            dcell = '<span class="muted">accepted</span>' if decided else '<span class="muted">—</span>'
        done_cls = " done" if decided else ""
        href = "/review/" + quote(rec["company"])
        rows += (
            f'<tr class="clickrow{done_cls}" data-co="1" onclick="location.href=\'{href}\'">'
            f'<td>{_esc(rec["company"])}</td><td><b>{_cell(rec.get("final_display"))}</b></td>'
            f'<td>{dashboard_html._pill(rec["model_priority"])}</td>'
            f'<td><span class="rvrec rec-{rec_action}">{rec_action.replace("_", " ")}</span></td>'
            f'<td>{dcell}</td><td>{_esc(rec["model"])}</td><td>{_esc(rec["stage"])}</td></tr>')

    total = len(records)
    if total == 0:
        body_inner = '<div class="src" style="margin-top:8px">Nothing pending review — every company in the ledger is finalized. New companies appear here after the next research batch.</div>'
    else:
        head = ('<tr><th>Company</th><th>Score</th><th>Model priority</th><th>Recommendation</th>'
                '<th>Your decision</th><th>Model</th><th>Stage</th></tr>')
        body_inner = (f'<div class="sheet"><div class="tablewrap rvtbl"><table class="gtbl">{head}{rows}</table></div></div>'
                      '<form method="post" action="/review/finalize" style="margin-top:16px">'
                      '<button type="submit" class="dbtn accept">Finalize review &rarr; send to dashboard</button>'
                      '<span class="dsub" style="margin-left:10px">Stamps every company reviewed and moves them into the dashboard.</span></form>')

    header = (f'<div class="rvtop"><div class="apptitle" style="color:var(--navy)">GATE-2 Review</div>'
              f'<div><a class="dbtn" href="/">&larr; Dashboard</a></div></div>'
              f'<div class="dsub">{done} of {total} decided &mdash; click a row to open its card, accept or override the priority, then finalize.</div>')
    return _page("GATE-2 Review", header + body_inner)


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return _esc(text) if text.strip() else "&nbsp;"


def render_card(record: dict, entry: dict) -> str:
    """A single review card: the dashboard detail body + the recommendation write-up + the priority decision
    control (pick a tier/accept, then Save — nothing submits until Save, so a reason is never lost)."""
    model = entry.get("model_priority")
    decision = entry.get("decision") or {}
    current = decision.get("human_override")
    reason = decision.get("override_reason") or ""
    decided = bool(decision.get("decided_date"))
    company = record["company"]

    def _opt(value, label, base):
        selected = (value == current) or (value == "accept" and decided and not current)
        return (f'<button type="button" class="dbtn opt {base}{" sel" if selected else ""}" '
                f'onclick="rvpick(this,\'{value}\')">{label}</button>')

    opts = (_opt("accept", f"Accept {_esc(model)}", "accept") + '<span class="dsep">or override &rarr;</span>'
            + "".join(_opt(t, t, "ovr") for t in PRIORITY_TIERS))
    initial = current or ("accept" if decided else "")
    save_disabled = "" if initial else " disabled"

    control = (
        f'<form method="post" action="/review/decision" class="decision">'
        f'<input type="hidden" name="company" value="{_esc(company)}">'
        f'<input type="hidden" id="rv-action" name="action" value="{_esc(initial)}">'
        f'<div class="dh">Your decision — priority only</div>'
        f'<div class="dsub">Model priority <b>{_esc(model)}</b>'
        f'{" · currently overridden to <b>" + _esc(current) + "</b>" if current else ""}</div>'
        f'<div class="dbtns">{opts}</div>'
        f'<textarea class="dreason" name="reason" placeholder="reason (strongly encouraged, not required)">'
        f'{_esc(reason)}</textarea>'
        f'<div style="margin-top:12px"><button type="submit" id="rv-save" class="dbtn accept"{save_disabled}>'
        f'Save decision</button></div></form>'
        '<script>function rvpick(el,val){document.getElementById("rv-action").value=val;'
        'document.querySelectorAll(".dbtn.opt").forEach(function(b){b.classList.remove("sel");});'
        'el.classList.add("sel");document.getElementById("rv-save").disabled=false;}</script>')

    crumb = ('<div class="rvtop"><div class="crumb"><a href="/review">'
             '<i class="ti ti-arrow-left"></i> GATE-2 Review</a> / '
             f'<span style="color:var(--text-primary)">{_esc(company)}</span></div>'
             '<div><a class="dbtn" href="/review">All pending</a></div></div>')
    return _page(f"Review — {company}",
                 crumb + dashboard_html._detail_body(record) + _recommendation_html(entry) + control)
