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

import copy
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from . import storage
from . import structured_evidence as se

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
    """Resolve the per-entry framework-version stamp.

    In a repo checkout the SOT doc IS present, so we read it live (never stamp a stale guess). When the
    package is pip-installed the SOT isn't shipped alongside it, so we fall back to the shipped
    `structured_evidence.FRAMEWORK_VERSION` constant (kept in lockstep with the SOT header; a test enforces
    it). An EXPLICIT `sot_path` is authoritative — a missing/invalid file there raises (Rule 5, no silent
    guess) rather than falling back."""
    explicit = sot_path is not None
    path = Path(sot_path) if explicit else _default_sot_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        if explicit:
            raise LedgerError(f"Cannot read the scoring SOT to stamp framework_version: {path} ({exc})") from exc
        return se.FRAMEWORK_VERSION          # pip-installed: SOT doc not packaged -> shipped constant
    match = _FRAMEWORK_VERSION_RE.search(text)
    if not match:
        if explicit:
            raise LedgerError(f"No FRAMEWORK_VERSION found in {path}")
        return se.FRAMEWORK_VERSION
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


def _parse_fit_brief_row(row) -> dict:
    """Parse a research row's fit_brief_json (dict / JSON string / blank) to a dict, tolerant of malformed."""
    raw = row.get("fit_brief_json") if hasattr(row, "get") else None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _stage_basis(row: dict, stage: str, company: str = "") -> str:
    """The one-line stage basis, ALIGNED to the resolved stage (via `resolve_stage_basis` — applies the same
    funding patches + human stage overrides scoring used, so the display can never contradict the stage).
    Display-only; feeds no scoring."""
    maturity = _parse_fit_brief_row(row).get("maturity_evidence")
    maturity = maturity if isinstance(maturity, dict) else {}
    return se.resolve_stage_basis(company, maturity.get("funding_rounds"), maturity.get("ipo_event"), stage) \
        or se.stage_label(stage)


