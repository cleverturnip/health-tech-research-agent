"""Targeted, idempotent re-land of dropped LLM-JSON clusters into the master.

Context: the run-once regeneration's inline STEP 10 build dropped two LLM-JSON
clusters from the summary -> master landing (role/timing + taxonomy-LLM), so the
canonical 55-company master carries them blank even though the saved research
checkpoint's ``fit_brief_json`` has them populated 55/55. This module re-lands that
*already-existing* data from the checkpoint -- no re-research, no STEP 10/12 re-run,
no master hand-edit.

Design (all verified against the authoritative notebook + the saved checkpoint):

- **Blank-only fill** of a fixed target-column set; already-populated columns are
  never written (idempotent -- a re-run is a no-op -- and human-set values survive).
- **Fail-loud, all-or-nothing.** A missing JSON block/key, an incomplete
  checkpoint<->master match, or a per-field read-back below the checkpoint's own
  populated count all raise; on a real write the master is rolled back from a backup.
- **Rule 7 boundary -- only the raw LLM evidence STEP 10 was meant to carry.** It
  deliberately does NOT write:
    * ``primary_market_segment_code`` -- the *validated* code is owned by the
      deterministic classifier (STEP 14 ``classify_dataframe``); the raw LLM code is
      preserved in ``primary_market_segment`` (STEP 14's LLM-first input).
    * the role/timing siblings (``timing_penalty_applied``,
      ``operator_timing_score_raw`` / ``_cap`` / ``_calibration_flag``) --
      deterministic, recomputed at the dashboard milestone.
    * the deterministic-taxonomy subset (``market_segment``, ``taxonomy_confidence``,
      ``taxonomy_rationale``, ``taxonomy_needs_review``, ``taxonomy_review_reason``)
      -- produced by STEP 14.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil

import pandas as pd

from .master_update import normalize_company
from .review import parse_first_json_object
from .storage import atomic_write_csv


class RelandError(RuntimeError):
    """Raised on any unsafe condition; the master is never left partially written."""


# ---------------------------------------------------------------------------
# Field contract (verified against the checkpoint fit_brief_json, 55/55)
# ---------------------------------------------------------------------------
_RT_KEYS = ("stage_timing_fit", "likely_agency_level", "why_now_or_why_not")
_TAX_REQUIRED_KEYS = (
    "primary_market_segment",
    "subsegment_tags",
    "product_model_tags",
    "distribution_model_tags",
    "data_input_tags",
    "classification_rationale",
)
_TAG_COLS = (
    "subsegment_tags",
    "product_model_tags",
    "distribution_model_tags",
    "data_input_tags",
)

# The 10 columns this re-land fills. ``primary_market_segment_code`` is DELIBERATELY
# absent -- deferred to STEP 14's classifier (Rule 7). Keep this tuple as the single
# source of truth for the fill, the targets, and the read-back.
TARGET_COLS = (
    *_RT_KEYS,
    "primary_market_segment",
    *_TAG_COLS,
    "taxonomy_assignment_method",
    "taxonomy_assignment_basis",
)


@dataclass
class RelandResult:
    matched_count: int
    checkpoint_rows: int
    master_rows: int
    targets: dict          # master_col -> expected populated count (from checkpoint source)
    fill_counts: dict      # master_col -> blank cells filled this run
    readback_counts: dict  # master_col -> populated count after write (reopened from disk)
    write_performed: bool
    dry_run: bool
    output_path: str = ""
    backup_path: str = ""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _is_blank(value) -> bool:
    return pd.isna(value) or str(value).strip() == ""


def _join_tags(value) -> str:
    """Port of STEP 10's ``step10_taxonomy_join``: list -> '; '-joined (empties
    dropped); str -> stripped; None -> ''."""
    if isinstance(value, list):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    return "" if value is None else str(value).strip()


def _source_nonblank(value) -> bool:
    """Emptiness check for target counting (handles list- and string-valued keys)."""
    if isinstance(value, list):
        return any(str(item).strip() for item in value)
    return not _is_blank(value)


def _parse_clusters(fit_brief_json, company: str) -> tuple[dict, dict]:
    """Parse + validate the two LLM blocks for one row. Fail loud on a missing block
    or a missing required key -- never fabricate around an absent key."""
    try:
        parsed = parse_first_json_object(fit_brief_json)
    except Exception as exc:  # no / invalid JSON
        raise RelandError(f"{company}: could not parse fit_brief_json ({exc}).") from exc

    role_timing = parsed.get("role_timing_assessment")
    taxonomy = parsed.get("taxonomy_classification")
    if not isinstance(role_timing, dict):
        raise RelandError(f"{company}: role_timing_assessment missing or not an object.")
    if not isinstance(taxonomy, dict):
        raise RelandError(f"{company}: taxonomy_classification missing or not an object.")

    for key in _RT_KEYS:
        if key not in role_timing:
            raise RelandError(f"{company}: role_timing_assessment missing key {key!r}.")
    for key in _TAX_REQUIRED_KEYS:
        if key not in taxonomy:
            raise RelandError(f"{company}: taxonomy_classification missing key {key!r}.")
    return role_timing, taxonomy


def _landed_values(role_timing: dict, taxonomy: dict) -> dict:
    """Compute each target column's value from the parsed clusters (transforms applied)."""
    segment = str(taxonomy.get("primary_market_segment", "")).strip()
    return {
        "stage_timing_fit": str(role_timing.get("stage_timing_fit", "")).strip(),
        "likely_agency_level": str(role_timing.get("likely_agency_level", "")).strip(),
        "why_now_or_why_not": str(role_timing.get("why_now_or_why_not", "")).strip(),
        # Raw LLM code -- STEP 14's LLM-first input; the *validated* _code is STEP 14's.
        "primary_market_segment": segment,
        "subsegment_tags": _join_tags(taxonomy.get("subsegment_tags")),
        "product_model_tags": _join_tags(taxonomy.get("product_model_tags")),
        "distribution_model_tags": _join_tags(taxonomy.get("distribution_model_tags")),
        "data_input_tags": _join_tags(taxonomy.get("data_input_tags")),
        "taxonomy_assignment_method": "llm_fit_brief" if segment else "",
        "taxonomy_assignment_basis": (
            str(taxonomy.get("classification_rationale", "")).strip() if segment else ""
        ),
    }


