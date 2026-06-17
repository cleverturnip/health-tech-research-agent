from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import math
import numbers
import re
import shutil
from typing import Callable

import pandas as pd

from .storage import atomic_write_csv, load_csv


class MasterUpdateError(RuntimeError):
    def __init__(self, message: str, *, details: dict | None = None):
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True)
class MasterUpdateResult:
    proposed_df: pd.DataFrame
    change_log_df: pd.DataFrame
    readback_df: pd.DataFrame
    write_performed: bool
    inserted_count: int
    updated_count: int
    unchanged_count: int
    backup_path: str = ""
    readback_path: str = ""
    change_log_path: str = ""
    rollback_performed: bool = False


_REVIEW_FIELDS = [
    "reviewed_priority_level",
    "review_status",
    "review_notes",
    "priority_review_note",
]
_DERIVED_PRIORITY_FIELDS = [
    "final_priority_level",
    "priority_source",
    "final_priority_code",
    "final_priority_rank",
]
_SUMMARY_EXCLUSIONS = {
    "company",
    "_company_key",
    "reviewed_priority_level",
    "review_status",
    "review_notes",
    "priority_review_note",
    *_DERIVED_PRIORITY_FIELDS,
}

_TAXONOMY_FIELDS = {
    "primary_market_segment_code",
    "primary_market_segment",
    "market_segment",
    "subsegment_tags",
    "product_model_tags",
    "distribution_model_tags",
    "data_input_tags",
    "taxonomy_confidence",
    "taxonomy_rationale",
    "taxonomy_needs_review",
    "taxonomy_review_reason",
    "taxonomy_assignment_method",
    "taxonomy_assignment_basis",
}


def _is_human_taxonomy_override(row: pd.Series) -> bool:
    method = safe_text(row.get("taxonomy_assignment_method", ""))
    normalized = re.sub(r"[^a-z0-9]+", "_", method.casefold()).strip("_")
    return normalized in {
        "human_override",
        "human_reviewed",
        "human_review",
        "manual_override",
    }


def normalize_company(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().casefold())


def safe_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _canonical_cell(value: object) -> str:
    """Return a stable CSV round-trip representation for one cell.

    Pandas may reload an integer-valued column as float when the column also
    contains blanks (for example ``2`` becomes ``2.0``). That is a storage
    representation change, not a semantic data change. Strings are never
    numerically coerced, so values such as ``"002"`` remain distinct from
    the number ``2``.
    """
    if value is None or pd.isna(value):
        return ""

    if isinstance(value, numbers.Integral) and not isinstance(value, bool):
        return str(int(value))

    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        numeric = float(value)
        if math.isfinite(numeric) and numeric.is_integer():
            return str(int(numeric))

    return str(value).strip()


def _normalized_frame(df: pd.DataFrame) -> pd.DataFrame:
    return df.map(_canonical_cell)


def _validate_unique_company_keys(df: pd.DataFrame, *, label: str) -> None:
    if "company" not in df.columns:
        raise MasterUpdateError(f"{label} is missing required column: company")
    keys = df["company"].map(normalize_company)
    blank = df.loc[keys.eq(""), "company"].tolist()
    if blank:
        raise MasterUpdateError(f"{label} contains blank company values.")
    duplicates = sorted(df.loc[keys.duplicated(keep=False), "company"].astype(str).unique())
    if duplicates:
        raise MasterUpdateError(
            f"{label} contains duplicate companies: {duplicates}",
            details={"duplicate_companies": duplicates},
        )


def _default_priority_applier(df: pd.DataFrame) -> pd.DataFrame:
    from .priority import apply_priority_fields
    return apply_priority_fields(df)


