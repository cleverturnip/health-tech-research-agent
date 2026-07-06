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


def _df_table(df: pd.DataFrame) -> str:
    heads = "".join(f"<th>{_esc(_pretty(c))}</th>" for c in df.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_cell(v)}</td>" for v in row) + "</tr>"
        for row in df.itertuples(index=False, name=None))
    return f'<table class="gtbl"><tr>{heads}</tr>{body}</table>'


_TIER_T = {"P0": "t0", "P1": "t1", "P2": "t2", "P3": "t3"}


def _app_header(title: str) -> str:
    return f'<div class="apphdr"><div class="apptitle">{_esc(title)}</div></div>'


def _kpi_section(records: list[dict]) -> str:
    """Top-of-dashboard analytics band: KPI stat tiles + a priority-distribution bar (computed from records)."""
    total = len(records)
    tally = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for r in records:
        if r.get("final_priority") in tally:
            tally[r["final_priority"]] += 1
    pursuing = sum(1 for r in records if r.get("pursue"))
    segments = len({r.get("segment_label") for r in records if r.get("segment_label")})

    tiles = [("Companies", total, "hero"), ("P0", tally["P0"], "t0"), ("P1", tally["P1"], "t1"),
             ("P2", tally["P2"], "t2"), ("P3", tally["P3"], "t3"), ("Pursuing", pursuing, "gold"), ("Segments", segments, "nv")]
    kpis = "".join(f'<div class="kpi {cls}"><div class="kn">{v}</div><div class="kl">{_esc(lbl)}</div></div>'
                   for lbl, v, cls in tiles)
    return f'<div class="kpis">{kpis}</div>'


def _segment_radar_chart(records: list[dict]) -> str:
    """Segment radar as a visual (replaces the plain table): one horizontal stacked bar per segment — length =
    company count (scaled to the biggest segment), stacked by priority tier — plus the coverage badge. Answers
    'where am I thin by segment' at a glance."""
    df = dash.segment_radar_view(records)
    if df.empty:
        return '<div class="radar"><div class="src">No segments yet.</div></div>'
    maxc = max((int(r.companies) for r in df.itertuples(index=False)), default=1) or 1
    legend = "".join(f'<span><i class="dot {_TIER_T[t]}"></i>{t}</span>' for t in ("P0", "P1", "P2", "P3"))
    cov_class = {"Strong": "cov-strong", "Directional": "cov-directional", "Sparse": "cov-sparse"}
    rows = ""
    for r in df.itertuples(index=False):
        segs = "".join(
            f'<div class="radseg {_TIER_T[t]}" style="width:{getattr(r, t) * 100 / maxc:.2f}%" '
            f'title="{t}: {getattr(r, t)}"></div>' for t in ("P0", "P1", "P2", "P3") if getattr(r, t))
        cov = str(r.coverage)
        rows += (
            f'<div class="radrow"><div class="radhead">'
            f'<div class="radname">{_esc(r.segment)}'
            f'<span class="cov {cov_class.get(cov, "cov-sparse")}">{_esc(cov)}</span></div>'
            f'<div class="radmeta">{r.companies} cos · {r.pursuing} pursuing</div></div>'
            f'<div class="radtrack">{segs}</div></div>')
    return f'<div class="radar"><div class="radleg">{legend}</div>{rows}</div>'


# ---------------------------------------------------------------------------
# per-company detail view (scoring + research levers, from the record)
# ---------------------------------------------------------------------------

def _row(label: str, value: str, strong: bool = False) -> str:
    cls = "v s" if strong else "v"
    return f'<div class="r"><span class="k">{_esc(label)}</span><span class="{cls}">{value}</span></div>'


def _lever_card(title: str, chip: str, rows: str, kind: str = "") -> str:
    return (f'<div class="lc"><div class="lch {kind}"><span class="lct">{_esc(title)}</span>'
            f'<span class="ls">{_esc(chip)}</span></div><div class="lcbody">{rows}</div></div>')


