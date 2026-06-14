"""
Health Tech Research Agent - Colab Workflow

This file mirrors the active Google Colab workflow.

Current execution environment:

* Google Colab
* Google Drive for persistent storage
* OpenAI API for fit synthesis
* CSV/XLSX exports for dashboard outputs

Important:

* This file is currently a source-of-truth reference for copy/paste Colab cells.
* It is not yet a fully modular script.
* As the workflow stabilizes, cells should be converted into functions and eventually into a runnable pipeline.
  """

# =============================================================================

# STEP 1 - Environment / imports / setup

# =============================================================================

# TODO: Paste current Step 1 Colab code here.

# =============================================================================

# STEP 2 - Company/source config

# =============================================================================

# TODO: Paste current Step 2 Colab code here.

# =============================================================================

# STEP 3 - Search / research helpers

# =============================================================================

# TODO: Paste current Step 3 Colab code here.

# =============================================================================

# STEP 4 - Raw research functions

# =============================================================================

# Purpose:

# - Funding research

# - Payer / institutional distribution research

# - Outcomes research

# - Commercial scale / revenue-quality research

# TODO: Paste current Step 4 Colab code here.

# =============================================================================

# STEP 5 - Company fit synthesis prompt

# =============================================================================

# Purpose:

# - Convert raw research findings into structured JSON

# - Score thesis fit, PMF/scale, evidence confidence, role fit, timing

# - Output scale signal fields

# - Use priority gate logic

# TODO: Paste current Step 5 Colab code here.

# =============================================================================

# STEP 6 - Batch config / paths / company list

# =============================================================================

# TODO: Paste current Step 6 Colab code here.

# =============================================================================

# STEP 6B - Standard cross-batch checkpoint recovery

# =============================================================================

# TODO: Paste current Step 6B Colab code here.

# =============================================================================

# STEP 7 - Run research + fit briefs

# =============================================================================

# TODO: Paste current Step 7 Colab code here.

# =============================================================================

# STEP 8 - Save current batch checkpoint

# =============================================================================

# TODO: Paste current Step 8 Colab code here.

# =============================================================================

# STEP 8A - Save raw research archive

# =============================================================================

# TODO: Paste current Step 8A Colab code here.

# =============================================================================

# STEP 9 - Print raw batch results

# =============================================================================

# TODO: Paste current Step 9 Colab code here.

# =============================================================================

# STEP 10 - Parse fit brief JSON into score/summary table

# =============================================================================

# TODO: Paste current Step 10 Colab code here.

# =============================================================================

# STEP 10A - Deterministic priority adjudication

# =============================================================================

# Purpose:

# - Enforce hard priority rules after LLM scoring

# - Prevent role fit / thesis interest from incorrectly promoting weak-scale companies

# - Update fit_brief_json, checkpoint, and archive rows in place

# TODO: Paste current Step 10A Colab code here.

# =============================================================================

# STEP 10B - Batch QA checks before export/master update

# =============================================================================

# TODO: Paste current Step 10B Colab code here.

# =============================================================================

# STEP 11 - Export current batch only

# =============================================================================

# TODO: Paste current Step 11 Colab code here.

# =============================================================================

# STEP 11A - Final raw archive QA

# =============================================================================

# TODO: Paste current Step 11A Colab code here.

# =============================================================================

# STEP 12 - Add/update current batch in master

# =============================================================================

# TODO: Paste current Step 12 Colab code here.

# =============================================================================

# Priority field helpers
# Purpose:
# - Keep priority_level as the automated/adjudicated system priority
# - Keep reviewed_priority_level as optional human override
# - Create final_priority_level for dashboard use
# - Create priority_source for transparency

import pandas as pd
import re

def is_blank_value(value):
    return pd.isna(value) or str(value).strip() == ""

def extract_priority_code(value):
    text = str(value).strip().upper()
    match = re.search(r"\bP[1-4]\b", text)
    return match.group(0) if match else ""