def _taxonomy(row: dict) -> dict:
    """The MODEL's taxonomy classification, carried as re-derivable CONTEXT (2026-07-03) so the dashboard can
    group by market segment WITHOUT re-parsing the research at render time — same pattern as `model` / `stage`.
    `segment` is the controlled CODE (e.g. WOMENS_FAMILY_HEALTH); the dashboard joins
    `taxonomy/market_segments.csv` (segment_code -> segment_label) for display names. Not a scoring input; not
    the human `decision.taxonomy_override` (that's the B2B/B2C model, Rule 6)."""
    tax = _parse_fit_brief_row(row).get("taxonomy_classification")
    tax = tax if isinstance(tax, dict) else {}

    def _tags(key):
        value = tax.get(key)
        return [_txt(t) for t in value if _txt(t)] if isinstance(value, list) else []

    return {
        "segment": _txt(tax.get("primary_market_segment")),
        "subsegment_tags": _tags("subsegment_tags"),
        "product_model_tags": _tags("product_model_tags"),
        "distribution_model_tags": _tags("distribution_model_tags"),
        "data_input_tags": _tags("data_input_tags"),
        "rationale": _txt(tax.get("classification_rationale")),
    }


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
    is_consumer = bm.upper() != "B2B"   # background fit is a CONSUMER measure — n/a for a B2B/professional co
    stage = _txt(rec.get("funding_stage"))
    bf = _num(rec.get("background_fit")) if is_consumer else None
    pmf = _num(rec.get("pmf"))
    arr = _num(rec.get("arr_level"))
    growth = _num(rec.get("growth"))
    strain = _num(rec.get("strain")) or 0
    # A B2B company has no consumer end-user, so bg is n/a and FINAL can't fully compute (it needs bg). The
    # other components (ARR / Growth / Strain) still compute — floors cap PRIORITY, not scoring (§4).
    bg_rationale = (_txt(rec.get("background_fit_basis")) if is_consumer
                    else "n/a — no consumer end-user (background fit is a consumer measure)")
    final_score = rec.get("final_score") if is_consumer else None

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
        "stage_basis": _stage_basis(row, stage, _txt(rec.get("company"))),
        "one_liner": "",   # no clean product/service source in the research output (2026-07-02) — skipped
        "taxonomy": _taxonomy(row),   # market segment (code) + nuance tags — for dashboard grouping (2026-07-03)

        # SCORING (write-once, never hand-edited — Rule 8)
        "scoring": {
            "bg_fit": {"score": bf, "loop": _loop(rec.get("data_feedback_loop")) if is_consumer else None,
                       "rationale": bg_rationale},
            "pmf": {"score": pmf,
                    "arr_level": {"score": arr, "basis": _arr_basis(arr, revenue_text, stage)},
                    "growth": {"score": growth, "basis": _txt(rec.get("growth_note") or rec.get("growth_evidence"))},
                    "rationale": f"0.4·ARR + 0.6·Growth (ARR {arr}, Growth {growth})"},
            "strain": {"score": strain, "strength": _txt(rec.get("strain_strength")),
                       "rationale": _txt(rec.get("strain_rationale"))},
            "final_score": final_score,
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


def is_reviewed(entry: dict) -> bool:
    """§1a GATE INVARIANT: has this entry passed GATE-2 review? True once `finalize_gate2_review` has stamped it
    (`decision.reviewed_date`). The dashboard enforces the invariant by refusing any entry where this is False —
    presence in the dashboard ⟹ reviewed. Distinct from `provenance` (accepted-vs-overridden): an accepted entry
    is still reviewed."""
    return bool(_txt(entry.get("decision", {}).get("reviewed_date")))


def final_priority_code(entry: dict) -> str:
    """The tier letter (the tier IS the code; domain P0–P3)."""
    return final_priority(entry)


def final_priority_rank(entry: dict):
    """Sort key = FINAL score (finer than the 4-bucket tier). Absent FINAL sorts last via the tier rank."""
    score = _num(entry.get("scoring", {}).get("final_score"))
    return score if score is not None else -PRIORITY_RANK.get(final_priority(entry), 99)


# ---------------------------------------------------------------------------
# PERSISTENCE (Commit C) — the durable ledger.jsonl master, written transactionally.
#
# One JSON entry per line (JSONL): git-diffable, append-friendly, clean for the nested scoring/decision/
# history/flags. The write mirrors the master_update transactional discipline (Rule 4/5): back up the
# existing ledger, write, REOPEN + PARSE + validate it equals what we intended, roll back on any mismatch.
# "Wrote the file" is not "done" — "reopened the file and confirmed its contents" is.
# ---------------------------------------------------------------------------

@dataclass
class LedgerWriteResult:
    path: str
    entries_written: int
    readback_ok: bool
    backup_path: str = ""
    rollback_performed: bool = False


def _entry_company(entry: dict) -> str:
    return _txt(entry.get("company"))


def _validate_unique_companies(entries: list[dict]) -> None:
    """The ledger is keyed by company — a duplicate is a merge/append bug, refuse before writing."""
    seen: set[str] = set()
    dupes: set[str] = set()
    for entry in entries:
        key = _entry_company(entry).lower()
        if key in seen:
            dupes.add(_entry_company(entry))
        seen.add(key)
    if dupes:
        raise LedgerError(f"Duplicate company entries in ledger: {sorted(dupes)}")


def _canonical(entries: list[dict]) -> list[dict]:
    """JSON round-trip so the comparison matches what a read-back yields (tuples->lists, key order, etc.)."""
    return [json.loads(json.dumps(entry, ensure_ascii=False)) for entry in entries]


def write_ledger(path: str | Path, entries: list[dict]) -> Path:
    """Atomically write `entries` as JSONL (one entry per line). Not transactional on its own — use
    `execute_ledger_write` for the backup + read-back + rollback discipline."""
    text = "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries)
    return storage.atomic_write_text(path, text)


def read_ledger(path: str | Path) -> list[dict]:
    """Parse a ledger.jsonl back into a list of entry dicts. A missing file -> [] (an empty ledger).
    A malformed / non-object line RAISES `LedgerError` (a corrupt ledger must be loud, never silently
    dropped — Rule 5)."""
    p = Path(path)
    if not p.exists():
        return []
    entries: list[dict] = []
    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            raise LedgerError(f"{p} line {lineno}: invalid JSON ({exc})") from exc
        if not isinstance(obj, dict):
            raise LedgerError(f"{p} line {lineno}: entry is not a JSON object")
        entries.append(obj)
    return entries


def _validate_readback(written: list[dict], readback: list[dict]) -> None:
    if len(written) != len(readback):
        raise LedgerError(f"Ledger read-back count mismatch: wrote {len(written)}, read {len(readback)}")
    canonical = _canonical(written)
    if canonical != readback:
        for i, (a, b) in enumerate(zip(canonical, readback)):
            if a != b:
                raise LedgerError(f"Ledger read-back mismatch at entry {i} ({a.get('company')!r})")
        raise LedgerError("Ledger read-back mismatch")


def execute_ledger_write(path: str | Path, entries: list[dict], *,
                         artifacts_dir: str | Path | None = None) -> LedgerWriteResult:
    """Transactionally write the ledger (Rule 4/5): validate unique keys -> back up any existing ledger ->
    write -> REOPEN + parse + validate it equals what we intended -> roll back to the backup on ANY failure.
    Returns a `LedgerWriteResult`; raises `LedgerError` (after rolling back) if the write can't be verified."""
    path = Path(path)
    _validate_unique_companies(entries)

    backup_path = ""
    if path.exists():
        adir = Path(artifacts_dir) if artifacts_dir else path.parent
        adir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = str(adir / f"{path.stem}_backup_{stamp}{path.suffix or '.jsonl'}")
        shutil.copy2(path, backup_path)

    try:
        write_ledger(path, entries)
        readback = read_ledger(path)
        _validate_readback(entries, readback)
    except Exception as exc:
        rollback_performed = False
        if backup_path:
            try:
                shutil.copy2(backup_path, path)
                rollback_performed = True
            except Exception as rollback_exc:
                raise LedgerError(
                    f"Ledger write failed AND rollback failed: {exc}; rollback: {rollback_exc}"
                ) from exc
        raise LedgerError(f"Ledger write failed (rolled_back={rollback_performed}): {exc}") from exc

    return LedgerWriteResult(path=str(path), entries_written=len(entries), readback_ok=True,
                             backup_path=backup_path, rollback_performed=False)


# ---------------------------------------------------------------------------
# DECISION ROUND-TRIP (Commit D) — render cards.csv -> Katelynd edits priority -> merge back into the ledger.
#
# cards.csv is the single decision-writing surface (Rule 3). Katelynd edits PRIORITY ONLY (2026-07-02): the
# `human_override` (a tier, or blank = accept the model) + an `override_reason`. `apply_decisions` merges her
# edits into the `decision` block ONLY — scores/gates/model_priority are NEVER touched (Rule 8) — appending
# each change to the append-only `history`; the human override then WINS on read (Rule 6, via final_priority).
# ---------------------------------------------------------------------------

# Read-only context columns (so a decision has its facts beside it) + the two editable priority columns.
CARDS_CONTEXT_COLUMNS = ["company", "Segment", "Model", "Stage", "Stage basis", "Model priority",
                         "Recommended action", "Final priority", "Background Fit", "Background Fit rationale",
                         "Product Market Fit", "ARR", "ARR basis", "Growth", "Growth basis", "Strain",
                         "Strain rationale", "FINAL", "Floor reason", "Agency", "Key flags"]
CARDS_DECISION_COLUMNS = ["human_override", "override_reason"]


def render_cards_csv(entries: list[dict]) -> pd.DataFrame:
    """The review-and-decide card, one row per company (2026-07-02): the full drafted card as read-only
    columns (scores + rationales + floor reason + flags) plus the two editable PRIORITY columns
    (`human_override` / `override_reason`), pre-filled from the current decision so the CSV round-trips.
    `company` + the two decision columns keep machine names for `apply_decisions`; the rest use display labels."""
    rows = []
    for entry in entries:
        scoring = entry.get("scoring", {})
        pmf = scoring.get("pmf", {})
        arr = pmf.get("arr_level", {})
        growth = pmf.get("growth", {})
        strain = scoring.get("strain", {})
        bg = scoring.get("bg_fit", {})
        decision = entry.get("decision", {})
        rows.append({
            "company": _txt(entry.get("company")),
            "Segment": _txt(entry.get("taxonomy", {}).get("segment")),
            "Model": _txt(entry.get("model")),
            "Stage": _txt(entry.get("stage")),
            "Stage basis": _txt(entry.get("stage_basis")),
            "Model priority": _txt(entry.get("model_priority")),
            "Recommended action": _txt(entry.get("recommended_action")),
            "Final priority": final_priority(entry),
            "Background Fit": _bg_display(entry),
            "Background Fit rationale": _txt(bg.get("rationale")),
            "Product Market Fit": pmf.get("score"),
            "ARR": arr.get("score"),
            "ARR basis": _txt(arr.get("basis")),
            "Growth": growth.get("score"),
            "Growth basis": _txt(growth.get("basis")),
            "Strain": strain.get("score"),
            "Strain rationale": _strain_detail(entry),
            "FINAL": _final_display(entry),
            "Floor reason": floor_summary(entry),
            "Agency": _agency_detail(entry),
            "Key flags": "; ".join(_txt(f.get("type")) for f in entry.get("flags", [])),
            "human_override": _txt(decision.get("human_override")),
            "override_reason": _txt(decision.get("override_reason")),
        })
    return pd.DataFrame(rows, columns=CARDS_CONTEXT_COLUMNS + CARDS_DECISION_COLUMNS)


def write_cards_csv(path: str | Path, entries: list[dict]) -> Path:
    return storage.atomic_write_csv(path, render_cards_csv(entries))


def read_cards_csv(path: str | Path) -> list[dict]:
    """Read an edited cards.csv back into per-company decision dicts (blank cells -> '')."""
    df = storage.load_csv(path).fillna("")
    return [{key: _txt(value) for key, value in record.items()} for record in df.to_dict("records")]


def _norm_override(value: Any):
    """A priority override is a tier (P0–P3) or blank (= accept the model, clears any prior override)."""
    text = _txt(value).upper()
    if text == "":
        return None
    if text not in PRIORITY_RANK:
        raise LedgerError(f"Invalid priority override {value!r} (expected one of {list(PRIORITY_TIERS)} or blank)")
    return text


def _append_history(decision: dict, field: str, frm, to, date: str, reason) -> None:
    decision.setdefault("history", []).append(
        {"date": date, "field": field, "from": frm, "to": to, "reason": reason})


def apply_decisions(entries: list[dict], decisions: list[dict], *,
                    decided_date: str, decided_at_gate: str) -> list[dict]:
    """Merge Katelynd's cards.csv edits into a COPY of the ledger entries. PRIORITY ONLY: sets/changes/clears
    `decision.human_override` + `override_reason`, appends the change to `decision.history`, and stamps
    `decided_date`/`decided_at_gate`. Idempotent — re-applying an unchanged CSV is a no-op (no history churn).
    Scores/gates/model_priority are NEVER modified (Rule 8); a decision for a company not in the ledger RAISES
    (Rule 5 — no silent mismatch)."""
    result = [copy.deepcopy(entry) for entry in entries]
    index = {_txt(entry.get("company")).lower(): entry for entry in result}

    for row in decisions:
        company = _txt(row.get("company"))
        if not company:
            continue
        entry = index.get(company.lower())
        if entry is None:
            raise LedgerError(f"Decision for a company not in the ledger: {company!r}")

        decision = entry.setdefault("decision", {})
        old_override = _norm_override(decision.get("human_override"))
        old_reason = _txt(decision.get("override_reason")) or None
        new_override = _norm_override(row.get("human_override"))
        new_reason = _txt(row.get("override_reason")) or None

        if new_override != old_override:
            _append_history(decision, "human_override", old_override, new_override, decided_date, new_reason)
            decision["human_override"] = new_override
            decision["override_reason"] = new_reason
            decision["decided_date"] = decided_date
            decision["decided_at_gate"] = decided_at_gate
        elif new_reason != old_reason:
            _append_history(decision, "override_reason", old_reason, new_reason, decided_date, new_reason)
            decision["override_reason"] = new_reason
            decision["decided_date"] = decided_date
            decision["decided_at_gate"] = decided_at_gate
        # else: nothing changed for this company — no-op (idempotent).

    return result


def finalize_gate2_review(entries: list[dict], *, reviewed_date: str, reviewed_at_gate: str) -> list[dict]:
    """Stamp EVERY entry as GATE-2-reviewed (§1a enforcement primitive), on a COPY. Called ONCE when the GATE-2
    review is finalized — after `apply_decisions` — to mark the whole batch reviewed, whether an entry was
    overridden or accepted-unchanged. This is the belt-and-suspenders behind the gate invariant: the review flow
    already forces per-company review, but stamping every entry lets the dashboard REFUSE any un-stamped (un-gated)
    entry (see `is_reviewed`). Writes `decision.reviewed_date` / `reviewed_at_gate` ONLY — never scores/gates
    (Rule 8). Idempotent in effect; re-finalizing just refreshes the stamp (the reference point for the
    dashboard's 'changed since you last looked')."""
    result = [copy.deepcopy(entry) for entry in entries]
    for entry in result:
        decision = entry.setdefault("decision", {})
        decision["reviewed_date"] = reviewed_date
        decision["reviewed_at_gate"] = reviewed_at_gate
    return result


# ---------------------------------------------------------------------------
# RENDERED VIEWS (Commit E) — summary_table.csv (scan) + master_full_export.csv (all fields + all research).
#
# Read-only views over the ledger (Rule 3). Display-label convention (2026-07-02): human-facing CSV headers
# spell out "Background Fit" / "Product Market Fit"; the JSONL keys stay bg_fit / pmf. master_full_export
# JOINS the raw research findings at render time (the ledger stores no raw research — Option 2 holds).
# ---------------------------------------------------------------------------

SUMMARY_COLUMNS = ["Company", "Segment", "Model", "Stage", "Tier", "FINAL", "Key flag", "Recommendation",
                   "Floor reason"]


def floor_summary(entry: dict) -> str:
    """A one-line floor reason for the summary scan (blank for a passing company). Reads the floor SOURCE off
    the entry so a gate floor (Path/Agency) is legibly distinct from a Low-Score floor (floored-vs-low)."""
    gates = entry.get("gates", {})
    path = gates.get("path", {})
    agency = gates.get("agency", {})
    floor_rule = entry.get("scoring", {}).get("floor_rule", {})
    if not path.get("passed", True):
        kind = "B2B floor" if gates.get("b2b_floor") else "Path floor"
        return f"{kind}: {_txt(path.get('detail'))}".rstrip(": ").strip()
    if not agency.get("passed", True):
        return f"Agency floor: {_txt(agency.get('detail'))}".rstrip(": ").strip()
    if not floor_rule.get("passed", True):
        return f"Low score: {_txt(floor_rule.get('reason'))}".rstrip(": ").strip()
    return ""


def _key_flag(entry: dict) -> str:
    """The single most salient flag for the summary (a warn beats an info; else the first flag; else '')."""
    flags = entry.get("flags", [])
    warns = [f for f in flags if _txt(f.get("severity")) == "warn"]
    chosen = warns[0] if warns else (flags[0] if flags else None)
    return _txt(chosen.get("type")) if chosen else ""


def _bg_display(entry: dict):
    """Background Fit for a human view: the score; or 'n/a (no consumer end-user)' for a B2B company (bg is a
    consumer measure, undefined without a consumer); or '' for a genuine consumer read-gap."""
    score = _num(entry.get("scoring", {}).get("bg_fit", {}).get("score"))
    if score is not None:
        return score
    return "n/a (no consumer end-user)" if _txt(entry.get("model")).upper() == "B2B" else ""


def _final_display(entry: dict):
    """FINAL for a human view: the score; or 'n/a' for a B2B company (FINAL needs background fit); or ''."""
    final = _num(entry.get("scoring", {}).get("final_score"))
    if final is not None:
        return final
    return "n/a" if _txt(entry.get("model")).upper() == "B2B" else ""


def _strain_detail(entry: dict) -> str:
    """The Strain LOGIC for the card (2026-07-03) — strength + what drove it, not just the terse basis. Strain
    is a capability + speed-of-scale read: a2 ≥ 70 → STRONG (+2), ≥ 55 or a fast-scaling signal → MODERATE
    (+1), else WEAK (+0)."""
    strain = entry.get("scoring", {}).get("strain", {})
    strength = _txt(strain.get("strength"))
    basis = _txt(strain.get("rationale"))
    if basis.startswith("a2="):
        thr = "≥ 70 → strong" if strength == "STRONG" else ("≥ 55 → moderate" if strength == "MODERATE" else "")
        gloss = f"operating-capability score {basis[3:]}" + (f" ({thr})" if thr else "")
    elif "speed" in basis.lower():
        gloss = "a fast-scaling signal (e.g. rapid headcount growth)"
    else:
        gloss = "no strong capability or fast-scaling signal (default-low)"
    return f"{strength} — {gloss}" if strength else gloss


def _agency_detail(entry: dict) -> str:
    """The AGENCY gate result + any RESET for the card (2026-07-03) — so a late-stage company that passed via a
    reset (e.g. a first-ever C-suite hire reopening the build window) shows WHY it wasn't floored. Reset acts
    on the AGENCY gate, not strain — kept separate so the same event can't double-count."""
    agency = entry.get("gates", {}).get("agency", {})
    detail = _txt(agency.get("detail"))
    reset = _txt(agency.get("reset"))
    if not agency.get("passed", True):
        return f"Floored — {detail}" if detail else "Floored"
    # A reset only MATTERS when it reopened a would-have-floored window — agency_gate marks that with "+reset"
    # in the reason (public / series-d-plus only). An in-window series-a/b/c passes on its own, so a reset
    # firing there is irrelevant and must NOT be shown as "reopened by a reset" (2026-07-03 fix).
    if "+reset" in detail:
        return f"Pass — build window reopened by a reset [{reset}]"
    return f"Pass — {detail.replace('-> PASS', 'in-window')}" if detail else "Pass"


def render_summary_table(entries: list[dict]) -> pd.DataFrame:
    """The lean scan: Company · Model · Stage · Tier (final priority) · FINAL · Key flag · Recommendation ·
    Floor reason. Read-only."""
    rows = [{
        "Company": _txt(entry.get("company")),
        "Segment": _txt(entry.get("taxonomy", {}).get("segment")),
        "Model": _txt(entry.get("model")),
        "Stage": _txt(entry.get("stage")),
        "Tier": final_priority_code(entry),
        "FINAL": _final_display(entry),
        "Key flag": _key_flag(entry),
        "Recommendation": _txt(entry.get("recommended_action")),
        "Floor reason": floor_summary(entry),
    } for entry in entries]
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def flatten_entry(entry: dict) -> dict:
    """Flatten a ledger entry into readable, human-facing columns (display labels for the score fields).
    Nested lists (flags / history) serialize to JSON strings; derived fields are computed on read (§3.1)."""
    scoring = entry.get("scoring", {})
    bg = scoring.get("bg_fit", {})
    pmf = scoring.get("pmf", {})
    arr = pmf.get("arr_level", {})
    growth = pmf.get("growth", {})
    strain = scoring.get("strain", {})
    floor_rule = scoring.get("floor_rule", {})
    gates = entry.get("gates", {})
    path = gates.get("path", {})
    agency = gates.get("agency", {})
    decision = entry.get("decision", {})
    taxonomy = entry.get("taxonomy", {})
    return {
        "Company": _txt(entry.get("company")),
        "Batch": _txt(entry.get("batch_id")),
        "Framework version": _txt(entry.get("framework_version")),
        "Date scored": _txt(entry.get("date_scored")),
        "Segment": _txt(taxonomy.get("segment")),
        "Subsegment tags": "; ".join(taxonomy.get("subsegment_tags", [])),
        "Product model tags": "; ".join(taxonomy.get("product_model_tags", [])),
        "Distribution model tags": "; ".join(taxonomy.get("distribution_model_tags", [])),
        "Data input tags": "; ".join(taxonomy.get("data_input_tags", [])),
        "Model": _txt(entry.get("model")),
        "Stage": _txt(entry.get("stage")),
        "Stage basis": _txt(entry.get("stage_basis")),
        "Background Fit": _bg_display(entry),
        "Background Fit loop": bg.get("loop"),
        "Background Fit rationale": _txt(bg.get("rationale")),
        "Product Market Fit": pmf.get("score"),
        "ARR": arr.get("score"),
        "ARR basis": _txt(arr.get("basis")),
        "Growth": growth.get("score"),
        "Growth basis": _txt(growth.get("basis")),
        "Product Market Fit rationale": _txt(pmf.get("rationale")),
        "Strain": strain.get("score"),
        "Strain strength": _txt(strain.get("strength")),
        "Strain rationale": _txt(strain.get("rationale")),
        "FINAL": _final_display(entry),
        "Floor rule passed": floor_rule.get("passed"),
        "Floor rule reason": _txt(floor_rule.get("reason")),
        "Path passed": path.get("passed"),
        "Path detail": _txt(path.get("detail")),
        "Agency passed": agency.get("passed"),
        "Agency detail": _txt(agency.get("detail")),
        "Agency reset": _txt(agency.get("reset")),
        "B2B floor": gates.get("b2b_floor"),
        "Model priority": _txt(entry.get("model_priority")),
        "Recommended action": _txt(entry.get("recommended_action")),
        "Override candidate": entry.get("override_candidate"),
        "Flags": json.dumps(entry.get("flags", []), ensure_ascii=False),
        "Final priority": final_priority(entry),
        "Provenance": provenance(entry),
        "Final priority code": final_priority_code(entry),
        "Final priority rank": final_priority_rank(entry),
        "Human override": _txt(decision.get("human_override")),
        "Override reason": _txt(decision.get("override_reason")),
        "Taxonomy override": _txt(decision.get("taxonomy_override")),
        "Taxonomy override reason": _txt(decision.get("taxonomy_override_reason")),
        "Decided date": _txt(decision.get("decided_date")),
        "Decided at gate": _txt(decision.get("decided_at_gate")),
        "Decision history": json.dumps(decision.get("history", []), ensure_ascii=False),
    }


def _research_index(research: Any) -> dict:
    """Index research rows by normalized company -> {finding columns} (drops the duplicate 'company' key).
    Accepts a pandas DataFrame or a list of dicts; None -> {} (export ledger fields only)."""
    if research is None:
        return {}
    records = research.fillna("").to_dict("records") if isinstance(research, pd.DataFrame) else list(research)
    index: dict[str, dict] = {}
    for record in records:
        company = _txt(record.get("company"))
        if company:
            index[company.lower()] = {k: v for k, v in record.items() if k != "company"}
    return index


def render_master_full_export(entries: list[dict], research: Any = None) -> pd.DataFrame:
    """Every ledger field PLUS all research findings joined in (by company) — the check-everything file.
    A company with no matching research row simply gets blank research columns."""
    ledger_columns = list(flatten_entry(entries[0]).keys()) if entries else []
    index = _research_index(research)
    research_columns: list[str] = []
    rows = []
    for entry in entries:
        flat = flatten_entry(entry)
        for key, value in index.get(_txt(entry.get("company")).lower(), {}).items():
            flat[key] = value
            if key not in research_columns:
                research_columns.append(key)
        rows.append(flat)
    if not rows:
        return pd.DataFrame(columns=ledger_columns)
    return pd.DataFrame(rows).reindex(columns=ledger_columns + research_columns)


def write_summary_table(path: str | Path, entries: list[dict]) -> Path:
    return storage.atomic_write_csv(path, render_summary_table(entries))


def write_master_full_export(path: str | Path, entries: list[dict], research: Any = None) -> Path:
    return storage.atomic_write_csv(path, render_master_full_export(entries, research))


# ---------------------------------------------------------------------------
# ORCHESTRATION (Commit F) — one call: scored roster -> ledger.jsonl + the three CSV views.
#
# The Colab GATE-2 cell calls THIS (new production behavior is an importable function, not cell logic).
# Takes the scored roster (research_runner.score_r1_from_cache / run_r1()['roster']) + the research
# DataFrame; builds every entry, writes the durable ledger transactionally, and renders the three views
# FROM THE REOPENED ledger (Rule 5 — views are built off the verified durable data, not the in-memory list).
# ---------------------------------------------------------------------------

@dataclass
class Gate2BuildResult:
    ledger_path: str
    summary_path: str
    cards_path: str
    export_path: str
    entries: int
    tally: dict
    readback_ok: bool
    backup_path: str = ""


def _context_rows(research: Any) -> dict:
    """Index research rows by normalized company for build_entry's context (one_liner / stage_basis)."""
    if research is None:
        return {}
    records = research.fillna("").to_dict("records") if isinstance(research, pd.DataFrame) else list(research)
    return {_txt(rec.get("company")).lower(): rec for rec in records}


def build_gate2_artifacts(roster: list[dict], research: Any = None, *, batch_id: str, date_scored: str,
                          out_dir: str | Path, framework_version: str | None = None) -> Gate2BuildResult:
    """Build the full GATE-2 packet from a scored roster: one ledger entry per company -> transactional
    `ledger.jsonl` write (backup + read-back + rollback) -> the three CSV views rendered from the REOPENED
    ledger. `research` (the research DataFrame) supplies build_entry's context + the master-export evidence
    join; `fit_brief_json` is dropped from the export (machine JSON, not human-checkable in a spreadsheet —
    its data is already decomposed into the ledger + the finding columns). Returns the paths + tally."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    context = _context_rows(research)

    entries = [
        build_entry(rec, context.get(_txt(rec.get("company")).lower(), {}),
                    batch_id=batch_id, date_scored=date_scored, framework_version=framework_version)
        for rec in roster
    ]

    ledger_path = out / "ledger.jsonl"
    write_result = execute_ledger_write(ledger_path, entries)
    reopened = read_ledger(ledger_path)   # Rule 5 — render views off the verified durable data

    export_research = research
    if isinstance(research, pd.DataFrame) and "fit_brief_json" in research.columns:
        export_research = research.drop(columns=["fit_brief_json"])

    summary_path = write_summary_table(out / "summary_table.csv", reopened)
    cards_path = write_cards_csv(out / "cards.csv", reopened)
    export_path = write_master_full_export(out / "master_full_export.csv", reopened, research=export_research)

    tally: dict = {}
    for entry in reopened:
        tier = final_priority(entry)
        tally[tier] = tally.get(tier, 0) + 1

    return Gate2BuildResult(
        ledger_path=str(ledger_path), summary_path=str(summary_path), cards_path=str(cards_path),
        export_path=str(export_path), entries=len(reopened), tally=tally,
        readback_ok=write_result.readback_ok, backup_path=write_result.backup_path)


def apply_gate2_decisions(out_dir: str | Path, decisions: list[dict], *, decided_date: str,
                          decided_at_gate: str, research: Any = None) -> dict:
    """Apply GATE-2 priority decisions to an already-built ledger and RE-RENDER the three views. Reads
    `ledger.jsonl` from `out_dir`, merges the decisions (priority-only, with history — Rule 6/8), writes it
    back transactionally, then re-renders summary / cards / master_full_export from the reopened durable
    ledger. `research` supplies the master-export evidence join (fit_brief_json dropped). Returns
    `{applied, tally, readback_ok}`."""
    out = Path(out_dir)
    ledger_path = out / "ledger.jsonl"
    merged = apply_decisions(read_ledger(ledger_path), decisions,
                             decided_date=decided_date, decided_at_gate=decided_at_gate)
    write_result = execute_ledger_write(ledger_path, merged)
    reopened = read_ledger(ledger_path)

    export_research = research
    if isinstance(research, pd.DataFrame) and "fit_brief_json" in research.columns:
        export_research = research.drop(columns=["fit_brief_json"])
    write_summary_table(out / "summary_table.csv", reopened)
    write_cards_csv(out / "cards.csv", reopened)
    write_master_full_export(out / "master_full_export.csv", reopened, research=export_research)

    tally: dict = {}
    for entry in reopened:
        tally[final_priority(entry)] = tally.get(final_priority(entry), 0) + 1
    return {"applied": len(list(decisions)), "tally": tally, "readback_ok": write_result.readback_ok}


def render_views(out_dir: str | Path, research: Any = None) -> dict:
    """Re-render the three CSV views from the EXISTING `ledger.jsonl` — NO rebuild, NO decision change — so a
    render-only fix can be picked up while the ledger (and any applied decisions) stays exactly as-is."""
    out = Path(out_dir)
    entries = read_ledger(out / "ledger.jsonl")
    export_research = research
    if isinstance(research, pd.DataFrame) and "fit_brief_json" in research.columns:
        export_research = research.drop(columns=["fit_brief_json"])
    return {
        "summary": str(write_summary_table(out / "summary_table.csv", entries)),
        "cards": str(write_cards_csv(out / "cards.csv", entries)),
        "export": str(write_master_full_export(out / "master_full_export.csv", entries, research=export_research)),
        "entries": len(entries),
    }