def _expected_source_counts(checkpoint_df: pd.DataFrame) -> dict:
    """Per target column, count checkpoint rows whose SOURCE is non-blank.

    Computed independently of ``_landed_values`` (directly off the verified source
    keys), so a wrong-key / parse-to-blank regression in the fill path lands below
    this target and trips the read-back assert -- the failure the original
    "column exists" check could not catch.
    """
    counts = {col: 0 for col in TARGET_COLS}
    for _, row in checkpoint_df.iterrows():
        company = str(row.get("company", ""))
        role_timing, taxonomy = _parse_clusters(row["fit_brief_json"], company)
        for key in _RT_KEYS:
            if _source_nonblank(role_timing.get(key)):
                counts[key] += 1
        segment_present = _source_nonblank(taxonomy.get("primary_market_segment"))
        if segment_present:
            counts["primary_market_segment"] += 1
            counts["taxonomy_assignment_method"] += 1
            if _source_nonblank(taxonomy.get("classification_rationale")):
                counts["taxonomy_assignment_basis"] += 1
        for col in _TAG_COLS:
            if _source_nonblank(taxonomy.get(col)):
                counts[col] += 1
    return counts


# ---------------------------------------------------------------------------
# Pure core (file-free; the unit tests exercise this directly)
# ---------------------------------------------------------------------------
def reland_llm_clusters_df(
    master_df: pd.DataFrame, checkpoint_df: pd.DataFrame
) -> tuple[pd.DataFrame, RelandResult]:
    """Blank-only fill of ``TARGET_COLS`` in a copy of ``master_df`` from
    ``checkpoint_df``.

    Raises ``RelandError`` on duplicate master keys, any unmatched checkpoint row,
    an incomplete 1:1 match, or a missing JSON block/key -- writing nothing in those
    cases. Returns ``(updated_df, result)`` with ``targets`` + ``fill_counts`` set;
    the file wrapper fills in ``readback_counts``.
    """
    master = master_df.copy()
    for col in TARGET_COLS:
        if col not in master.columns:
            master[col] = ""

    # 1:1 master key map; reject duplicate company keys (case/space-insensitive).
    master_keys = master["company"].map(normalize_company)
    if master_keys.duplicated().any():
        dups = sorted(set(master_keys[master_keys.duplicated()]))
        raise RelandError(f"master has duplicate company keys: {dups}")
    key_to_idx = dict(zip(master_keys, master.index))

    # Targets first (independent of the fill path) -- also validates every row's JSON.
    targets = _expected_source_counts(checkpoint_df)

    # Completeness guard: every checkpoint row must map to exactly one master row.
    landed_by_idx: dict = {}
    unmatched: list[str] = []
    for _, row in checkpoint_df.iterrows():
        company = str(row["company"])
        idx = key_to_idx.get(normalize_company(company))
        if idx is None:
            unmatched.append(company)
            continue
        role_timing, taxonomy = _parse_clusters(row["fit_brief_json"], company)
        landed_by_idx[idx] = _landed_values(role_timing, taxonomy)

    if unmatched:
        raise RelandError(
            f"{len(unmatched)} checkpoint row(s) have no master counterpart "
            f"(writing nothing): {unmatched}"
        )
    matched = len(landed_by_idx)
    if not matched == len(checkpoint_df) == len(master):
        raise RelandError(
            f"incomplete match: matched={matched}, checkpoint={len(checkpoint_df)}, "
            f"master={len(master)} (expected all equal)."
        )

    # Blank-only fill.
    fill_counts = {col: 0 for col in TARGET_COLS}
    for idx, values in landed_by_idx.items():
        for col in TARGET_COLS:
            new_value = values[col]
            if str(new_value).strip() and _is_blank(master.at[idx, col]):
                master.at[idx, col] = new_value
                fill_counts[col] += 1

    result = RelandResult(
        matched_count=matched,
        checkpoint_rows=len(checkpoint_df),
        master_rows=len(master),
        targets=targets,
        fill_counts=fill_counts,
        readback_counts={},
        write_performed=False,
        dry_run=False,
    )
    return master, result