def build_proposed_master(
    *,
    master_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    approved_df: pd.DataFrame,
    batch_id: str,
    priority_applier: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    updated_at: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    _validate_unique_company_keys(master_df, label="Master")
    _validate_unique_company_keys(summary_df, label="Summary artifact")
    _validate_unique_company_keys(approved_df, label="Approved decisions artifact")

    required_approved = {"company", *_REVIEW_FIELDS}
    missing = sorted(required_approved - set(approved_df.columns))
    if missing:
        raise MasterUpdateError(
            f"Approved decisions artifact is missing columns: {missing}"
        )

    # Object dtype prevents pandas from rejecting text updates in columns
    # that were inferred as all-null float columns when the CSV was loaded.
    master = master_df.copy().astype(object)
    summary = summary_df.copy()
    approved = approved_df.copy()
    for frame in (master, summary, approved):
        frame["_company_key"] = frame["company"].map(normalize_company)

    if "batch_id" in approved.columns:
        unexpected_batches = sorted({
            safe_text(value)
            for value in approved["batch_id"].tolist()
            if safe_text(value) != batch_id
        })
        if unexpected_batches:
            raise MasterUpdateError(
                "Approved decisions artifact contains a different batch ID.",
                details={"unexpected_batch_ids": unexpected_batches},
            )

    approved_keys = set(approved["_company_key"])
    missing_summary = sorted(approved_keys - set(summary["_company_key"]))
    if missing_summary:
        raise MasterUpdateError(
            "Approved companies are missing from summary artifact.",
            details={"missing_summary_keys": missing_summary},
        )

    timestamp = updated_at or datetime.now(timezone.utc).isoformat()
    summary_fields = [
        col for col in summary.columns
        if col in master.columns and col not in _SUMMARY_EXCLUSIONS
    ]

    changes: list[dict[str, object]] = []
    inserted = updated = unchanged = 0
    applier = priority_applier or _default_priority_applier

    for _, approved_row in approved.iterrows():
        key = approved_row["_company_key"]
        company_display = safe_text(approved_row["company"])
        summary_row = summary.loc[summary["_company_key"].eq(key)].iloc[0]
        existing_matches = master.index[master["_company_key"].eq(key)].tolist()
        is_insert = not existing_matches

        if is_insert:
            row_index = len(master)
            blank = {col: "" for col in master.columns}
            blank["company"] = company_display
            blank["_company_key"] = key
            master = pd.concat([master, pd.DataFrame([blank])], ignore_index=True)
        else:
            row_index = existing_matches[0]

        original = master.loc[row_index].copy()

        preserve_human_taxonomy = (
            not is_insert and _is_human_taxonomy_override(original)
        )

        for col in summary_fields:
            # Source precedence:
            # 1. Existing human taxonomy overrides remain authoritative.
            # 2. Otherwise, the approved summary may fill or refresh taxonomy.
            # 3. Non-taxonomy research fields continue to come from the summary.
            if preserve_human_taxonomy and col in _TAXONOMY_FIELDS:
                continue

            value = summary_row.get(col, "")
            if safe_text(value):
                master.at[row_index, col] = value

        for col in _REVIEW_FIELDS:
            master.at[row_index, col] = approved_row.get(col, "")

        one_row = master.loc[[row_index]].drop(columns=["_company_key"], errors="ignore")
        prioritized = applier(one_row.copy())
        for col in _DERIVED_PRIORITY_FIELDS:
            if col in master.columns and col in prioritized.columns:
                master.at[row_index, col] = prioritized.iloc[0][col]

        controlled_fields = [
            *summary_fields,
            *_REVIEW_FIELDS,
            *_DERIVED_PRIORITY_FIELDS,
        ]
        controlled_changed = any(
            safe_text(original.get(col, "")) != safe_text(master.at[row_index, col])
            for col in controlled_fields
            if col in master.columns
        ) or is_insert

        if controlled_changed:
            if "final_priority_patch_batch" in master.columns:
                master.at[row_index, "final_priority_patch_batch"] = batch_id
            if "final_priority_patch_updated_at" in master.columns:
                master.at[row_index, "final_priority_patch_updated_at"] = timestamp

        current = master.loc[row_index]
        row_changes = []
        for col in master.columns:
            if col == "_company_key":
                continue
            before = safe_text(original.get(col, ""))
            after = safe_text(current.get(col, ""))
            if before != after:
                row_changes.append((col, before, after))
                changes.append({
                    "batch_id": batch_id,
                    "company": company_display,
                    "company_key": key,
                    "action": "INSERT" if is_insert else "UPDATE",
                    "field": col,
                    "before": before,
                    "after": after,
                })

        if is_insert:
            inserted += 1
        elif row_changes:
            updated += 1
        else:
            unchanged += 1

    approved_rows = master[master["_company_key"].isin(approved_keys)]
    blank_taxonomy = approved_rows[
        approved_rows.get("primary_market_segment_code", pd.Series("", index=approved_rows.index))
        .fillna("").astype(str).str.strip().eq("")
    ]
    if not blank_taxonomy.empty:
        companies = blank_taxonomy["company"].astype(str).tolist()
        raise MasterUpdateError(
            "Approved master rows have blank primary_market_segment_code.",
            details={"blank_taxonomy_companies": companies},
        )

    proposed = master.drop(columns=["_company_key"], errors="ignore")
    change_log = pd.DataFrame(changes, columns=[
        "batch_id", "company", "company_key", "action", "field", "before", "after"
    ])
    return proposed, change_log, {
        "inserted_count": inserted,
        "updated_count": updated,
        "unchanged_count": unchanged,
    }


def validate_master_readback(
    *,
    proposed_df: pd.DataFrame,
    readback_df: pd.DataFrame,
    approved_companies: list[str],
) -> None:
    _validate_unique_company_keys(readback_df, label="Master read-back")
    if list(proposed_df.columns) != list(readback_df.columns):
        raise MasterUpdateError("Master read-back columns do not match proposal.")
    if proposed_df.shape != readback_df.shape:
        raise MasterUpdateError(
            f"Master read-back shape mismatch: proposed={proposed_df.shape}, "
            f"readback={readback_df.shape}"
        )
    if not _normalized_frame(proposed_df).equals(_normalized_frame(readback_df)):
        raise MasterUpdateError("Master read-back content does not match proposal.")

    keys = set(readback_df["company"].map(normalize_company))
    missing = sorted({normalize_company(c) for c in approved_companies} - keys)
    if missing:
        raise MasterUpdateError(
            "Approved companies are missing from master read-back.",
            details={"missing_approved_keys": missing},
        )


def execute_master_update_transaction(
    *,
    master_path: str | Path,
    summary_path: str | Path,
    approved_path: str | Path,
    batch_id: str,
    artifacts_dir: str | Path,
    priority_applier: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    writer: Callable[[str | Path, pd.DataFrame], Path] = atomic_write_csv,
    loader: Callable[[str | Path], pd.DataFrame] = load_csv,
) -> MasterUpdateResult:
    master_path = Path(master_path)
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    master_df = loader(master_path)
    summary_df = loader(summary_path)
    approved_df = loader(approved_path)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    proposed, change_log, counts = build_proposed_master(
        master_df=master_df,
        summary_df=summary_df,
        approved_df=approved_df,
        batch_id=batch_id,
        priority_applier=priority_applier,
    )

    change_log_path = artifacts_dir / f"{batch_id}_master_change_log_{timestamp}.csv"
    readback_path = artifacts_dir / f"{batch_id}_master_readback_{timestamp}.csv"
    writer(change_log_path, change_log)

    if change_log.empty:
        writer(readback_path, master_df)
        validate_master_readback(
            proposed_df=proposed,
            readback_df=master_df,
            approved_companies=approved_df["company"].tolist(),
        )
        return MasterUpdateResult(
            proposed_df=proposed,
            change_log_df=change_log,
            readback_df=master_df,
            write_performed=False,
            inserted_count=counts["inserted_count"],
            updated_count=counts["updated_count"],
            unchanged_count=counts["unchanged_count"],
            readback_path=str(readback_path),
            change_log_path=str(change_log_path),
        )

    backup_path = artifacts_dir / f"{master_path.stem}_backup_before_{batch_id}_{timestamp}.csv"
    shutil.copy2(master_path, backup_path)

    try:
        writer(master_path, proposed)
        readback = loader(master_path)
        validate_master_readback(
            proposed_df=proposed,
            readback_df=readback,
            approved_companies=approved_df["company"].tolist(),
        )
        writer(readback_path, readback)
    except Exception as exc:
        rollback_performed = False
        try:
            shutil.copy2(backup_path, master_path)
            restored = loader(master_path)
            if not _normalized_frame(restored).equals(_normalized_frame(master_df)):
                raise RuntimeError("Rollback verification failed.")
            rollback_performed = True
        except Exception as rollback_exc:
            raise MasterUpdateError(
                f"Master update failed and rollback also failed: {exc}; {rollback_exc}",
                details={
                    "backup_path": str(backup_path),
                    "rollback_performed": False,
                },
            ) from exc
        raise MasterUpdateError(
            f"Master update failed; original master was restored: {exc}",
            details={
                "backup_path": str(backup_path),
                "rollback_performed": rollback_performed,
            },
        ) from exc

    return MasterUpdateResult(
        proposed_df=proposed,
        change_log_df=change_log,
        readback_df=readback,
        write_performed=True,
        inserted_count=counts["inserted_count"],
        updated_count=counts["updated_count"],
        unchanged_count=counts["unchanged_count"],
        backup_path=str(backup_path),
        readback_path=str(readback_path),
        change_log_path=str(change_log_path),
    )
