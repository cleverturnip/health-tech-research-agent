"""
Dashboard HTML render (Phase 5) — the interim review surface.

A pure render of the Phase-2/3 data model (`dashboard.build_company_records` + `merge_user_layer`) into a
self-contained HTML page: the four grid tabs (all companies · pursuit · contacts · segment radar) and a
per-company detail view (click a row). It authors NOTHING — every value comes from the records / user store, so
this same data artifact is what the eventual front end renders (only the presentation is upgraded later,
DASHBOARD_DESIGN.md §7). Layout matches `specs/dashboard_wireframe.html`.

Safety signals from the merge report (changed-since / orphaned) render as banners at the top — an autonomous
segment surfaces problems, never hides them.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import pandas as pd

from . import dashboard as dash
from . import storage

_TIER_CLASS = {"P0": "p0", "P1": "p1", "P2": "p2", "P3": "p3"}


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _slug(company: str) -> str:
    return "co-" + re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")


def _pill(tier: str) -> str:
    return f'<span class="pill {_TIER_CLASS.get(tier, "p3")}">{_esc(tier)}</span>'


def _cell(value: Any) -> str:
    """A grid cell value; blanks/None -> em space so the column stays legible."""
    text = "" if value is None else str(value)
    return _esc(text) if text.strip() else "&nbsp;"


def _pretty(name: Any) -> str:
    """Humanize a snake_case column name for display (underscores -> spaces; the CSS title-cases it)."""
    return str(name).replace("_", " ").strip()


# ---------------------------------------------------------------------------
# grid tabs
# ---------------------------------------------------------------------------

def _all_companies_rows(records: list[dict]) -> str:
    out = []
    for r in records:
        was = f' <span class="was">was {_esc(r["model_priority"])}</span>' if r.get("is_overridden") else ""
        tags = r["tags"]
        slug = _slug(r["company"])
        out.append(
            f'<tr data-co="{slug}" data-company="{_esc(r["company"])}" onclick="selectRow(this,\'{slug}\')">'
            f'<td class="mycol"><input type="checkbox" disabled {"checked" if r.get("pursue") else ""} '
            f'title="Set pursue in your Google Sheet, then Refresh"></td>'
            f'<td>{_esc(r["company"])}</td>'
            f'<td>{_pill(r["final_priority"])}{was}</td>'
            f'<td>{_esc(r["segment_label"])}</td>'
            f'<td>{_esc(r["model"])}</td><td>{_esc(r["stage"])}</td>'
            f'<td>{_cell(r["final_display"])}</td>'
            f'<td><button class="xbtn" title="Open detail" '
            f'onclick="event.stopPropagation();selectRow(this.closest(\'tr\'),\'{slug}\');showDetail(\'{slug}\')">'
            f'<i class="ti ti-layout-sidebar-right-expand"></i></button></td>'
            f'<td class="detail">{_esc("; ".join(tags["subsegment"]))}</td>'
            f'<td class="detail">{_esc("; ".join(tags["product_model"]))}</td>'
            f'<td class="detail">{_esc("; ".join(tags["distribution_model"]))}</td>'
            f'<td class="detail">{_esc("; ".join(tags["data_input"]))}</td>'
            f'<td class="detail">{_cell(r["bg_display"])}</td>'
            f'<td class="detail">{_cell(r["scores"]["pmf"])}</td>'
            f'<td class="detail">{_cell(r["scores"]["arr"])}</td>'
            f'<td class="detail">{_cell(r["scores"]["growth"])}</td>'
            f'<td class="detail">{_cell(r["scores"]["strain"])}</td>'
            f'</tr>')
    return "".join(out)


def _df_table(df: pd.DataFrame, group_label: str) -> str:
    heads = "".join(f"<th>{_esc(_pretty(c))}</th>" for c in df.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_cell(v)}</td>" for v in row) + "</tr>"
        for row in df.itertuples(index=False, name=None))
    return (f'<table class="gtbl"><tr class="grouphdr"><th class="grp-ledger" colspan="{len(df.columns)}">'
            f'{_esc(group_label)}</th></tr><tr>{heads}</tr>{body}</table>')


# ---------------------------------------------------------------------------
# per-company detail view (scoring + research levers, from the record)
# ---------------------------------------------------------------------------

def _row(label: str, value: str, strong: bool = False) -> str:
    cls = "v s" if strong else "v"
    return f'<div class="r"><span class="k">{_esc(label)}</span><span class="{cls}">{value}</span></div>'


def _lever_card(title: str, chip: str, rows: str) -> str:
    return (f'<div class="lc"><div class="lch"><span class="lct">{_esc(title)}</span>'
            f'<span class="ls">{_esc(chip)}</span></div>{rows}</div>')


def _detail_html(r: dict) -> str:
    s = r["scores"]
    scoring = r.get("scoring", {})
    gates = r.get("gates", {})
    res = r.get("research") or {}
    was = f' <span class="pill p3" style="opacity:.8">model: {_esc(r["model_priority"])}</span>' \
        if r.get("is_overridden") else ""

    score_boxes = "".join(
        f'<div class="sbox"><div class="l">{_esc(lbl)}</div><div class="v">{_cell(val)}</div></div>'
        for lbl, val in [("background fit", r["bg_display"]), ("PMF", s["pmf"]), ("ARR", s["arr"]),
                         ("growth", s["growth"]), ("strain", s["strain"]), ("FINAL", r["final_display"])])

    ov = ""
    if r.get("override"):
        o = r["override"]
        ov = (f'<div class="ov"><b>Your override → {_esc(o["to"])}:</b> {_esc(o["reason"])} '
              f'<span class="src">(model said {_esc(o["from"])})</span></div>')

    bg_rat = _esc(scoring.get("bg_fit", {}).get("rationale"))
    floor = _esc(scoring.get("floor_rule", {}).get("reason"))
    why = f'<div class="why"><div>{bg_rat}</div><div>Floor rule: {floor}</div></div>' if (bg_rat or floor) else ""

    # gate cards
    path = gates.get("path", {})
    agency = gates.get("agency", {})
    class_rows = (_row("model", _esc(r["model"]))
                  + _row("PATH", ("pass" if path.get("passed") else "floored") + " — " + _esc(path.get("detail")), True)
                  + (_row("channel", _esc(res.get("commercial", {}).get("business_model_type")))
                     if res.get("commercial", {}).get("business_model_type") else ""))
    fund_rows = _row("stage", _esc(r["stage"]), True) + _row("agency", _esc(agency.get("detail")))
    if res.get("maturity", {}).get("total_funding"):
        fund_rows += _row("total raised", _esc(res["maturity"]["total_funding"]))

    gate_cards = (_lever_card("classification & channel", "drives PATH", class_rows)
                  + _lever_card("funding & maturity", "drives agency", fund_rows))

    # score cards
    com = res.get("commercial", {})
    pmf_rows = _row("ARR / growth", f'{_cell(s["arr"])} / {_cell(s["growth"])}', True)
    if com.get("revenue_or_arr"):
        pmf_rows += _row("revenue", _esc(com["revenue_or_arr"]))
    if com.get("growth_signal"):
        pmf_rows += _row("growth", _esc(com["growth_signal"]))
    if com.get("evidence_quality"):
        pmf_rows += _row("evidence", _esc(com["evidence_quality"]) + ' <span class="src">— trust cue</span>')
    bg_rows = _row("cadence", bg_rat or "—", True) + _row("loop", str(scoring.get("bg_fit", {}).get("loop")))
    cap = res.get("capability", {})
    strain_rows = _row("strain", _esc(scoring.get("strain", {}).get("strength")) + f' ({_cell(s["strain"])})', True)
    if cap.get("a2_basis"):
        strain_rows += _row("a2 basis", _esc(cap["a2_basis"]))

    score_cards = (_lever_card("product market fit", "drives ARR + growth", pmf_rows)
                   + _lever_card("background fit", "drives Background Fit", bg_rows)
                   + _lever_card("operator needed", "drives strain", strain_rows))

    # research accordions (only when research is joined)
    research_block = ""
    if r.get("research"):
        facts = "".join(
            f'<div class="fact"><span class="pill cv-ver">verified</span><div>{_esc(f)}</div></div>'
            for f in res.get("verified_facts", []))
        weak = "".join(
            f'<div class="fact"><span class="pill cv-weak">weak</span><div>{_esc(w)}</div></div>'
            for w in res.get("weak_claims", []))
        findings = "".join(
            f'<div class="acc"><div class="ah" onclick="this.parentElement.classList.toggle(\'open\')">'
            f'<i class="ti ti-chevron-right chev"></i> {_esc(name.replace("_finding", "").replace("_", " "))}'
            f'</div><div class="ab"><div class="md">{_esc(text)}</div></div></div>'
            for name, text in res.get("findings", {}).items())
        research_block = (
            '<div class="acc"><div class="ah" onclick="this.parentElement.classList.toggle(\'open\')">'
            '<i class="ti ti-chevron-right chev"></i> verified facts &amp; sources</div>'
            f'<div class="ab">{facts}{weak}</div></div>'
            '<div class="acc"><div class="ah" onclick="this.parentElement.classList.toggle(\'open\')">'
            '<i class="ti ti-chevron-right chev"></i> full findings — raw research text</div>'
            f'<div class="ab">{findings}</div></div>')
    else:
        research_block = '<div class="src" style="margin-top:10px">No research joined for this company.</div>'

    return (
        f'<div class="detailco" id="{_slug(r["company"])}" style="display:none">'
        f'<div class="crumb"><a href="#" onclick="showGrid();return false;"><i class="ti ti-arrow-left"></i> '
        f'all companies</a> / <span style="color:var(--text-primary)">{_esc(r["company"])}</span></div>'
        f'<div class="hd"><h3>{_esc(r["company"])}</h3>{_pill(r["final_priority"])}{was}'
        f'<span style="color:var(--text-secondary);font-size:12.5px">{_esc(r["segment_label"])} · '
        f'{_esc(r["model"])} · {_esc(r["stage"])}</span></div>'
        f'<div class="card"><p class="ct">SCORING &amp; DECISION — from the ledger (write-once)</p>'
        f'<div class="scores">{score_boxes}</div>{why}{ov}</div>'
        f'<div class="card"><p class="ct">RESEARCH EVIDENCE — at a glance (each card = a scoring lever)</p>'
        f'<div class="glabel">the gates — a fail here caps priority at P3</div>'
        f'<div class="cgrid cg2">{gate_cards}</div>'
        f'<div class="glabel">the score — background fit + PMF + strain = FINAL</div>'
        f'<div class="cgrid cg3">{score_cards}</div>{research_block}</div></div>')


# ---------------------------------------------------------------------------
# banners + assembly
# ---------------------------------------------------------------------------

def _banners(report: dict | None) -> str:
    if not report:
        return ""
    out = []
    for c in report.get("changed", []):
        deltas = "; ".join(f"{k} {v['from']}→{v['to']}" for k, v in c.items() if k != "company")
        out.append(f'<div class="banner warn"><i class="ti ti-alert-triangle"></i> '
                   f'{_esc(c["company"])} changed since you last looked — {_esc(deltas)}</div>')
    for company in report.get("orphaned_workspace", []):
        out.append(f'<div class="banner danger"><i class="ti ti-alert-circle"></i> '
                   f'You have notes on {_esc(company)}, but it is no longer in the reviewed ledger.</div>')
    for company in report.get("orphaned_contacts", []):
        out.append(f'<div class="banner danger"><i class="ti ti-alert-circle"></i> '
                   f'You have contacts for {_esc(company)}, but it is no longer in the reviewed ledger.</div>')
    return "".join(out)


_CSS = """
:root{--surface-0:#f6f7f9;--surface-1:#eef0f4;--surface-2:#fff;--text-primary:#1c2128;--text-secondary:#57606a;--text-muted:#9aa1ac;--border:rgba(27,31,40,.09);--border-strong:rgba(27,31,40,.16);--accent:#3a63e8;--accent-soft:#EBF0FE;--radius:10px;--shadow:0 1px 2px rgba(27,31,40,.04),0 6px 20px rgba(27,31,40,.06)}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,system-ui,sans-serif;color:var(--text-primary);background:var(--surface-0);margin:0;padding:28px;line-height:1.5;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.wrap{max-width:1060px;margin:0 auto}
.doc-note{font-size:12.5px;color:var(--text-secondary);background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius);padding:12px 15px;margin-bottom:14px;box-shadow:var(--shadow)}
.banner{font-size:12.5px;border-radius:var(--radius);padding:10px 13px;margin-bottom:8px;border:1px solid transparent}
.banner.warn{background:#FDF4E3;color:#7A4B06;border-color:#F2DCB3}.banner.danger{background:#FCECEC;color:#8A2020;border-color:#F1C9C9}
.topnav{display:flex;gap:8px;margin:14px 0}
.topnav button{font:inherit;font-size:13px;font-weight:500;background:var(--surface-2);border:1px solid var(--border-strong);border-radius:var(--radius);padding:8px 15px;cursor:pointer;color:var(--text-secondary);transition:.12s}
.topnav button:hover{border-color:var(--accent);color:var(--accent)}
.topnav button.active{background:var(--text-primary);color:#fff;border-color:var(--text-primary)}
.pill{font-size:11px;font-weight:600;padding:2px 9px;border-radius:20px;display:inline-block;letter-spacing:.01em}
.p0{background:#E4F2D8;color:#2C5A0C}.p1{background:#E1ECFC;color:#12447F}.p2{background:#FBEBCF;color:#7A4B06}.p3{background:#ECEDF0;color:#585d68}
.was{font-size:11px;color:var(--text-muted);font-weight:400}.muted{color:var(--text-muted)}.src{color:var(--text-muted);font-size:11.5px}
.sheet{border:1px solid var(--border);border-radius:14px;overflow:hidden;background:var(--surface-2);font-size:13px;box-shadow:var(--shadow)}
.tabs{display:flex;gap:4px;padding:6px 8px 0;border-bottom:1px solid var(--border);background:linear-gradient(var(--surface-1),var(--surface-2))}
.tab{padding:9px 15px;font-size:13px;font-weight:500;color:var(--text-secondary);cursor:pointer;border:none;background:none;border-bottom:2px solid transparent;border-radius:6px 6px 0 0;transition:.12s}
.tab:hover{color:var(--text-primary);background:rgba(27,31,40,.03)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}
.toolbar{display:flex;align-items:center;gap:8px;padding:9px 14px;border-bottom:1px solid var(--border);flex-wrap:wrap;background:var(--surface-2)}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;padding:5px 11px;border:1px solid var(--border-strong);border-radius:var(--radius);color:var(--text-primary);background:var(--surface-2);cursor:pointer}
.chip:hover{border-color:var(--accent);color:var(--accent)}
.tablewrap{overflow-x:auto}
table.gtbl{border-collapse:separate;border-spacing:0;width:100%;font-size:12.5px}
.gtbl th{text-align:left;font-weight:600;font-size:11px;letter-spacing:.03em;text-transform:capitalize;color:var(--text-muted);padding:10px;border-bottom:1px solid var(--border);white-space:nowrap}
.gtbl td{padding:9px 10px;border-bottom:1px solid var(--border);white-space:nowrap;color:var(--text-primary)}
.gtbl tr[data-co]{cursor:pointer;transition:background .1s}
.gtbl tr[data-co]:hover td{background:var(--surface-1)}
.gtbl tr.sel td{background:var(--accent-soft);box-shadow:inset 3px 0 0 var(--accent)}
.grouphdr th{font-size:10.5px;font-weight:600;letter-spacing:.03em;text-transform:none;padding:7px 10px}
.grp-ledger{background:var(--surface-1);color:var(--text-muted)}.grp-detail{background:var(--surface-1);color:var(--text-muted)}.grp-mine{background:#FBEBCF;color:#7A4B06}
.mycol{border-left:2px solid var(--accent)}.detail{display:none}.sheet.show-detail .detail{display:table-cell}
.xbtn{border:1px solid var(--border-strong);background:var(--surface-2);border-radius:7px;padding:3px 8px;cursor:pointer;color:var(--text-secondary)}
.xbtn:hover{border-color:var(--accent);color:var(--accent)}
.crumb{font-size:12px;color:var(--text-secondary);margin-bottom:10px}.crumb a{color:var(--accent);text-decoration:none}
.hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}.hd h3{font-size:20px;margin:0;letter-spacing:-.01em}
.card{background:var(--surface-2);border:1px solid var(--border);border-radius:14px;padding:16px 18px;margin-top:14px;box-shadow:var(--shadow)}
.ct{font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin:0 0 12px}
.scores{display:flex;gap:8px;flex-wrap:wrap;margin:2px 0 10px}
.sbox{background:var(--surface-1);border-radius:var(--radius);padding:8px 13px;min-width:76px}
.sbox .l{font-size:11px;color:var(--text-secondary)}.sbox .v{font-size:18px;font-weight:600}
.why{font-size:12.5px;line-height:1.6}
.ov{font-size:12.5px;margin-top:8px;padding:10px 12px;border:1px solid #EFA84A;border-radius:var(--radius);background:#FDF4E3;color:#7A4B06}
.glabel{font-size:11px;color:var(--text-muted);font-weight:600;margin:14px 0 6px;letter-spacing:.02em}
.cgrid{display:grid;gap:10px}.cg2{grid-template-columns:repeat(2,1fr)}.cg3{grid-template-columns:repeat(3,1fr)}
.lc{background:var(--surface-1);border-radius:var(--radius);padding:11px 13px 12px}
.lch{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:8px;padding-bottom:7px;border-bottom:1px solid var(--border)}
.lct{font-size:11.5px;color:var(--text-primary);font-weight:600}.ls{font-size:10px;background:#DFF3EC;color:#0A5A48;padding:2px 8px;border-radius:20px;font-weight:500}
.r{display:flex;gap:8px;padding:3px 0;font-size:12px;align-items:flex-start}.k{color:var(--text-muted);width:96px;flex-shrink:0}.v{color:var(--text-secondary);line-height:1.45}.v.s{color:var(--text-primary);font-weight:600}
.acc{border:1px solid var(--border);border-radius:var(--radius);margin-top:8px;background:var(--surface-1);overflow:hidden}.acc .acc{margin-top:6px;background:var(--surface-2)}
.ah{padding:11px 13px;cursor:pointer;display:flex;align-items:center;gap:8px;font-size:13px;font-weight:500}.ah:hover{background:rgba(27,31,40,.02)}.chev{display:inline-block;color:var(--text-muted)}
.ab{display:none;padding:0 13px 13px}.acc.open>.ab{display:block}.acc.open>.ah .chev{transform:rotate(90deg)}
.fact{font-size:12.5px;line-height:1.5;padding:8px 0;border-top:1px solid var(--border);display:flex;gap:9px}.fact:first-child{border-top:none}
.cv-ver{background:#DFF3EC;color:#0A5A48}.cv-weak{background:#FBEBCF;color:#7A4B06}.md{font-size:12px;line-height:1.55;color:var(--text-secondary);padding-top:8px}
"""

_SCRIPT = """
var _selCo=null;
function gtab(p,el){['all','pursuit','contacts','radar'].forEach(function(k){document.getElementById('p-'+k).style.display=(k===p)?'':'none';});document.querySelectorAll('.tab').forEach(function(t){t.classList.toggle('active',t===el);});}
function selectRow(el,slug){var t=el.closest('table');if(t){t.querySelectorAll('tr.sel').forEach(function(r){r.classList.remove('sel');});}el.classList.add('sel');_selCo=slug;}
function showGrid(){document.getElementById('view-grid').style.display='';document.getElementById('view-detail').style.display='none';document.querySelectorAll('.topnav button').forEach(function(b){b.classList.toggle('active',b.dataset.view==='grid');});window.scrollTo(0,0);}
function showDetail(id){document.getElementById('view-grid').style.display='none';var d=document.getElementById('view-detail');d.style.display='';document.querySelectorAll('.detailco').forEach(function(x){x.style.display='none';});var el=document.getElementById(id);if(el)el.style.display='';document.querySelectorAll('.topnav button').forEach(function(b){b.classList.toggle('active',b.dataset.view==='detail');});window.scrollTo(0,0);}
function showSelectedDetail(){var id=_selCo||(document.querySelector('.detailco')&&document.querySelector('.detailco').id);if(id)showDetail(id);}
"""


def render_dashboard_html(records: list[dict], report: dict | None = None, *, title: str = "Health-tech career dashboard") -> str:
    """Render the whole dashboard (grid tabs + per-company detail views) from the records as one self-contained
    HTML page. Pure render — every value comes from the records / merged user store."""
    all_rows = _all_companies_rows(records)
    pursuit_tbl = _df_table(dash.pursuit_view(records), "pursuit — your active companies (ledger refreshed · your columns preserved)")
    contacts_tbl = _df_table(dash.contacts_view(records), "contacts — one row per contact")
    radar_tbl = _df_table(dash.segment_radar_view(records), "segment radar — where am I thin? (read-only)")
    details = "".join(_detail_html(r) for r in records)

    all_head = ('<tr class="grouphdr"><th class="grp-mine">yours</th>'
                '<th class="grp-ledger" colspan="7">from the ledger — read-only</th>'
                '<th class="grp-detail detail" colspan="9">tags &amp; scores — toggle</th></tr>'
                '<tr><th class="mycol">pursue</th><th>company</th><th>priority</th><th>segment</th><th>model</th>'
                '<th>stage</th><th>FINAL</th><th></th><th class="detail">subsegment</th><th class="detail">product</th>'
                '<th class="detail">distribution</th><th class="detail">data input</th><th class="detail">bg</th>'
                '<th class="detail">PMF</th><th class="detail">ARR</th><th class="detail">growth</th>'
                '<th class="detail">strain</th></tr>')

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.17.0/dist/tabler-icons.min.css">
<style>{_CSS}</style></head><body><div class="wrap">
<div class="doc-note"><b>{_esc(title)}</b> — rebuilt from the GATE-2-reviewed ledger; your notes preserved. Every company shown passed GATE-2 review (§1a).</div>
{_banners(report)}
<div class="topnav"><button data-view="grid" class="active" onclick="showGrid()">Grid views</button>
<button data-view="detail" onclick="showSelectedDetail()">Company detail</button></div>
<div id="view-grid"><div class="sheet" id="sheet">
<div class="tabs"><button class="tab active" onclick="gtab('all',this)">All companies</button>
<button class="tab" onclick="gtab('pursuit',this)">Pursuit</button>
<button class="tab" onclick="gtab('contacts',this)">Contacts</button>
<button class="tab" onclick="gtab('radar',this)">Segment radar</button></div>
<div id="p-all"><div class="toolbar"><span class="muted" style="font-size:11px">Click a row to select it, then open <b>Company detail</b> above &mdash; or use the expand button on a row.</span>
<span class="chip" style="margin-left:auto" onclick="document.getElementById('sheet').classList.toggle('show-detail')"><i class="ti ti-chevron-right"></i> tags &amp; scores</span></div>
<div class="tablewrap"><table class="gtbl">{all_head}{all_rows}</table></div></div>
<div id="p-pursuit" style="display:none"><div class="tablewrap">{pursuit_tbl}</div></div>
<div id="p-contacts" style="display:none"><div class="tablewrap">{contacts_tbl}</div></div>
<div id="p-radar" style="display:none"><div class="tablewrap">{radar_tbl}</div></div>
</div></div>
<div id="view-detail" style="display:none">{details}</div>
</div><script>{_SCRIPT}</script></body></html>"""


def write_dashboard_html(path: str | Path, records: list[dict], report: dict | None = None, **kwargs) -> Path:
    return storage.atomic_write_text(path, render_dashboard_html(records, report, **kwargs))