def _gate_badge(passed: Any) -> str:
    """A visually distinct PASS/FAIL chip (green check / red x), shown first on a gate row."""
    if passed:
        return '<span class="gbadge pass">&#10003; PASS</span>'
    return '<span class="gbadge fail">&#10007; FAIL</span>'


def _gate_detail(detail: Any) -> str:
    """Tidy a gate detail string: drop the embedded verdict + arrows/brackets so only the reasons remain
    (e.g. 'series-c -> PASS [late-C clean-pass, dial]' -> 'series-c, late-C clean-pass, dial')."""
    d = "" if detail is None else str(detail)
    d = re.sub(r"\s*(->|→)\s*(PASS|FAIL)\b", "", d)
    d = re.sub(r"^\s*(pass|passed|fail|failed)\s*[—-]\s*", "", d, flags=re.I)
    d = d.replace("[", ", ").replace("]", "")
    d = re.sub(r"\s{2,}", " ", d)
    d = re.sub(r"\s+,", ",", d)
    return d.strip(" ,;—-")


def _score(v: Any, denom: int) -> str:
    """Format a score as 'v/denom' when numeric, else the raw display (e.g. 'n/a (no consumer end-user)')."""
    if isinstance(v, bool) or v is None:
        return _cell(v)
    if isinstance(v, (int, float)):
        return f"{v}/{denom}"
    sv = str(v).strip()
    return f"{sv}/{denom}" if sv.replace(".", "", 1).isdigit() else _cell(v)