def priority_rank(value):
    code = extract_priority_code(value)
    return {
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }.get(code, 99)

def apply_priority_fields(input_df):
    output_df = input_df.copy()

    if "priority_level" not in output_df.columns:
        output_df["priority_level"] = ""

    if "reviewed_priority_level" not in output_df.columns:
        output_df["reviewed_priority_level"] = ""

    if "priority_review_note" not in output_df.columns:
        output_df["priority_review_note"] = ""

    output_df["final_priority_level"] = output_df.apply(
        lambda row: row["reviewed_priority_level"]
        if not is_blank_value(row.get("reviewed_priority_level", ""))
        else row.get("priority_level", ""),
        axis=1
    )

    output_df["priority_source"] = output_df["reviewed_priority_level"].apply(
        lambda value: "Human Reviewed" if not is_blank_value(value) else "Auto Adjudicated"
    )

    output_df["final_priority_code"] = output_df["final_priority_level"].apply(extract_priority_code)
    output_df["final_priority_rank"] = output_df["final_priority_level"].apply(priority_rank)

    return output_df

# =============================================================================

# Purpose:

# - Normalize priority labels into P0-P4 dashboard priority

# - Create final_priority_level, priority_source, final_priority_code, final_priority_rank

# - Preserve priority_level and reviewed_priority_level for traceability

# TODO: Paste current Step 12B Colab code here.

# =============================================================================

# STEP 13 - Load master dashboard using final priority

# =============================================================================

# 13 - Load master dashboard using final priority
# Purpose:
# - Load active master
# - Apply priority helper from Step 12B
# - Create final_priority_level using reviewed_priority_level first, then priority_level
# - Create priority_source for Auto Adjudicated vs Human Reviewed
# - Preserve decision_priority / decision_priority_sort as backward-compatible aliases for older dashboard steps
# - Does not modify or save the master

import pandas as pd
import shutil
from pathlib import Path
from google.colab import drive

drive.mount("/content/drive")

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_master_path = drive_folder / "health_tech_market_research_summary_MASTER.csv"
local_master_path = Path("health_tech_market_research_summary_MASTER.csv")

if not drive_master_path.exists():
    raise FileNotFoundError(f"Master not found: {drive_master_path}")

# Step 13 now depends on Step 12B.
# This prevents multiple cells from maintaining conflicting priority logic.
if "apply_priority_fields" not in globals():
    raise NameError(
        "STOP: apply_priority_fields is not defined. "
        "Run Step 12B - Priority field helper before Step 13."
    )

if "priority_rank" not in globals():
    raise NameError(
        "STOP: priority_rank is not defined. "
        "Run Step 12B - Priority field helper before Step 13."
    )

shutil.copy(drive_master_path, local_master_path)

master_df = pd.read_csv(local_master_path)

# -----------------------------
# Required baseline columns
# -----------------------------

if "company" not in master_df.columns:
    raise ValueError("STOP: Master is missing required column: company")

if "priority_level" not in master_df.columns:
    master_df["priority_level"] = ""

if "reviewed_priority_level" not in master_df.columns:
    master_df["reviewed_priority_level"] = ""

if "priority_review_note" not in master_df.columns:
    master_df["priority_review_note"] = ""

# -----------------------------
# Apply final priority logic from Step 12B
# -----------------------------

master_df = apply_priority_fields(master_df)

# Backward-compatible aliases for steps that still reference old names.
# These should eventually be replaced downstream with final_priority_level / final_priority_rank.
master_df["decision_priority"] = master_df["final_priority_level"]
master_df["decision_priority_sort"] = master_df["final_priority_rank"]

# -----------------------------
# Sort dashboard-ready master
# -----------------------------

sort_cols = []
ascending = []

if "final_priority_rank" in master_df.columns:
    sort_cols.append("final_priority_rank")
    ascending.append(True)

