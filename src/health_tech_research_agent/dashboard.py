"""
Dashboard segment (the second autonomous segment, after GATE 2) — the READ side (Phase 2).

Rebuilt from scratch against the scoring ledger (`ledger.jsonl`), per `specs/DASHBOARD_DESIGN.md`. This is the
"engine": it turns GATE-2-reviewed ledger entries (+ the research join) into a stable per-company DATA MODEL,
and projects that model into the grid views (all companies, segment radar). The user's editable layer (pursue
flag, workspace notes, contacts) and its merge are Phase 3; the HTML render is Phase 5; the orchestrator that
writes durable artifacts is Phase 4.

Load-bearing rules honored here:
  - §1a GATE INVARIANT — only `ledger.is_reviewed` entries reach the dashboard; an un-reviewed entry RAISES
    (never silently included). Presence in the dashboard ⟹ passed GATE-2 review.
  - The data model is the stable interface: the grid views, the (later) detail view, and the (later) front end
    are all projections/renders of the SAME per-company record — nothing valuable gets rebuilt per surface.
  - Segment is CARRIED CONTEXT on the entry (`taxonomy.segment`, a code) — joined to its display label from
    `taxonomy/market_segments.csv`; the dashboard never re-parses the research for the grid. The research join
    is only for the per-company detail view's evidence layers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import ledger
from . import taxonomy as tax

# Coverage-read thresholds (LOCKED 2026-07-03, DASHBOARD_DESIGN.md §5 Tab 4 — the original research-coverage
# intent: "have I researched this segment enough?"). Company-count basis, NOT a career-fit judgment.
COVERAGE_STRONG_COMPANIES = 3
COVERAGE_STRONG_DESIRABLE = 2
COVERAGE_DIRECTIONAL_COMPANIES = 2
COVERAGE_DIRECTIONAL_DESIRABLE = 1
DESIRABLE_TIERS = ("P0", "P1", "P2")

# The 8 raw research findings joined into the detail view's deepest layer (Layer 3).
RESEARCH_FINDING_COLUMNS = (
    "funding_finding", "payer_institutional_finding", "outcomes_finding", "commercial_scale_finding",
    "growth_finding", "paying_finding", "org_events_finding", "operating_characteristics_finding",
)


class DashboardError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# small value helpers (self-contained; mirror ledger's normalization)
# ---------------------------------------------------------------------------

def _txt(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none") else text


def _num(value: Any):
    if isinstance(value, bool):
        return None
    return value if isinstance(value, (int, float)) else None


def _norm_company(value: Any) -> str:
    return _txt(value).lower()


# ---------------------------------------------------------------------------
# display helpers (grid-facing; B2B n/a legibility, DASHBOARD_DESIGN.md §5a)
# ---------------------------------------------------------------------------

def _is_b2b(entry: dict) -> bool:
    return _txt(entry.get("model")).upper() == "B2B"


def _bg_display(entry: dict):
    """Background fit for a human view: the score; 'n/a (no consumer end-user)' for B2B; else '' (read-gap)."""
    score = _num(entry.get("scoring", {}).get("bg_fit", {}).get("score"))
    if score is not None:
        return score
    return "n/a (no consumer end-user)" if _is_b2b(entry) else ""


def _final_display(entry: dict):
    """FINAL for a human view: the score; 'n/a' for B2B (FINAL needs background fit); else ''."""
    final = _num(entry.get("scoring", {}).get("final_score"))
    if final is not None:
        return final
    return "n/a" if _is_b2b(entry) else ""


def _key_flag(entry: dict) -> str:
    """The single most salient flag (a warn beats an info; else the first; else '')."""
    flags = entry.get("flags", [])
    warns = [f for f in flags if _txt(f.get("severity")) == "warn"]
    chosen = warns[0] if warns else (flags[0] if flags else None)
    return _txt(chosen.get("type")) if chosen else ""


# ---------------------------------------------------------------------------
# segment label join
# ---------------------------------------------------------------------------

def segment_label_map(taxonomy_dir: str | Path | None = None) -> dict:
    """`segment_code -> segment_label` from `taxonomy/market_segments.csv` (all 14 dashboard-visible segments,
    incl. OTHER_REVIEW='Other', FINTECH, ENTERTAINMENT_TECH). Defaults to the repo taxonomy dir."""
    code_to_label, _ = tax.code_label_maps(tax.load_taxonomy_tables(taxonomy_dir))
    return code_to_label


# ---------------------------------------------------------------------------
# research join (for the per-company detail view — Layer 1 structured + Layer 3 raw findings)
# ---------------------------------------------------------------------------

def _research_index(research: Any) -> dict:
    """Index research rows by normalized company. Accepts a DataFrame or a list of dicts; None -> {}."""
    if research is None:
        return {}
    records = research.fillna("").to_dict("records") if isinstance(research, pd.DataFrame) else list(research)
    return {_norm_company(rec.get("company")): rec for rec in records if _norm_company(rec.get("company"))}


def _parse_fit_brief(row: dict) -> dict:
    raw = row.get("fit_brief_json")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def research_payload(row: dict) -> dict:
    """Extract the detail view's research evidence from ONE research row (§5a Layers 1–3). Pulls the STRUCTURED
    fit-brief evidence (facts, commercial, maturity, capability, classification rationale) + the 8 raw findings.
    Deliberately EXCLUDES the retired synthesis scores and the LLM's parallel judgments (`role_timing`,
    `priority_gate_preliminary_result`, q1–q4 as scoring) — those are not §B inputs (DASHBOARD_DESIGN.md §5b)."""
    fb = _parse_fit_brief(row)
    commercial = fb.get("commercial_evidence") if isinstance(fb.get("commercial_evidence"), dict) else {}
    maturity = fb.get("maturity_evidence") if isinstance(fb.get("maturity_evidence"), dict) else {}
    capability = fb.get("capability_evidence") if isinstance(fb.get("capability_evidence"), dict) else {}
    taxonomy = fb.get("taxonomy_classification") if isinstance(fb.get("taxonomy_classification"), dict) else {}
    return {
        "verified_facts": list(fb.get("verified_facts_with_sources") or []),
        "inferences": list(fb.get("inferences") or []),
        "weak_claims": list(fb.get("unverified_or_weak_claims") or []),
        "commercial": {
            "revenue_or_arr": _txt(commercial.get("revenue_or_arr")),
            "growth_signal": _txt(commercial.get("growth_signal")),
            "paying_customer_count": _txt(commercial.get("paying_customer_count")),
            "revenue_per_user": _txt(commercial.get("revenue_per_user")),
            "business_model_type": _txt(commercial.get("business_model_type")),
            "evidence_quality": _txt(commercial.get("q4_evidence_quality")),
        },
        "maturity": {
            "funding_rounds": list(maturity.get("funding_rounds") or []),
            "total_funding": _txt(maturity.get("total_funding")),
            "funding_stage_evidence": _txt(maturity.get("funding_stage_evidence")),
        },
        "capability": {
            "a2_score": capability.get("a2_score"),
            "a2_basis": _txt(capability.get("a2_basis")),
        },
        "classification_rationale": _txt(taxonomy.get("classification_rationale")),
        "findings": {col: _txt(row.get(col)) for col in RESEARCH_FINDING_COLUMNS if _txt(row.get(col))},
    }


# ---------------------------------------------------------------------------
# the per-company DATA MODEL (the stable interface every surface renders)
# ---------------------------------------------------------------------------

def build_company_record(entry: dict, research_row: dict | None = None, *, label_map: dict | None = None) -> dict:
    """Turn ONE ledger entry (+ optional research row) into the dashboard's per-company record. Ledger-derived
    fields use the public `ledger` read helpers (never re-scored). Segment code -> label via `label_map`.
    User-layer fields (pursue / workspace / contacts) are added later by the merge (Phase 3) — defaulted here."""
    label_map = label_map or {}
    taxonomy = entry.get("taxonomy", {}) if isinstance(entry.get("taxonomy"), dict) else {}
    segment_code = _txt(taxonomy.get("segment"))
    decision = entry.get("decision", {})
    human_override = _txt(decision.get("human_override"))
    scoring = entry.get("scoring", {})
    pmf = scoring.get("pmf", {})

    record = {
        "company": _txt(entry.get("company")),
        "reviewed": ledger.is_reviewed(entry),
        # priority / provenance (derived on read)
        "final_priority": ledger.final_priority(entry),
        "final_priority_rank": ledger.final_priority_rank(entry),
        "model_priority": _txt(entry.get("model_priority")),
        "provenance": ledger.provenance(entry),
        "is_overridden": bool(human_override),
        "override": ({"from": _txt(entry.get("model_priority")), "to": human_override,
                      "reason": _txt(decision.get("override_reason"))} if human_override else None),
        # identity / context
        "model": _txt(entry.get("model")),
        "stage": _txt(entry.get("stage")),
        "segment_code": segment_code,
        "segment_label": label_map.get(segment_code, segment_code),
        "tags": {
            "subsegment": list(taxonomy.get("subsegment_tags") or []),
            "product_model": list(taxonomy.get("product_model_tags") or []),
            "distribution_model": list(taxonomy.get("distribution_model_tags") or []),
            "data_input": list(taxonomy.get("data_input_tags") or []),
        },
        # scores (raw + human display with B2B n/a legibility)
        "scores": {
            "bg": _num(scoring.get("bg_fit", {}).get("score")),
            "pmf": _num(pmf.get("score")),
            "arr": _num(pmf.get("arr_level", {}).get("score")),
            "growth": _num(pmf.get("growth", {}).get("score")),
            "strain": _num(scoring.get("strain", {}).get("score")),
            "final": _num(scoring.get("final_score")),
        },
        "bg_display": _bg_display(entry),
        "final_display": _final_display(entry),
        # flags
        "flags": list(entry.get("flags", [])),
        "key_flag": _key_flag(entry),
        # detail-view pass-throughs (scoring rationale + gates) — rendered by the detail view (Phase 5)
        "scoring": scoring,
        "gates": entry.get("gates", {}),
        "recommended_action": _txt(entry.get("recommended_action")),  # not shown on the dashboard; kept for provenance
        # research evidence (detail view Layers 1–3) — None when no research row joined
        "research": research_payload(research_row) if research_row is not None else None,
        # user layer (Phase 3) — defaults; the merge fills these from the durable user store
        "pursue": False,
    }
    return record


def build_company_records(entries: list[dict], research: Any = None, *, taxonomy_dir: str | Path | None = None,
                          require_reviewed: bool = True) -> list[dict]:
    """Build the per-company records for a whole ledger. ENFORCES the §1a gate invariant: with
    `require_reviewed` (default), any entry that has NOT passed GATE-2 review (`ledger.is_reviewed` False) RAISES
    — an un-gated entry must never reach the dashboard. Sorted by final priority (tier, then FINAL desc)."""
    unreviewed = [_txt(e.get("company")) for e in entries if not ledger.is_reviewed(e)]
    if require_reviewed and unreviewed:
        raise DashboardError(
            "GATE-2 invariant (§1a): these entries are not reviewed and must not reach the dashboard: "
            f"{sorted(unreviewed)}. Finalize the GATE-2 review (ledger.finalize_gate2_review) first."
        )

    label_map = segment_label_map(taxonomy_dir)
    index = _research_index(research)
    records = [
        build_company_record(entry, index.get(_norm_company(entry.get("company"))), label_map=label_map)
        for entry in entries
    ]
    return sort_records(records)


def sort_records(records: list[dict]) -> list[dict]:
    """Sort by priority tier (P0 first) then FINAL score desc, then company. A None rank sorts last within tier."""
    def key(r):
        tier = ledger.PRIORITY_RANK.get(r.get("final_priority"), 99)
        rank = r.get("final_priority_rank")
        rank = rank if isinstance(rank, (int, float)) else -999
        return (tier, -rank, r.get("company", ""))
    return sorted(records, key=key)


# ---------------------------------------------------------------------------
# projections — the grid views (all companies, segment radar)
# ---------------------------------------------------------------------------

ALL_COMPANIES_COLUMNS = [
    "pursue", "company", "final_priority", "model_priority", "provenance", "segment", "model", "stage", "FINAL",
    "subsegment_tags", "product_model_tags", "distribution_model_tags", "data_input_tags",
    "background_fit", "PMF", "ARR", "growth", "strain", "key_flag",
]


def all_companies_view(records: list[dict]) -> pd.DataFrame:
    """The all-companies grid (DASHBOARD_DESIGN.md §5 Tab 1). `pursue` is the one editable column (Phase 3
    fills it); the rest are read-only ledger-derived. Tags/scores render in the collapsible group in the view."""
    rows = [{
        "pursue": bool(r.get("pursue")),
        "company": r["company"],
        "final_priority": r["final_priority"],
        "model_priority": r["model_priority"],
        "provenance": r["provenance"],
        "segment": r["segment_label"],
        "model": r["model"],
        "stage": r["stage"],
        "FINAL": r["final_display"],
        "subsegment_tags": "; ".join(r["tags"]["subsegment"]),
        "product_model_tags": "; ".join(r["tags"]["product_model"]),
        "distribution_model_tags": "; ".join(r["tags"]["distribution_model"]),
        "data_input_tags": "; ".join(r["tags"]["data_input"]),
        "background_fit": r["bg_display"],
        "PMF": r["scores"]["pmf"],
        "ARR": r["scores"]["arr"],
        "growth": r["scores"]["growth"],
        "strain": r["scores"]["strain"],
        "key_flag": r["key_flag"],
    } for r in records]
    return pd.DataFrame(rows, columns=ALL_COMPANIES_COLUMNS)


def coverage_read(company_count: int, desirable_count: int) -> str:
    """LOCKED thresholds (§5 Tab 4): Strong = ≥3 companies AND ≥2 P0–P2; Directional = ≥2 AND ≥1; else Sparse."""
    if company_count >= COVERAGE_STRONG_COMPANIES and desirable_count >= COVERAGE_STRONG_DESIRABLE:
        return "Strong"
    if company_count >= COVERAGE_DIRECTIONAL_COMPANIES and desirable_count >= COVERAGE_DIRECTIONAL_DESIRABLE:
        return "Directional"
    return "Sparse"


SEGMENT_RADAR_COLUMNS = ["segment", "companies", "P0", "P1", "P2", "P3", "desirable", "pursuing", "coverage"]


def segment_radar_view(records: list[dict]) -> pd.DataFrame:
    """The segment radar (§5 Tab 4): one row per segment label, tier counts + desirable (P0–P2) + pursuing +
    coverage read. Answers 'where am I thin by segment' across all gated companies. Sorted by coverage strength
    then desirable count desc."""
    agg: dict[str, dict] = {}
    for r in records:
        seg = r["segment_label"] or r["segment_code"] or "(unlabeled)"
        bucket = agg.setdefault(seg, {"companies": 0, "P0": 0, "P1": 0, "P2": 0, "P3": 0, "pursuing": 0})
        bucket["companies"] += 1
        tier = r["final_priority"]
        if tier in bucket:
            bucket[tier] += 1
        if r.get("pursue"):
            bucket["pursuing"] += 1

    rows = []
    for seg, b in agg.items():
        desirable = sum(b[t] for t in DESIRABLE_TIERS)
        rows.append({
            "segment": seg, "companies": b["companies"],
            "P0": b["P0"], "P1": b["P1"], "P2": b["P2"], "P3": b["P3"],
            "desirable": desirable, "pursuing": b["pursuing"],
            "coverage": coverage_read(b["companies"], desirable),
        })
    order = {"Strong": 0, "Directional": 1, "Sparse": 2}
    rows.sort(key=lambda x: (order.get(x["coverage"], 9), -x["desirable"], -x["companies"], x["segment"]))
    return pd.DataFrame(rows, columns=SEGMENT_RADAR_COLUMNS)


# ---------------------------------------------------------------------------
# THE LIVING LAYER (Phase 3) — merge the durable user store into the records.
#
# Your editable layer lives in a durable store (a workbook: a Workspace tab keyed one-row-per-company +
# a Contacts tab, one-row-per-contact — DASHBOARD_DESIGN.md §3/§5). The dashboard REBUILDS the ledger side
# fresh each run, then merges your side in by COMPANY NAME: ledger columns refresh (no drift), YOUR columns are
# carried through untouched (Rule 6), and any column you added yourself is preserved. Two safety signals are
# surfaced (never silently resolved — no one is watching the run): a pursued company whose priority/segment
# CHANGED since you last looked, and a company you have notes on that DROPPED from the reviewed ledger.
# The engine is format-agnostic (operates on rows); the workbook read/write + edit sync-back is Phase 4.
# ---------------------------------------------------------------------------

# The Workspace tab: engine-managed keys (change-detection snapshot) + `company`/`pursue` are reserved; every
# OTHER column is yours and is preserved verbatim across runs (seed set below, but you may add more).
WORKSPACE_RESERVED_KEYS = {"company", "pursue", "last_seen_priority", "last_seen_segment"}
WORKSPACE_USER_COLUMNS = ["status", "next_step", "HQ", "desirability_notes", "deep_dive_notes", "last_updated"]
CONTACTS_COLUMNS = ["company", "contact", "title", "their_org", "relationship", "warm_intro_path",
                    "email_or_linkedin", "ask_status", "notes"]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _txt(value).lower() in ("true", "1", "yes", "y", "x")


def _index_rows(rows: Any) -> dict:
    """Group store rows (a DataFrame or list of dicts) by normalized company -> list of rows."""
    if rows is None:
        return {}
    records = rows.fillna("").to_dict("records") if isinstance(rows, pd.DataFrame) else list(rows)
    out: dict[str, list] = {}
    for rec in records:
        key = _norm_company(rec.get("company"))
        if key:
            out.setdefault(key, []).append(rec)
    return out


def merge_user_layer(records: list[dict], workspace: Any = None, contacts: Any = None) -> tuple[list[dict], dict]:
    """Merge the durable user store into the (freshly rebuilt) records, by company. Sets `pursue`, attaches the
    preserved `workspace` dict (all your columns, including ones you added) and the `contacts` list, and computes
    the `changed` signal from the stored snapshot. Returns `(records, report)` where report surfaces the two
    safety signals: `orphaned_workspace` / `orphaned_contacts` (notes on a company no longer in the ledger) and
    `changed` (a pursued company whose priority/segment moved). Never mutates the ledger side."""
    ws_index = _index_rows(workspace)
    ct_index = _index_rows(contacts)
    record_keys = {_norm_company(r.get("company")) for r in records}

    changed: list[dict] = []
    for record in records:
        key = _norm_company(record.get("company"))
        ws_rows = ws_index.get(key)
        ws = ws_rows[0] if ws_rows else {}       # one row per company on the Workspace tab
        record["pursue"] = _truthy(ws.get("pursue")) if ws else False
        record["workspace"] = {k: v for k, v in ws.items() if k not in WORKSPACE_RESERVED_KEYS}
        record["contacts"] = ct_index.get(key, [])

        record["changed"] = None
        if ws:
            last_priority = _txt(ws.get("last_seen_priority"))
            last_segment = _txt(ws.get("last_seen_segment"))
            deltas = {}
            if last_priority and last_priority != record["final_priority"]:
                deltas["priority"] = {"from": last_priority, "to": record["final_priority"]}
            if last_segment and last_segment != record["segment_label"]:
                deltas["segment"] = {"from": last_segment, "to": record["segment_label"]}
            if deltas:
                record["changed"] = deltas
                changed.append({"company": record["company"], **deltas})

    orphaned_workspace = sorted(
        _txt(rows[0].get("company")) for key, rows in ws_index.items() if key not in record_keys)
    orphaned_contacts = sorted(
        {_txt(rows[0].get("company")) for key, rows in ct_index.items() if key not in record_keys})

    report = {"orphaned_workspace": orphaned_workspace, "orphaned_contacts": orphaned_contacts, "changed": changed}
    return records, report


def next_workspace_store(records: list[dict]) -> pd.DataFrame:
    """The Workspace tab to persist back after a run: one row per pursued company, carrying `pursue`, your
    columns verbatim, and a REFRESHED `last_seen_priority` / `last_seen_segment` snapshot (the reference point
    for next run's 'changed since you last looked'). Companies you're not pursuing drop off the tab. Any extra
    columns you added are preserved (union of all workspace keys seen)."""
    pursued = [r for r in records if r.get("pursue")]
    extra_cols: list[str] = []
    for r in pursued:
        for k in (r.get("workspace") or {}):
            if k not in WORKSPACE_USER_COLUMNS and k not in extra_cols:
                extra_cols.append(k)
    user_cols = WORKSPACE_USER_COLUMNS + extra_cols

    rows = []
    for r in pursued:
        ws = r.get("workspace") or {}
        row = {"company": r["company"], "pursue": True}
        for col in user_cols:
            row[col] = ws.get(col, "")
        row["last_seen_priority"] = r["final_priority"]
        row["last_seen_segment"] = r["segment_label"]
        rows.append(row)
    columns = ["company", "pursue"] + user_cols + ["last_seen_priority", "last_seen_segment"]
    return pd.DataFrame(rows, columns=columns)


def pursuit_view(records: list[dict]) -> pd.DataFrame:
    """The Pursuit tab (§5 Tab 2): pursued companies only, ledger columns refreshed + your workspace columns,
    plus a `changed` note when priority/segment moved since you last looked. One row per company."""
    pursued = [r for r in records if r.get("pursue")]
    extra_cols: list[str] = []
    for r in pursued:
        for k in (r.get("workspace") or {}):
            if k not in WORKSPACE_USER_COLUMNS and k not in extra_cols:
                extra_cols.append(k)
    user_cols = WORKSPACE_USER_COLUMNS + extra_cols
    ledger_cols = ["company", "final_priority", "model_priority", "segment", "stage", "FINAL", "changed"]

    rows = []
    for r in pursued:
        ws = r.get("workspace") or {}
        changed = r.get("changed")
        note = "; ".join(f"{k} {v['from']}→{v['to']}" for k, v in changed.items()) if changed else ""
        row = {"company": r["company"], "final_priority": r["final_priority"],
               "model_priority": r["model_priority"], "segment": r["segment_label"],
               "stage": r["stage"], "FINAL": r["final_display"], "changed": note}
        for col in user_cols:
            row[col] = ws.get(col, "")
        rows.append(row)
    return pd.DataFrame(rows, columns=ledger_cols + user_cols)


def contacts_view(records: list[dict]) -> pd.DataFrame:
    """The Contacts tab (§5 Tab 3): one row per contact across pursued companies, in the fixed schema, preserving
    any extra columns you added."""
    extra_cols: list[str] = []
    rows = []
    for r in records:
        for contact in (r.get("contacts") or []):
            for k in contact:
                if k not in CONTACTS_COLUMNS and k not in extra_cols:
                    extra_cols.append(k)
            rows.append({**{c: _txt(contact.get(c)) for c in CONTACTS_COLUMNS},
                         **{c: contact.get(c) for c in extra_cols}})
    return pd.DataFrame(rows, columns=CONTACTS_COLUMNS + extra_cols)
