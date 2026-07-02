"""
Scoring ledger — the GATE-2 master (MASTER_REDESIGN_SPEC §3.4 / §4).

Turns ONE `structured_evidence.score_company` record (+ its research row, for context and the
render-time evidence join) into a ledger ENTRY: the write-once scoring block, the gates, the
`model_priority`, the routing (`recommended_action` / `override_candidate` / `flags`), the per-entry
`framework_version` stamp (read live from the SOT — never hardcoded stale), and the empty human-writable
`decision` block. Derived-on-read helpers (`final_priority` / `provenance` / code / rank) are computed,
never stored (§3.1).

Design decisions locked with Katelynd (2026-07-02, see MASTER_REDESIGN_SPEC §4 render design):
  - Scores are write-once and NEVER hand-edited (Rule 8); the `decision` block is the only mutable region,
    and it changes PRIORITY only (Rule 6). This module BUILDS entries; the decision round-trip is a later commit.
  - A DOCUMENTED priority override (the scorer's `human_override`, e.g. Function Health) is NOT pre-applied
    to `decision.human_override`. It makes the company an `override_candidate` (→ a card + `review_override`),
    and `model_priority` stays the pure §B call. Katelynd makes the actual call at the gate. (Matches the §3.4
    entry example: Function Health = model_priority P3 + override_candidate true + decision.human_override null.)
  - Display labels ("Background Fit" / "Product Market Fit") are a render concern; the JSONL keys stay bg_fit/pmf.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PRIORITY_TIERS = ("P0", "P1", "P2", "P3")
PRIORITY_RANK = {tier: i for i, tier in enumerate(PRIORITY_TIERS)}

# Flag partition (MASTER_REDESIGN_SPEC §4 routing): the floor-VERDICT flags state WHY a company floored
# (they do not, by themselves, demand extra review); the data-QUALITY warns are the ones that route a
# floor-PASS company to `review_override`.
FLOOR_VERDICT_FLAGS = frozenset({"b2b_floor", "agency_floor", "low_score_floor"})
DATA_QUALITY_WARN = frozenset({"data_gap", "evidence_thin", "fence_leak", "under_extract", "leak_discounted"})

_SOT_FILENAME = "SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md"
_FRAMEWORK_VERSION_RE = re.compile(r"FRAMEWORK_VERSION:\s*(v\d+(?:\.\d+)*)", re.I)


class LedgerError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# framework_version — the per-entry staleness stamp (§2/§3.1), read LIVE from the SOT.
# ---------------------------------------------------------------------------

def _default_sot_path() -> Path:
    """Locate the scoring SOT relative to the package: src/health_tech_research_agent/ledger.py -> repo root."""
    return Path(__file__).resolve().parents[2] / "specs" / _SOT_FILENAME


def read_framework_version(sot_path: str | Path | None = None) -> str:
    """Read `FRAMEWORK_VERSION` from the scoring SOT header (e.g. 'v1.25'). Raises `LedgerError` if the SOT
    can't be read or carries no version — the stamp is load-bearing (an entry with no version is a silent
    staleness hole), so we fail loudly rather than stamp a guess."""
    path = Path(sot_path) if sot_path else _default_sot_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LedgerError(f"Cannot read the scoring SOT to stamp framework_version: {path} ({exc})") from exc
    match = _FRAMEWORK_VERSION_RE.search(text)
    if not match:
        raise LedgerError(f"No FRAMEWORK_VERSION found in {path}")
    return match.group(1)


# ---------------------------------------------------------------------------
# small value helpers
# ---------------------------------------------------------------------------

def _txt(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none") else text


def _num(value: Any):
    """Return an int/float score, or None (bool is NOT a number here — guards True/False leaking as 1/0)."""
    if isinstance(value, bool):
        return None
    return value if isinstance(value, (int, float)) else None


def _loop(value: Any):
    """data_feedback_loop 'yes'/'no' -> True/False, else None (absent)."""
    text = _txt(value).lower()
    return True if text == "yes" else (False if text == "no" else None)


# ---------------------------------------------------------------------------
# routing (§4): override_candidate -> recommended_action -> flags
# ---------------------------------------------------------------------------

def override_candidate(rec: dict) -> bool:
    """§4: a documented priority override (the scorer's `human_override`, which comes ONLY from
    DOCUMENTED_PRIORITY_OVERRIDES) OR `floored_on_bg` (floored solely on a low/uncertain bg read — a possible
    real prospect frozen low). Earns a card's attention even at P3; no longer gates card eligibility."""
    return rec.get("human_override") is not None or bool(rec.get("floored_on_bg"))


