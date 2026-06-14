# =============================================================================
# STEP 12C - One-time master priority label migration
# =============================================================================
# Purpose:
# - Convert legacy priority labels in the master CSV to the native P0-P4 model
# - Preserve original raw priority labels in backup columns for traceability
# - Save a timestamped backup before modifying anything
# - Save a change log showing every migrated priority label
#
# Run once, after codebase is updated to native P0/P1/P2/P3/P4.
#
# Recommended run order:
# 12C -> 12B -> 13 -> 14 -> 15 -> 16 -> 17 -> 18 -> 19 -> 19A

import pandas as pd
import re
import shutil
from pathlib import Path
from datetime import datetime
from google.colab import drive, files

# -----------------------------
# Config / paths
# -----------------------------

drive.mount("/content/drive")

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_folder.mkdir(parents=True, exist_ok=True)

MASTER_FILENAME = "health_tech_market_research_summary_MASTER.csv"

drive_master_path = drive_folder / MASTER_FILENAME
local_master_path = Path(MASTER_FILENAME)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

backup_drive_path = drive_folder / f"health_tech_market_research_summary_MASTER_backup_before_12C_priority_label_migration_{timestamp}.csv"
snapshot_drive_path = drive_folder / f"health_tech_market_research_summary_MASTER_after_12C_priority_label_migration_{timestamp}.csv"
change_log_drive_path = drive_folder / f"health_tech_market_research_summary_MASTER_12C_priority_label_migration_change_log_{timestamp}.csv"

local_change_log_path = Path(f"health_tech_market_research_summary_MASTER_12C_priority_label_migration_change_log_{timestamp}.csv")

# -----------------------------
# Safety checks
# -----------------------------

if not drive_master_path.exists():
    raise FileNotFoundError(f"STOP: Master not found in Google Drive: {drive_master_path}")

shutil.copy(drive_master_path, local_master_path)

master_df = pd.read_csv(local_master_path)

if "company" not in master_df.columns:
    raise ValueError("STOP: Master is missing company column.")

if master_df["company"].duplicated().any():
    dupes = master_df[master_df["company"].duplicated(keep=False)]["company"].tolist()
    raise ValueError(f"STOP: Duplicate companies found in master: {dupes}")

for col in ["priority_level", "reviewed_priority_level"]:
    if col not in master_df.columns:
        master_df[col] = ""

# -----------------------------
# Helpers
# -----------------------------

def is_blank_value(value):
    return pd.isna(value) or str(value).strip() == ""

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def normalize_priority_label_native(value):
    """
    Converts legacy and native labels into the native P0-P4 model.

    Native model:
    - P0 = Highest-priority target / active pursuit
    - P1 = Near-priority target / former P1-border
    - P2 = Worth deeper diligence
    - P3 = Watch list
    - P4 = Low priority / likely reject

    Legacy mapping:
    - P1: High-priority target              -> P0
    - Strong P2 / P1-border                -> P1
    - P2: Worth deeper diligence           -> P2
    - Review P2                            -> P2
    - P3: Watch list                       -> P3
    - P4: Low priority / likely reject     -> P4
    """
    text = safe_text(value)

    if text == "":
        return ""

    lower = text.lower()

    # Native P0 or old top-priority P1.
    if (
        lower.startswith("p0")
        or "highest-priority" in lower
        or "highest priority" in lower
        or "active pursuit" in lower
        or "top-priority" in lower
        or "top priority" in lower
        or lower.startswith("p1: high-priority")
        or lower.startswith("p1: high priority")
        or lower.startswith("p1 - high-priority")
        or lower.startswith("p1 - high priority")
    ):
        return "P0: Highest-priority target"

    # Native P1 / old P1-border.
    if (
        lower.startswith("p1: near-priority")
        or lower.startswith("p1: near priority")
        or lower.startswith("p1 - near-priority")
        or lower.startswith("p1 - near priority")
        or "p1-border" in lower
        or "p1 border" in lower
        or "near-priority" in lower
        or "near priority" in lower
        or "strong p2" in lower
        or "p0-border" in lower
        or "p0 border" in lower
    ):
        return "P1: Near-priority target"

    if (
        lower.startswith("p2")
        or lower.startswith("review p2")
        or "review p2" in lower
        or "worth deeper diligence" in lower
        or "diligence target" in lower
        or "deeper diligence" in lower
    ):
        return "P2: Worth deeper diligence"

    if (
        lower.startswith("p3")
        or "watch list" in lower
        or "watchlist" in lower
    ):
        return "P3: Watch list"

    if (
        lower.startswith("p4")
        or "low priority" in lower
        or "likely reject" in lower
        or "weak fit" in lower
        or "reject" in lower
    ):
        return "P4: Low priority / likely reject"

    # Ambiguous bare P1: in the native model, P1 means near-priority.
    if lower == "p1":
        return "P1: Near-priority target"

    # Preserve unknown values so nothing is silently destroyed.
    return text

def priority_code(value):
    text = safe_text(value).upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""

def priority_rank(value):
    code = priority_code(value)
    return {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }.get(code, 99)

def log_change(company, field, old_value, new_value, reason):
    if safe_text(old_value) != safe_text(new_value):
        change_log.append({
            "company": company,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "migrated_at": timestamp
        })

# -----------------------------
# Preserve legacy source labels
# -----------------------------

# Only create these once. If you rerun this cell, do not overwrite the original legacy values.
if "legacy_priority_level_before_p0_migration" not in master_df.columns:
    master_df["legacy_priority_level_before_p0_migration"] = master_df["priority_level"]

if "legacy_reviewed_priority_level_before_p0_migration" not in master_df.columns:
    master_df["legacy_reviewed_priority_level_before_p0_migration"] = master_df["reviewed_priority_level"]