def _detail_body(r: dict) -> str:
    """The per-company detail CARD BODY (header + SCORING & DECISION + RESEARCH EVIDENCE) — shared by the
    dashboard's detail view and the Phase-2 GATE-2 review card. No outer toggle wrapper / breadcrumb."""
    s = r["scores"]
    scoring = r.get("scoring", {})
    gates = r.get("gates", {})
    res = r.get("research") or {}
    was = f' <span class="pill p3" style="opacity:.8">model: {_esc(r["model_priority"])}</span>' \
        if r.get("is_overridden") else ""

    def _sbox(lbl, val, cls=""):
        return f'<div class="sbox {cls}"><div class="l">{_esc(lbl)}</div><div class="v">{_cell(val)}</div></div>'

    # Background Fit · PMF (ARR + Growth connected beneath — they FEED pmf, not the Total) · Strain · Total
    pmf_group = (f'<div class="pmfcol">{_sbox("PMF", s["pmf"])}<div class="pmfconn"></div>'
                 f'<div class="pmfsub">{_sbox("ARR", s["arr"], "sm")}{_sbox("Growth", s["growth"], "sm")}</div></div>')
    score_boxes = (_sbox("Background Fit", r["bg_display"]) + pmf_group
                   + _sbox("Strain", s["strain"]) + _sbox("Total", r["final_display"], "final"))

    ov = ""
    if r.get("override"):
        o = r["override"]
        ov = (f'<div class="ov"><b>Your override → {_esc(o["to"])}:</b> {_esc(o["reason"])} '
              f'<span class="src">(model said {_esc(o["from"])})</span></div>')

    bg_rat = _esc(scoring.get("bg_fit", {}).get("rationale"))
    floor = _esc(scoring.get("floor_rule", {}).get("reason"))
    why_parts = ([f'<div>{bg_rat}</div>'] if bg_rat else []) + ([f'<div>Floor rule: {floor}</div>'] if floor else [])
    right_inner = "".join(why_parts) + ov
    score_why = f'<div class="scorewhy">{right_inner}</div>' if right_inner.strip() else ""

    # gate cards — the GATE result (PASS/FAIL badge) is the top row of each
    path = gates.get("path", {})
    agency = gates.get("agency", {})
    class_rows = (_row("Path to Scale Gate", _gate_badge(path.get("passed")) + _esc(_gate_detail(path.get("detail"))))
                  + _row("Model", _esc(r["model"]))
                  + (_row("Channel", _esc(res.get("commercial", {}).get("business_model_type")))
                     if res.get("commercial", {}).get("business_model_type") else ""))
    fund_rows = (_row("Agency Gate", _gate_badge(agency.get("passed")) + _esc(_gate_detail(agency.get("detail"))))
                 + _row("Stage", _esc(r["stage"])))
    if res.get("maturity", {}).get("total_funding"):
        fund_rows += _row("Total Raised", _esc(res["maturity"]["total_funding"]))

    gate_cards = (_lever_card("Classification & Channel", "Drives Path", class_rows, "gate")
                  + _lever_card("Funding & Maturity", "Drives Agency", fund_rows, "gate"))

    # score cards — the SCORE is the top row of each
    com = res.get("commercial", {})
    pmf_rows = _row("ARR", _score(s["arr"], 10), True) + _row("Growth", _score(s["growth"], 10), True)
    if com.get("revenue_or_arr"):
        pmf_rows += _row("Revenue", _esc(com["revenue_or_arr"]))
    if com.get("growth_signal"):
        pmf_rows += _row("Growth signal", _esc(com["growth_signal"]))
    if com.get("evidence_quality"):
        pmf_rows += _row("Evidence", _esc(com["evidence_quality"]) + ' <span class="src">— trust cue</span>')
    bg_rows = (_row("Background Fit", _score(r["bg_display"], 10), True)
               + _row("Cadence", bg_rat or "—") + _row("Loop", str(scoring.get("bg_fit", {}).get("loop"))))
    cap = res.get("capability", {})
    strain_rows = _row("Strain", _score(s["strain"], 2), True)
    if scoring.get("strain", {}).get("strength"):
        strain_rows += _row("Strength", _esc(scoring["strain"]["strength"]))
    if cap.get("a2_basis"):
        strain_rows += _row("Context", _esc(cap["a2_basis"]))

    score_cards = (_lever_card("Product Market Fit", "Drives PMF", pmf_rows, "score")
                   + _lever_card("Background Fit", "Drives Background Fit", bg_rows, "score")
                   + _lever_card("Operator Needed", "Drives Strain", strain_rows, "score"))

    # research accordions (only when research is joined)
    research_block = ""
    if r.get("research"):
        facts = "".join(
            f'<div class="fact"><span class="pill cv-ver">Verified</span><div>{_esc(f)}</div></div>'
            for f in res.get("verified_facts", []))
        weak = "".join(
            f'<div class="fact"><span class="pill cv-weak">Weak</span><div>{_esc(w)}</div></div>'
            for w in res.get("weak_claims", []))
        findings = "".join(
            f'<div class="acc"><div class="ah" onclick="this.parentElement.classList.toggle(\'open\')">'
            f'<i class="ti ti-chevron-right chev"></i> {_esc(name.replace("_finding", "").replace("_", " ").title())}'
            f'</div><div class="ab"><div class="md">{_esc(text)}</div></div></div>'
            for name, text in res.get("findings", {}).items())
        research_block = (
            '<div class="acc"><div class="ah" onclick="this.parentElement.classList.toggle(\'open\')">'
            '<i class="ti ti-chevron-right chev"></i> Verified Facts &amp; Sources</div>'
            f'<div class="ab">{facts}{weak}</div></div>'
            '<div class="acc"><div class="ah" onclick="this.parentElement.classList.toggle(\'open\')">'
            '<i class="ti ti-chevron-right chev"></i> Full Findings — raw research text</div>'
            f'<div class="ab">{findings}</div></div>')
    else:
        research_block = '<div class="src" style="margin-top:10px">No research joined for this company.</div>'

    return (
        f'<div class="hd"><h3>{_esc(r["company"])}</h3>{_pill(r["final_priority"])}{was}'
        f'<span style="color:var(--text-secondary);font-size:12.5px">{_esc(r["segment_label"])} · '
        f'{_esc(r["model"])} · {_esc(r["stage"])}</span></div>'
        f'<div class="card"><p class="ct">SCORING &amp; DECISION</p>'
        f'<div class="scorewrap"><div class="scores">{score_boxes}</div>{score_why}</div></div>'
        f'<div class="card"><p class="ct">RESEARCH EVIDENCE — at a glance (each card = a scoring lever)</p>'
        f'<div class="glabel">The Gates — a fail here caps priority at P3</div>'
        f'<div class="cgrid cg2">{gate_cards}</div>'
        f'<div class="glabel">The Score — Background Fit + PMF + Strain = Total</div>'
        f'<div class="cgrid cg3">{score_cards}</div>{research_block}</div>')