def build_flags(rec: dict) -> list[dict]:
    """Map the scorer's real signals to the §3.5 flag vocabulary (mapping LOCKED 2026-07-02). Each flag is
    `{type, severity (info|warn), note}` and names the rule that fired + its scoring impact."""
    bm = _txt(rec.get("business_model")).upper()
    path_passed = bool(rec.get("path_passed"))
    agency_passed = bool(rec.get("agency_passed"))
    gate_floored = bool(rec.get("gate_floored"))
    floor_ok = bool(rec.get("floor_ok"))
    flags: list[dict] = []

    if not path_passed and bm == "B2B":
        flags.append({"type": "b2b_floor", "severity": "warn",
                      "note": "PATH Test A — human-locked B2B floor list → not scored, capped at P3"})
    if path_passed and not agency_passed:
        flags.append({"type": "agency_floor", "severity": "warn",
                      "note": "AGENCY gate — out of the build window → capped at P3"})
    if not gate_floored and not floor_ok:
        flags.append({"type": "low_score_floor", "severity": "warn",
                      "note": "Floor rule (Background Fit or Product Market Fit ≤ 4) → capped at P3 regardless of FINAL"})
    if "FENCED" in _txt(rec.get("growth_note")).upper():
        flags.append({"type": "data_gap", "severity": "warn",
                      "note": "Growth signal is a count/scale, not a revenue series — growth held to UNKNOWN by the fence"})
    if override_candidate(rec):
        why = ("documented priority-override candidate" if rec.get("human_override") is not None
               else "floored solely on a low/uncertain Background Fit read — a possible frozen-low prospect")
        flags.append({"type": "override_candidate", "severity": "info", "note": why})
    if bool(rec.get("tier_review")):
        flags.append({"type": "tier_review", "severity": "info",
                      "note": "FINAL sits within ±1 of a tier boundary — a nudge would change the tier"})
    return flags


def recommended_action(rec: dict, flags: list[dict] | None = None) -> str:
    """§4 routing (rules LOCKED 2026-07-02):
      review_override — a human override exists / override_candidate / tier_review / a data-QUALITY warn flag.
      accept          — a clean gate-floor (bulk-confirm the floor) OR a clear P0 with nothing flagged.
      normal          — everything else (a quick confirm).
    Note the floor-VERDICT flags (b2b/agency/low_score) do NOT force review_override — a clean floor is
    `accept`-able; only data-quality warns pull a company in for a closer look."""
    flags = build_flags(rec) if flags is None else flags
    flag_types = {f["type"] for f in flags}
    if (override_candidate(rec) or bool(rec.get("tier_review")) or (flag_types & DATA_QUALITY_WARN)):
        return "review_override"
    if bool(rec.get("gate_floored")) or _txt(rec.get("model_priority")).upper() == "P0":
        return "accept"
    return "normal"


# ---------------------------------------------------------------------------
# entry builder (§3.4)
# ---------------------------------------------------------------------------

def _floor_rule_reason(bf, pmf, floor_ok: bool) -> str:
    """The floor-RULE-specific reason (bg_fit > 4 AND pmf > 4), in human labels. Distinct from a gate floor
    (that reads in the gates block) — this is the §B7 Low-Score floor, and it separates a genuine low score
    from a bg READ-FAILURE (None)."""
    if floor_ok:
        return f"Background Fit {bf} and Product Market Fit {pmf} both > 4 — passes"
    parts = []
    parts.append("Background Fit READ-FAILED (None — re-take)" if bf is None
                 else (f"Background Fit {bf} (≤ 4)" if bf <= 4 else f"Background Fit {bf}"))
    parts.append("Product Market Fit READ-FAILED (None)" if pmf is None
                 else (f"Product Market Fit {pmf} (≤ 4)" if pmf <= 4 else f"Product Market Fit {pmf}"))
    return "; ".join(parts) + " — the floor gate needs BOTH > 4"


def _arr_basis(arr, revenue_text: str, stage: str) -> str:
    if arr is None:
        return "no revenue figure found (Scale A)"
    return f"{revenue_text} @ {stage} (Scale A)" if revenue_text else f"Scale A @ {stage}"