# ---------------------------------------------------------------------------
# File wrapper (backup + atomic write + read-back + rollback)
# ---------------------------------------------------------------------------
def _read_csv_str(path: Path) -> pd.DataFrame:
    """Read preserving strings and blanks (storage.load_csv does neither)."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _populated_count(df: pd.DataFrame, col: str) -> int:
    if col not in df.columns:
        return 0
    return int(df[col].map(lambda value: not _is_blank(value)).sum())


def reland_llm_clusters(master_path, checkpoint_path, *, dry_run: bool = False) -> RelandResult:
    """Load the master + checkpoint, re-land (blank-only), atomic-write, then reopen
    and validate.

    Reads the already-written master and the saved checkpoint only -- it does NOT run
    STEP 10 (``summary_rows``) or STEP 12 (``optional_model_cols``) and, being
    blank-only, never touches the master's other columns.

    ``dry_run=True`` writes to a throwaway ``DRYRUN_*`` file beside the master and
    leaves the real master untouched. A real write backs the master up first and
    rolls it back on any read-back / safety failure.
    """
    master_path = Path(master_path)
    checkpoint_path = Path(checkpoint_path)
    master_df = _read_csv_str(master_path)
    checkpoint_df = _read_csv_str(checkpoint_path)

    updated, result = reland_llm_clusters_df(master_df, checkpoint_df)
    result.dry_run = dry_run

    if dry_run:
        out_path = master_path.with_name(f"DRYRUN_reland_{master_path.name}")
    else:
        out_path = master_path
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = master_path.with_name(
            f"{master_path.stem}_backup_before_reland_{timestamp}.csv"
        )
        shutil.copy2(master_path, backup_path)
        result.backup_path = str(backup_path)

    atomic_write_csv(out_path, updated)
    result.output_path = str(out_path)
    result.write_performed = True

    # Read-back from disk (Rule 5: reopen and confirm).
    reopened = _read_csv_str(out_path)
    result.readback_counts = {col: _populated_count(reopened, col) for col in TARGET_COLS}

    def _rollback() -> None:
        if not dry_run:
            shutil.copy2(result.backup_path, master_path)

    where = "no real write" if dry_run else "master rolled back"

    # Guard 1: per-field read-back must meet the checkpoint's own populated count.
    shortfalls = {
        col: (result.readback_counts[col], result.targets[col])
        for col in TARGET_COLS
        if result.readback_counts[col] < result.targets[col]
    }
    if shortfalls:
        _rollback()
        raise RelandError(
            f"read-back below checkpoint target (got, want) {shortfalls} -- {where}."
        )

    # Guard 2: non-target columns must be untouched (populated-count unchanged).
    for col in master_df.columns:
        if col in TARGET_COLS:
            continue
        before = _populated_count(master_df, col)
        after = _populated_count(reopened, col)
        if before != after:
            _rollback()
            raise RelandError(
                f"non-target column {col!r} changed ({before} -> {after}) -- {where}."
            )

    return result


def format_report(result: RelandResult) -> str:
    """Human-readable summary for the notebook caller -- makes read-not-rerun visible."""
    lines = [
        "=== Field-landing re-land (role/timing + taxonomy-LLM) ===",
        "MODE: reads the already-written master + the saved checkpoint and fills "
        "blank columns only.",
        "      Does NOT run STEP 10 (summary_rows) or STEP 12 (optional_model_cols); "
        "the master write path is not invoked.",
        f"dry_run={result.dry_run}  write_performed={result.write_performed}",
        f"output: {result.output_path}",
    ]
    if result.backup_path:
        lines.append(f"backup: {result.backup_path}")
    lines.append(
        f"match: checkpoint={result.checkpoint_rows} master={result.master_rows} "
        f"matched={result.matched_count}  (must be equal)"
    )
    lines.append(f"{'column':<30}{'target':>8}{'filled':>8}{'readback':>10}")
    for col in TARGET_COLS:
        lines.append(
            f"{col:<30}{result.targets[col]:>8}{result.fill_counts[col]:>8}"
            f"{result.readback_counts.get(col, 0):>10}"
        )
    lines.append(
        "DEFERRED (not written here): primary_market_segment_code + the 4 role/timing "
        "siblings + the 5 deterministic-taxonomy fields (STEP 14 / dashboard milestone)."
    )
    return "\n".join(lines)