def _detail_html(r: dict) -> str:
    """Dashboard detail view: the shared card body wrapped in the toggled container + breadcrumb (dashboard nav)."""
    return (
        f'<div class="detailco" id="{_slug(r["company"])}" style="display:none">'
        f'<div class="crumb"><a href="#" onclick="showGrid();return false;"><i class="ti ti-arrow-left"></i> '
        f'All Companies</a> / <span style="color:var(--text-primary)">{_esc(r["company"])}</span></div>'
        f'{_detail_body(r)}</div>')


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
:root{--navy:#144C6F;--navy-2:#1C6389;--surface-0:#eef2f6;--surface-1:#e3eaf0;--surface-2:#fff;--text-primary:#1a2b38;--text-secondary:#54636f;--text-muted:#8794a0;--border:rgba(20,60,90,.11);--border-strong:rgba(20,60,90,.20);--accent:#06C4BD;--accent-ink:#0A8F89;--accent-soft:#D6F4F2;--gold:#F2C14E;--radius:10px;--shadow:0 1px 2px rgba(20,60,90,.05),0 8px 24px rgba(20,60,90,.08);--t0:#144C6F;--t1:#2E86B8;--t2:#58B0DE;--t3:#BADCF0;--p0c:#123F5C;--p0bg:#D7E3EC;--p1c:#1B6299;--p1bg:#D9E8F4;--p2c:#2E90BE;--p2bg:#DEEFF8;--p3c:#647D8E;--p3bg:#E9EEF1}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,system-ui,sans-serif;color:var(--text-primary);background:var(--surface-0);margin:0;padding:28px;line-height:1.5;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.wrap{max-width:1060px;margin:0 auto}
.doc-note{font-size:12.5px;color:var(--text-secondary);background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius);padding:12px 15px;margin-bottom:14px;box-shadow:var(--shadow)}
.banner{font-size:12.5px;border-radius:var(--radius);padding:10px 13px;margin-bottom:8px;border:1px solid transparent}
.banner.warn{background:#FDF4E3;color:#7A4B06;border-color:#F2DCB3}.banner.danger{background:#FCECEC;color:#8A2020;border-color:#F1C9C9}
.topnav{display:flex;gap:8px;margin:14px 0}
.topnav button{font:inherit;font-size:13px;font-weight:500;background:var(--surface-2);border:1px solid var(--border-strong);border-radius:var(--radius);padding:8px 15px;cursor:pointer;color:var(--text-secondary);transition:.12s}
.topnav button:hover{border-color:var(--accent);color:var(--accent)}
.topnav button.active{background:var(--navy);color:#fff;border-color:var(--navy)}
.pill{font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px;display:inline-block;letter-spacing:.01em}
.p0{background:var(--p0c);color:#fff}.p1{background:var(--p1c);color:#fff}.p2{background:var(--p2c);color:#fff}.p3{background:var(--p3c);color:#fff}
.was{font-size:11px;color:var(--text-muted);font-weight:400}.muted{color:var(--text-muted)}.src{color:var(--text-muted);font-size:11.5px}
.sheet{border:1px solid var(--border);border-radius:14px;overflow:hidden;background:var(--surface-2);font-size:13px;box-shadow:var(--shadow)}
.tabs{display:flex;gap:4px;padding:7px 8px 0;background:var(--navy)}
.tab{padding:10px 17px;font-size:13px;font-weight:600;color:rgba(255,255,255,.72);cursor:pointer;border:none;background:transparent;border-radius:8px 8px 0 0;transition:.12s}
.tab:hover{color:#fff;background:rgba(255,255,255,.14)}
.tab.active{color:var(--navy);background:var(--surface-2)}
.toolbar{display:flex;align-items:center;gap:8px;padding:9px 14px;border-bottom:1px solid var(--border);flex-wrap:wrap;background:var(--surface-2)}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;padding:5px 11px;border:1px solid var(--border-strong);border-radius:var(--radius);color:var(--text-primary);background:var(--surface-2);cursor:pointer}
.chip:hover{border-color:var(--accent);color:var(--accent)}
.tablewrap{overflow-x:auto}
.apphdr{background:linear-gradient(120deg,var(--navy),var(--navy-2));color:#fff;border-radius:14px;padding:18px 22px;margin:2px 0 16px;box-shadow:var(--shadow)}
.apptitle{font-size:21px;font-weight:800;letter-spacing:-.01em;color:#fff}
.appsub{font-size:12px;color:rgba(255,255,255,.72);margin-top:4px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:10px;margin-bottom:14px}
.kpi{display:flex;align-items:baseline;gap:8px;border:1px solid var(--border);border-radius:11px;padding:13px 15px;box-shadow:var(--shadow);background:var(--surface-2)}
.kpi .kn{font-size:24px;font-weight:800;letter-spacing:-.02em;line-height:1;color:var(--navy)}
.kpi .kl{font-size:11px;color:var(--text-secondary);font-weight:700;text-transform:uppercase;letter-spacing:.03em}
.kpi.hero{background:#D9F4F1;border-color:#B6E7E2}.kpi.hero .kn{color:#0A7D7D}
.kpi.nv{background:#E5EBF1;border-color:#CDD9E4}.kpi.nv .kn{color:#123F5C}
.kpi.gold{background:#FBF1D8;border-color:#EEDBA6}.kpi.gold .kn{color:#8A6A12}.kpi.gold .kl{color:#8A6A12}
.kpi.t0{background:var(--p0c);border-color:var(--p0c)}.kpi.t1{background:var(--p1c);border-color:var(--p1c)}
.kpi.t2{background:var(--p2c);border-color:var(--p2c)}.kpi.t3{background:var(--p3c);border-color:var(--p3c)}
.kpi.t0 .kn,.kpi.t0 .kl,.kpi.t1 .kn,.kpi.t1 .kl,.kpi.t2 .kn,.kpi.t2 .kl,.kpi.t3 .kn,.kpi.t3 .kl{color:#fff}
.kpi.t0 .kl,.kpi.t1 .kl,.kpi.t2 .kl,.kpi.t3 .kl{font-size:24px;font-weight:700;text-transform:none;letter-spacing:-.02em}
.distwrap{background:var(--surface-2);border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin-bottom:18px;box-shadow:var(--shadow)}
.distbar{display:flex;height:14px;border-radius:8px;overflow:hidden;background:var(--surface-1)}
.distseg{height:100%}.distseg.t0{background:var(--t0)}.distseg.t1{background:var(--t1)}.distseg.t2{background:var(--t2)}.distseg.t3{background:var(--t3)}
.distleg{display:flex;gap:16px;margin-top:11px;font-size:11.5px;color:var(--text-secondary);font-weight:500}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px;vertical-align:middle}
.dot.t0{background:var(--t0)}.dot.t1{background:var(--t1)}.dot.t2{background:var(--t2)}.dot.t3{background:var(--t3)}
table.gtbl{border-collapse:collapse;width:100%;font-size:12.5px}
.gtbl th{text-align:left;font-weight:700;font-size:11px;letter-spacing:.02em;text-transform:capitalize;color:rgba(255,255,255,.92);background:var(--navy);padding:11px 10px;white-space:nowrap}
.gtbl td{padding:10px;border-bottom:1px solid var(--border);white-space:nowrap;color:var(--text-primary)}
.gtbl tr:nth-child(even) td{background:#EAF1F8}
.gtbl tr[data-co]{cursor:pointer;transition:background .1s}
.gtbl tr[data-co]:hover td{background:#DCE8F5}
.gtbl tr.sel td{background:var(--accent-soft)}
.gtbl tr.sel td:first-child{box-shadow:inset 3px 0 0 var(--accent)}
input[type=checkbox]{accent-color:var(--accent);width:15px;height:15px}
.radar{padding:16px 18px}
.radleg{display:flex;gap:16px;margin-bottom:16px;font-size:11.5px;color:var(--text-secondary);font-weight:500}
.radrow{padding:11px 2px;border-bottom:1px solid var(--border)}
.radrow:last-child{border-bottom:none}
.radhead{display:flex;justify-content:space-between;align-items:baseline;gap:14px;margin-bottom:8px}
.radname{font-size:13px;font-weight:600;color:var(--text-primary)}
.radname .cov{margin-left:8px}
.radtrack{display:flex;height:16px;background:var(--surface-1);border-radius:6px;overflow:hidden}
.radseg{height:100%}.radseg.t0{background:var(--t0)}.radseg.t1{background:var(--t1)}.radseg.t2{background:var(--t2)}.radseg.t3{background:var(--t3)}
.radmeta{font-size:11.5px;color:var(--text-muted);white-space:nowrap;flex-shrink:0}
.cov{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;padding:2px 7px;border-radius:10px;white-space:nowrap}
.cov-strong{background:#E4F2D8;color:#3B7D1E}.cov-directional{background:#FBEBCF;color:#B4741A}.cov-sparse{background:#F7DADA;color:#9A2A2A}
.grouphdr th{font-size:10.5px;font-weight:600;letter-spacing:.03em;text-transform:none;padding:7px 10px}
.grp-ledger{background:var(--surface-1);color:var(--text-muted)}.grp-detail{background:var(--surface-1);color:var(--text-muted)}.grp-mine{background:#FBEBCF;color:#7A4B06}
.mycol{border-left:2px solid var(--accent)}.detail{display:none}.sheet.show-detail .detail{display:table-cell}
.xbtn{border:1px solid var(--border-strong);background:var(--surface-2);border-radius:7px;padding:3px 8px;cursor:pointer;color:var(--text-secondary)}
.xbtn:hover{border-color:var(--accent);color:var(--accent)}
.crumb{font-size:12px;color:var(--text-secondary);margin-bottom:10px}.crumb a{color:var(--accent);text-decoration:none}
.hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}.hd h3{font-size:20px;margin:0;letter-spacing:-.01em}
.card{background:var(--surface-2);border:1px solid var(--border);border-top:3px solid var(--navy);border-radius:14px;padding:16px 18px;margin-top:14px;box-shadow:var(--shadow)}
.ct{font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--navy);font-weight:700;margin:0 0 12px}
.scorewrap{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap;margin:2px 0 2px}
.scores{display:flex;gap:8px;align-items:flex-start}
.scorewhy{flex:1;min-width:260px;background:var(--surface-1);border:1px solid var(--border);border-radius:var(--radius);padding:12px 14px;font-size:12.5px;line-height:1.6;color:var(--text-secondary)}
.pmfcol{display:flex;flex-direction:column;align-items:center;gap:0}
.pmfconn{width:2px;height:8px;background:var(--border-strong)}
.pmfsub{display:flex;gap:6px}
.sbox.sm{width:44px;padding:6px 4px}.sbox.sm .l{font-size:10px}.sbox.sm .v{font-size:14px}
.gbadge{display:inline-block;font-size:10px;font-weight:800;padding:2px 8px;border-radius:20px;letter-spacing:.03em;margin-right:8px}
.gbadge.pass{background:#DCF3E4;color:#1E7A3E}.gbadge.fail{background:#FADCDC;color:#A32020}
.sbox{background:#EAF1F8;border:1px solid #D3E1EE;border-radius:var(--radius);padding:9px 8px;width:94px;text-align:center}
.sbox .l{font-size:11px;color:var(--text-secondary)}.sbox .v{font-size:18px;font-weight:700;color:var(--navy);margin-top:2px}
.sbox.final{background:var(--navy);border-color:var(--navy)}.sbox.final .l{color:rgba(255,255,255,.72)}.sbox.final .v{color:#fff}
.why{font-size:12.5px;line-height:1.6}
.ov{font-size:12.5px;margin-top:8px;padding:10px 12px;border:1px solid var(--gold);border-radius:var(--radius);background:#FCF5E2;color:#7A5B10}
.glabel{font-size:11px;color:var(--accent-ink);font-weight:700;margin:14px 0 6px;letter-spacing:.03em}
.cgrid{display:grid;gap:10px}.cg2{grid-template-columns:repeat(2,1fr)}.cg3{grid-template-columns:repeat(3,1fr)}
.lc{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.lch{display:flex;justify-content:space-between;align-items:center;gap:6px;padding:9px 12px}
.lch.gate{background:var(--accent)}.lch.score{background:#2E6FA8}
.lct{font-size:11.5px;color:#fff;font-weight:700}
.ls{font-size:9.5px;background:rgba(255,255,255,.24);color:#fff;padding:2px 8px;border-radius:20px;font-weight:600}
.lcbody{padding:10px 12px 12px}
.r{display:flex;gap:8px;padding:3px 0;font-size:12px;align-items:flex-start}.k{color:var(--text-muted);width:96px;flex-shrink:0}.v{color:var(--text-secondary);line-height:1.45}.v.s{color:var(--text-primary);font-weight:600}
.acc{border:1px solid var(--border);border-radius:var(--radius);margin-top:8px;background:var(--surface-1);overflow:hidden}.acc .acc{margin-top:6px;background:var(--surface-2)}
.ah{padding:11px 13px;cursor:pointer;display:flex;align-items:center;gap:8px;font-size:13px;font-weight:500}.ah:hover{background:rgba(27,31,40,.02)}.chev{display:inline-block;color:var(--text-muted)}
.ab{display:none;padding:0 13px 13px}.acc.open>.ab{display:block}.acc.open>.ah .chev{transform:rotate(90deg)}
.fact{font-size:12.5px;line-height:1.5;padding:8px 0;border-top:1px solid var(--border);display:flex;gap:9px}.fact:first-child{border-top:none}
.cv-ver{background:var(--accent-soft);color:var(--accent-ink)}.cv-weak{background:#FBF1D8;color:#8A6A12}.md{font-size:12px;line-height:1.55;color:var(--text-secondary);padding-top:8px}
"""

_SCRIPT = """
var _selCo=null;
function gtab(p,el){['all','pursuit','contacts','radar'].forEach(function(k){document.getElementById('p-'+k).style.display=(k===p)?'':'none';});document.querySelectorAll('.tab').forEach(function(t){t.classList.toggle('active',t===el);});try{sessionStorage.setItem('htra_tab',p);}catch(e){}}
window.addEventListener('DOMContentLoaded',function(){var t=null;try{t=sessionStorage.getItem('htra_tab');}catch(e){}if(t&&t!=='all'){var b=document.querySelector('.tab[data-tab="'+t+'"]');if(b)gtab(t,b);}});
function selectRow(el,slug){var t=el.closest('table');if(t){t.querySelectorAll('tr.sel').forEach(function(r){r.classList.remove('sel');});}el.classList.add('sel');_selCo=slug;}
function showGrid(){document.getElementById('view-grid').style.display='';document.getElementById('view-detail').style.display='none';document.querySelectorAll('.topnav button').forEach(function(b){b.classList.toggle('active',b.dataset.view==='grid');});window.scrollTo(0,0);}
function showDetail(id){document.getElementById('view-grid').style.display='none';var d=document.getElementById('view-detail');d.style.display='';document.querySelectorAll('.detailco').forEach(function(x){x.style.display='none';});var el=document.getElementById(id);if(el)el.style.display='';document.querySelectorAll('.topnav button').forEach(function(b){b.classList.toggle('active',b.dataset.view==='detail');});window.scrollTo(0,0);}
function showSelectedDetail(){var id=_selCo||(document.querySelector('.detailco')&&document.querySelector('.detailco').id);if(id)showDetail(id);}
"""


def render_dashboard_html(records: list[dict], report: dict | None = None, *, title: str = "Katelynd Career Research Dashboard") -> str:
    """Render the whole dashboard (grid tabs + per-company detail views) from the records as one self-contained
    HTML page. Pure render — every value comes from the records / merged user store."""
    all_rows = _all_companies_rows(records)
    pursuit_tbl = _df_table(dash.pursuit_view(records))
    contacts_tbl = _df_table(dash.contacts_view(records))
    radar_chart = _segment_radar_chart(records)
    details = "".join(_detail_html(r) for r in records)

    all_head = ('<tr><th class="mycol">pursue</th><th>company</th><th>priority</th><th>segment</th><th>model</th>'
                '<th>stage</th><th>FINAL</th><th></th><th class="detail">subsegment</th><th class="detail">product</th>'
                '<th class="detail">distribution</th><th class="detail">data input</th><th class="detail">bg</th>'
                '<th class="detail">PMF</th><th class="detail">ARR</th><th class="detail">growth</th>'
                '<th class="detail">strain</th></tr>')

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.17.0/dist/tabler-icons.min.css">
<style>{_CSS}</style></head><body><div class="wrap">
{_banners(report)}
<div id="view-grid">{_kpi_section(records)}<div class="sheet" id="sheet">
<div class="tabs"><button class="tab active" data-tab="all" onclick="gtab('all',this)">All Companies</button>
<button class="tab" data-tab="pursuit" onclick="gtab('pursuit',this)">Pursuit</button>
<button class="tab" data-tab="contacts" onclick="gtab('contacts',this)">Contacts</button>
<button class="tab" data-tab="radar" onclick="gtab('radar',this)">Segment Radar</button></div>
<div id="p-all"><div class="toolbar"><span class="muted" style="font-size:11px">Click a row to select it, then open <b>Company detail</b> &mdash; or use the expand button on a row.</span>
<span class="topnav" style="margin:0 8px 0 auto"><button data-view="grid" class="active" onclick="showGrid()">Grid views</button><button data-view="detail" onclick="showSelectedDetail()">Company detail</button></span>
<span class="chip" onclick="document.getElementById('sheet').classList.toggle('show-detail')"><i class="ti ti-chevron-right"></i> tags &amp; scores</span></div>
<div class="tablewrap"><table class="gtbl">{all_head}{all_rows}</table></div></div>
<div id="p-pursuit" style="display:none"><div class="toolbar"><span class="muted" style="font-size:12px">Companies Katelynd is actively pursuing</span></div><div class="tablewrap">{pursuit_tbl}</div></div>
<div id="p-contacts" style="display:none"><div class="toolbar"><span class="muted" style="font-size:12px">Contact list for target companies</span></div><div class="tablewrap">{contacts_tbl}</div></div>
<div id="p-radar" style="display:none">{radar_chart}</div>
</div></div>
<div id="view-detail" style="display:none">{details}</div>
</div><script>{_SCRIPT}</script></body></html>"""


def write_dashboard_html(path: str | Path, records: list[dict], report: dict | None = None, **kwargs) -> Path:
    return storage.atomic_write_text(path, render_dashboard_html(records, report, **kwargs))