def build_entry(score_record: dict, row: dict | None = None, *, batch_id: str, date_scored: str,
                framework_version: str | None = None) -> dict:
    """Build ONE ledger entry (MASTER_REDESIGN_SPEC §3.4) from a `score_company` record + its research row.

    `score_record` is `structured_evidence.score_company`'s output (post-2026-07-02 rationale passthrough);
    `row` is the research row (for `one_liner` / `stage_basis` context and the render-time evidence join) —
    optional so the builder is unit-testable from a pure record. Scores are copied write-once; the `decision`
    block is emitted EMPTY (Katelynd fills it at the gate). `framework_version` defaults to the live SOT read."""
    rec = dict(score_record)
    row = dict(row) if row is not None else {}
    fv = framework_version or read_framework_version()

    bm = _txt(rec.get("business_model"))
    stage = _txt(rec.get("funding_stage"))
    bf = _num(rec.get("background_fit"))
    pmf = _num(rec.get("pmf"))
    arr = _num(rec.get("arr_level"))
    growth = _num(rec.get("growth"))
    strain = _num(rec.get("strain")) or 0

    path_passed = bool(rec.get("path_passed"))
    agency_passed = bool(rec.get("agency_passed"))
    floor_ok = bool(rec.get("floor_ok"))
    model_priority = _txt(rec.get("model_priority")).upper() or "P3"
    revenue_text = _txt(rec.get("revenue_or_arr")) or _txt(row.get("revenue_or_arr"))

    flags = build_flags(rec)

    return {
        "company": _txt(rec.get("company")),
        "batch_id": batch_id,
        "framework_version": fv,
        "date_scored": date_scored,

        # CONTEXT (re-derivable from research; for judging, not authored here)
        "model": bm,
        "stage": stage,
        "stage_basis": _txt(row.get("stage_basis") or row.get("maturity_basis")),
        "one_liner": _txt(row.get("one_liner") or row.get("description") or row.get("company_one_liner")),

        # SCORING (write-once, never hand-edited — Rule 8)
        "scoring": {
            "bg_fit": {"score": bf, "loop": _loop(rec.get("data_feedback_loop")),
                       "rationale": _txt(rec.get("background_fit_basis"))},
            "pmf": {"score": pmf,
                    "arr_level": {"score": arr, "basis": _arr_basis(arr, revenue_text, stage)},
                    "growth": {"score": growth, "basis": _txt(rec.get("growth_note") or rec.get("growth_evidence"))},
                    "rationale": f"0.4·ARR + 0.6·Growth (ARR {arr}, Growth {growth})"},
            "strain": {"score": strain, "strength": _txt(rec.get("strain_strength")),
                       "rationale": _txt(rec.get("strain_rationale"))},
            "final_score": rec.get("final_score"),
            "floor_rule": {"passed": floor_ok, "reason": _floor_rule_reason(bf, pmf, floor_ok)},
        },

        # GATES
        "gates": {
            "path": {"passed": path_passed, "detail": _txt(rec.get("path_detail"))},
            "agency": {"passed": agency_passed, "detail": _txt(rec.get("agency_detail")),
                       "reset": _txt(rec.get("reset_detail"))},
            "b2b_floor": (not path_passed) and bm.upper() == "B2B",
        },

        # MODEL OUTPUT + REVIEW ROUTING (write-once)
        "model_priority": model_priority,
        "recommended_action": recommended_action(rec, flags),
        "override_candidate": override_candidate(rec),
        "flags": flags,

        # DECISION — the ONLY human-writable region (priority + taxonomy; emitted EMPTY at build)
        "decision": {
            "human_override": None,
            "override_reason": None,
            "taxonomy_override": None,
            "taxonomy_override_reason": None,
            "decided_date": None,
            "decided_at_gate": None,
            "history": [],
        },
    }


# ---------------------------------------------------------------------------
# DERIVED ON READ (§3.1 — computed, NEVER stored)
# ---------------------------------------------------------------------------

def final_priority(entry: dict) -> str:
    """`decision.human_override` if set, else `model_priority`."""
    override = entry.get("decision", {}).get("human_override")
    return _txt(override) if _txt(override) else _txt(entry.get("model_priority"))


def provenance(entry: dict) -> str:
    """OVERRIDE-ONLY (§3.2): 'human-overridden' if an override is set, else 'model-accepted' (reviewed-and-
    accepted is guaranteed by the GATE INVARIANT — nothing reaches the dashboard un-gated)."""
    return "human-overridden" if _txt(entry.get("decision", {}).get("human_override")) else "model-accepted"


def final_priority_code(entry: dict) -> str:
    """The tier letter (the tier IS the code; domain P0–P3)."""
    return final_priority(entry)


def final_priority_rank(entry: dict):
    """Sort key = FINAL score (finer than the 4-bucket tier). Absent FINAL sorts last via the tier rank."""
    score = _num(entry.get("scoring", {}).get("final_score"))
    return score if score is not None else -PRIORITY_RANK.get(final_priority(entry), 99)