if "priority_label_migrated_at" not in master_df.columns:
    master_df["priority_label_migrated_at"] = ""

# -----------------------------
# Backup before modifying
# -----------------------------

master_df.to_csv(local_master_path, index=False)
shutil.copy(local_master_path, backup_drive_path)

print("Backup saved before migration:")
print(backup_drive_path)

# -----------------------------
# Migrate labels
# -----------------------------

change_log = []

for idx, row in master_df.iterrows():
    company = row["company"]

    old_auto = row.get("priority_level", "")
    new_auto = normalize_priority_label_native(old_auto)

    old_reviewed = row.get("reviewed_priority_level", "")
    new_reviewed = normalize_priority_label_native(old_reviewed)

    log_change(
        company,
        "priority_level",
        old_auto,
        new_auto,
        "Normalize automated priority to native P0-P4 model"
    )

    log_change(
        company,
        "reviewed_priority_level",
        old_reviewed,
        new_reviewed,
        "Normalize reviewed priority to native P0-P4 model"
    )

    master_df.loc[idx, "priority_level"] = new_auto
    master_df.loc[idx, "reviewed_priority_level"] = new_reviewed

    if safe_text(old_auto) != safe_text(new_auto) or safe_text(old_reviewed) != safe_text(new_reviewed):
        master_df.loc[idx, "priority_label_migrated_at"] = timestamp

# Recompute final priority fields for preview / convenience.
# Step 12B remains the official helper, but this confirms the migration outcome immediately.
def final_priority_level_for_row(row):
    reviewed = safe_text(row.get("reviewed_priority_level", ""))
    auto = safe_text(row.get("priority_level", ""))

    if reviewed != "":
        return normalize_priority_label_native(reviewed)

    return normalize_priority_label_native(auto)

master_df["final_priority_level"] = master_df.apply(final_priority_level_for_row, axis=1)

def priority_source_for_row(row):
    auto = normalize_priority_label_native(row.get("priority_level", ""))
    reviewed = normalize_priority_label_native(row.get("reviewed_priority_level", ""))
    note = safe_text(row.get("priority_review_note", ""))

    if reviewed == "":
        return "Auto Adjudicated"

    if reviewed != auto:
        return "Human Reviewed"

    if note != "":
        return "Human Reviewed"

    return "Auto Adjudicated"

if "priority_review_note" not in master_df.columns:
    master_df["priority_review_note"] = ""

master_df["priority_source"] = master_df.apply(priority_source_for_row, axis=1)
master_df["final_priority_code"] = master_df["final_priority_level"].apply(priority_code)
master_df["final_priority_rank"] = master_df["final_priority_level"].apply(priority_rank)

# -----------------------------
# Validate no legacy priority labels remain in active priority columns
# -----------------------------

legacy_patterns = [
    "P1: High-priority",
    "P1: High priority",
    "Strong P2",
    "P1-border",
    "P1 border",
    "Review P2"
]

legacy_issues = []

for col in ["priority_level", "reviewed_priority_level", "final_priority_level"]:
    for pattern in legacy_patterns:
        mask = master_df[col].astype(str).str.contains(pattern, case=False, na=False)
        for company in master_df.loc[mask, "company"].tolist():
            legacy_issues.append({
                "company": company,
                "column": col,
                "legacy_pattern": pattern,
                "current_value": master_df.loc[master_df["company"] == company, col].iloc[0]
            })

legacy_issues_df = pd.DataFrame(legacy_issues)

if not legacy_issues_df.empty:
    print("STOP: Legacy labels remain in active priority columns.")
    display(legacy_issues_df)
    raise ValueError("Legacy priority labels remain after migration.")

# -----------------------------
# Save master and change log
# -----------------------------

change_log_df = pd.DataFrame(change_log)

master_df.to_csv(local_master_path, index=False)
shutil.copy(local_master_path, drive_master_path)
shutil.copy(local_master_path, snapshot_drive_path)

change_log_df.to_csv(local_change_log_path, index=False)
shutil.copy(local_change_log_path, change_log_drive_path)

# -----------------------------
# Output summary
# -----------------------------

print("\nPriority label migration complete.")
print("Master shape:", master_df.shape)
print("Company count:", master_df["company"].nunique())

print("\nActive master saved to:")
print(drive_master_path)

print("\nPost-migration snapshot saved to:")
print(snapshot_drive_path)

print("\nChange log saved to:")
print(change_log_drive_path)

print("\nPriority migration changes:")
if change_log_df.empty:
    print("No priority labels required migration.")
else:
    display(change_log_df)

print("\nFinal priority summary after migration:")
priority_summary = (
    master_df
    .groupby(["final_priority_level", "priority_source"], dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
)

priority_summary["final_priority_rank"] = priority_summary["final_priority_level"].apply(priority_rank)

display(
    priority_summary
    .sort_values(["final_priority_rank", "priority_source"])
    .drop(columns=["final_priority_rank"])
)

print("\nRows with human-reviewed priority source:")
human_reviewed = master_df[
    master_df["priority_source"].astype(str).str.lower().eq("human reviewed")
].copy()

human_cols = [
    "company",
    "priority_level",
    "reviewed_priority_level",
    "final_priority_level",
    "priority_review_note",
    "legacy_priority_level_before_p0_migration",
    "legacy_reviewed_priority_level_before_p0_migration"
]

human_cols = [col for col in human_cols if col in human_reviewed.columns]

if human_reviewed.empty:
    print("None")
else:
    human_sort_cols = [col for col in ["final_priority_rank", "company"] if col in human_reviewed.columns]

    display(
        human_reviewed
        .sort_values(human_sort_cols)
        [human_cols]
    )

files.download(str(local_master_path))
files.download(str(local_change_log_path))