for col in [
    "pmf_scale_score",
    "thesis_fit_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "evidence_confidence_score"
]:
    if col in master_df.columns:
        sort_cols.append(col)
        ascending.append(False)

if sort_cols:
    master_df = master_df.sort_values(
        by=sort_cols,
        ascending=ascending
    ).reset_index(drop=True)

# -----------------------------
# Output summary
# -----------------------------

print("Master loaded for dashboard use.")
print("Master shape:", master_df.shape)
print("Company count:", master_df["company"].nunique())

print("\nFinal priority summary:")
priority_summary = (
    master_df
    .groupby(["final_priority_level", "priority_source"], dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
)

priority_summary["priority_sort"] = priority_summary["final_priority_level"].apply(priority_rank)

priority_summary = priority_summary.sort_values(
    by=["priority_sort", "priority_source"],
    ascending=[True, True]
).drop(columns=["priority_sort"])

display(priority_summary)

print("\nPriority source summary:")
display(
    master_df
    .groupby("priority_source", dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
    .sort_values("priority_source")
)

human_reviewed_df = master_df[
    master_df["priority_source"].astype(str).str.lower().eq("human reviewed")
].copy()

if not human_reviewed_df.empty:
    print("\nHuman-reviewed priority overrides:")
    override_cols = [
        "company",
        "priority_level",
        "reviewed_priority_level",
        "final_priority_level",
        "priority_review_note"
    ]
    override_cols = [col for col in override_cols if col in human_reviewed_df.columns]

    display(
        human_reviewed_df[override_cols]
        .sort_values("final_priority_level")
        .reset_index(drop=True)
    )
else:
    print("\nNo human-reviewed priority overrides found.")

print("\nDashboard priority fields available:")
print("- priority_level = auto/adjudicated system priority")
print("- reviewed_priority_level = optional human override")
print("- final_priority_level = dashboard priority")
print("- priority_source = Auto Adjudicated or Human Reviewed")
print("- final_priority_rank = hidden/helper sort field")

# =============================================================================

# STEP 14 - Build market map view

# =============================================================================

# TODO: Paste current Step 14 Colab code here.

# =============================================================================

# STEP 15 - Segment-level summary

# =============================================================================

# TODO: Paste current Step 15 Colab code here.

# =============================================================================

# STEP 16 - Segment priority summary

# =============================================================================

# TODO: Paste current Step 16 Colab code here.

# =============================================================================

# STEP 17 - Company data depth audit

# =============================================================================

# TODO: Paste current Step 17 Colab code here.

# =============================================================================

# STEP 18 - Segment coverage audit

# =============================================================================

# TODO: Paste current Step 18 Colab code here.

# =============================================================================

# STEP 19 - Export dashboard workbook

# =============================================================================

# Purpose:

# - Export focused dashboard workbook

# - Keep Master Dashboard clean

# - Move priority traceability to Priority Logic Audit

# TODO: Paste current Step 19 Colab code here.

# =============================================================================

# STEP 19A - Format exported dashboard workbook

# =============================================================================

# Purpose:

# - Convert headers to readable labels

# - Apply filters

# - Freeze header row

# - Set column widths

# - Wrap text

# - Save/copy/download formatted workbook

# 19A - Format exported dashboard workbook
# Purpose:
# - Convert snake_case headers to readable labels in the workbook only
# - Apply filters
# - Freeze header row
# - Set readable column widths
# - Wrap text for long cells
# - Save formatted workbook locally
# - Copy formatted workbook to Google Drive
# - Download formatted workbook

from pathlib import Path
import re
import shutil
from google.colab import files
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# -----------------------------
# Locate workbook
# -----------------------------

if "dashboard_workbook_path" in globals():
    workbook_path = Path(dashboard_workbook_path)
elif "market_map_workbook_path" in globals():
    workbook_path = Path(market_map_workbook_path)
elif "output_workbook_path" in globals():
    workbook_path = Path(output_workbook_path)
elif "local_export_path" in globals():
    workbook_path = Path(local_export_path)
else:
    raise NameError(
        "STOP: Could not find dashboard_workbook_path, market_map_workbook_path, "
        "output_workbook_path, or local_export_path."
    )

if not workbook_path.exists():
    raise FileNotFoundError(f"STOP: Workbook not found: {workbook_path}")

if "drive_export_path" in globals():
    formatted_drive_path = Path(drive_export_path)
else:
    drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
    drive_folder.mkdir(parents=True, exist_ok=True)
    formatted_drive_path = drive_folder / workbook_path.name

# -----------------------------
# Header formatting helpers
# -----------------------------

def friendly_header(header):
    if header is None:
        return ""

    text = str(header).strip()

    explicit_map = {
        "company": "Company",
        "priority_level": "Priority Level",
        "reviewed_priority_level": "Reviewed Priority Level",
        "final_priority_level": "Final Priority Level",
        "priority_source": "Priority Source",
        "priority_review_note": "Priority Review Note",
        "final_priority_code": "Final Priority Code",
        "final_priority_rank": "Final Priority Rank",
        "decision_priority": "Decision Priority",
        "decision_priority_sort": "Decision Priority Sort",
        "review_status": "Review Status",
        "review_notes": "Review Notes",
        "thesis_fit_score": "Thesis Fit Score",
        "pmf_scale_score": "PMF / Scale Score",
        "evidence_confidence_score": "Evidence Confidence Score",
        "katelynd_role_fit_score": "Katelynd Role Fit Score",
        "operator_timing_score": "Operator Timing Score",
        "final_recommendation": "Final Recommendation",
        "business_model_classification": "Business Model Classification",
        "commercial_scale_assessment": "Commercial Scale Assessment",
        "pmf_scale_assessment": "PMF / Scale Assessment",
        "scale_signal_assessment": "Scale Signal Assessment",
        "calibration_flag": "Calibration Flag",
        "final_takeaway": "Final Takeaway",
        "date_researched": "Date Researched",
        "funding_finding": "Funding Finding",
        "payer_institutional_finding": "Payer / Institutional Finding",
        "outcomes_finding": "Outcomes Finding",
        "commercial_scale_finding": "Commercial Scale Finding",
        "fit_brief_json": "Fit Brief JSON",
        "segment": "Segment",
        "market_segment": "Market Segment",
        "strategic_bucket": "Strategic Bucket",
        "company_stage": "Company Stage",
        "funding_stage": "Funding Stage",
        "revenue_estimate": "Revenue Estimate",
        "employee_count": "Employee Count",
        "source_urls": "Source URLs",
        "notes": "Notes",
        "company_count": "Company Count",
        "p1_count": "P1 Count",
        "p2_count": "P2 Count",
        "p3_count": "P3 Count",
        "p4_count": "P4 Count",
        "human_reviewed_count": "Human Reviewed Count",
        "avg_thesis_fit": "Avg. Thesis Fit",
        "avg_pmf_scale": "Avg. PMF / Scale",
        "avg_evidence_confidence": "Avg. Evidence Confidence",
        "avg_katelynd_role_fit": "Avg. Katelynd Role Fit",
        "avg_operator_timing": "Avg. Operator Timing",
        "best_final_priority_level": "Best Final Priority Level",
        "best_final_priority_rank": "Best Final Priority Rank",
        "best_companies": "Best Companies",
        "current_best_companies": "Current Best Companies",
        "coverage_status": "Coverage Status",
        "companies_needed_for_directional_read": "Companies Needed for Directional Read",
        "companies_needed_for_stronger_read": "Companies Needed for Stronger Read",
        "data_depth_status": "Data Depth Status",
        "raw_record_count": "Raw Record Count",
        "raw_completeness_score": "Raw Completeness Score",
        "has_funding_raw": "Has Funding Raw",
        "has_payer_raw": "Has Payer Raw",
        "has_outcomes_raw": "Has Outcomes Raw",
        "has_commercial_scale_raw": "Has Commercial Scale Raw",
        "has_fit_brief_raw": "Has Fit Brief Raw",
        "fit_brief_json_parseable": "Fit Brief JSON Parseable",
        "raw_source_files": "Raw Source Files",
        "raw_batch_names": "Raw Batch Names"
    }

    if text in explicit_map:
        return explicit_map[text]

    text = text.replace("_", " ").strip()
    text = re.sub(r"\s+", " ", text)

    small_words = {"and", "or", "to", "of", "in", "for", "with", "by"}

    words = []
    for i, word in enumerate(text.split(" ")):
        lower = word.lower()

        if i > 0 and lower in small_words:
            words.append(lower)
        elif lower == "pmf":
            words.append("PMF")
        elif lower == "d2c":
            words.append("D2C")
        elif lower == "b2b2c":
            words.append("B2B2C")
        elif lower == "arr":
            words.append("ARR")
        elif lower == "cac":
            words.append("CAC")
        elif lower == "api":
            words.append("API")
        elif lower == "json":
            words.append("JSON")
        elif lower == "qa":
            words.append("QA")
        else:
            words.append(word.capitalize())

    return " ".join(words)

def width_for_header(header):
    header_lower = str(header).lower()

    very_long_text_terms = [
        "assessment",
        "finding",
        "takeaway",
        "rationale",
        "notes",
        "claim",
        "source",
        "json",
        "description",
        "summary",
        "commercial",
        "outcomes",
        "institutional",
        "companies needed",
        "current best companies",
        "best companies",
        "raw source files",
        "raw batch names"
    ]

    medium_text_terms = [
        "classification",
        "recommendation",
        "priority",
        "business model",
        "segment",
        "flag",
        "status",
        "bucket",
        "source"
    ]

    if any(term in header_lower for term in very_long_text_terms):
        return 44

    if any(term in header_lower for term in medium_text_terms):
        return 26

    if "company" in header_lower:
        return 24

    if "score" in header_lower or "rank" in header_lower or "count" in header_lower:
        return 14

    if "date" in header_lower:
        return 16

    return 18

# -----------------------------
# Format workbook
# -----------------------------

wb = load_workbook(workbook_path)

header_fill = PatternFill("solid", fgColor="D9EAF7")
header_font = Font(bold=True, color="000000")
thin_border = Border(
    bottom=Side(style="thin", color="B7B7B7")
)

for ws in wb.worksheets:
    if ws.max_row < 1 or ws.max_column < 1:
        continue

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for cell in ws[1]:
        original_header = cell.value
        display_header = friendly_header(original_header)

        cell.value = display_header
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )

    ws.row_dimensions[1].height = 36

    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        header_value = ws.cell(row=1, column=col_idx).value

        ws.column_dimensions[col_letter].width = width_for_header(header_value)

        for row_idx in range(2, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True
            )

    for row_idx in range(2, ws.max_row + 1):
        ws.row_dimensions[row_idx].height = 45

    for col_idx in range(1, ws.max_column + 1):
        header_value = str(ws.cell(row=1, column=col_idx).value or "").strip().lower()

        if header_value in [
            "final priority rank",
            "final priority code",
            "decision priority sort",
            "data depth status rank",
            "coverage status rank"
        ]:
            ws.column_dimensions[get_column_letter(col_idx)].hidden = True

# -----------------------------
# Save, sync, download
# -----------------------------

wb.save(workbook_path)
shutil.copy(workbook_path, formatted_drive_path)

print("PASS: Dashboard workbook formatted.")
print("Formatted local workbook:", workbook_path)
print("Formatted Drive workbook:", formatted_drive_path)

files.download(str(workbook_path))

