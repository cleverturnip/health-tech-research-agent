# =============================================================================
# STEP 10A - Deterministic priority adjudication
# =============================================================================
# Purpose:
# - Enforce hard priority rules after LLM scoring
# - Use native P0/P1/P2/P3/P4 priority labels
# - Prevent role fit / thesis interest from incorrectly promoting weak-scale companies
# - Treat incorrect outputs as decision-logic calibration data
# - Update fit_brief_json in df, checkpoint, and current batch raw/archive rows
#
# Required flow:
# 1. Run Step 10
# 2. Run this Step 10A cell
# 3. Rerun Step 10
# 4. Run Step 10B

import json
import re
import pandas as pd
import shutil
from pathlib import Path

# -----------------------------
# Safety checks
# -----------------------------

if "df" not in globals() or not isinstance(df, pd.DataFrame) or df.empty:
    raise NameError("STOP: df is not available or empty.")

if "BATCH_NAME" not in globals():
    raise NameError("STOP: BATCH_NAME is not defined.")

if "batch_checkpoint_path" not in globals() or "drive_checkpoint_path" not in globals():
    raise NameError("STOP: checkpoint paths are not defined.")

required_current_schema_cols = [
    "company",
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "org_events_finding",                  # FIX: Slice 3.7 finding (was dropped)
    "operating_characteristics_finding",   # FIX: Slice 3.7 finding (was dropped)
    "fit_brief_json"
]

missing_cols = [col for col in required_current_schema_cols if col not in df.columns]

if missing_cols:
    raise ValueError(f"STOP: df missing required columns: {missing_cols}")

# -----------------------------
# JSON helpers
# -----------------------------

def clean_json_text(text):
    text = str(text).strip()
    text = re.sub(r"^```json", "", text)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()

def parse_first_json_object(text):
    raw = clean_json_text(text)
    start = raw.find("{")

    if start == -1:
        raise ValueError("No JSON object found")

    decoder = json.JSONDecoder()
    parsed, end = decoder.raw_decode(raw[start:])
    return parsed

def get_score(parsed, key):
    scores = parsed.get("scores", {})
    value = scores.get(key)

    if isinstance(value, dict):
        return value.get("score")

    return value

def safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default

def normalize_signal(value):
    text = str(value).strip().lower()

    if text in ["strong", "moderate", "weak", "none"]:
        return text

    if "strong" in text:
        return "strong"
    if "moderate" in text or "medium" in text:
        return "moderate"
    if "weak" in text:
        return "weak"
    if "none" in text or text in ["no", "n/a", "na", ""]:
        return "none"

    return "none"

def text_contains_any(text, terms):
    text = str(text).lower()
    return any(term.lower() in text for term in terms)

def bool_from_value(value, default=False):
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in ["true", "yes", "1"]:
        return True

    if text in ["false", "no", "0"]:
        return False

    return default

def append_flag(existing, new_flag):
    existing = str(existing or "").strip()

    if not existing:
        return new_flag

    if new_flag in existing:
        return existing

    return existing + " | " + new_flag

def priority_code(value):
    text = str(value or "").upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""

def normalize_priority_label(value):
    text = str(value or "").strip()
    lower = text.lower()

    if lower.startswith("p0") or "highest-priority" in lower or "highest priority" in lower:
        return "P0: Highest-priority target"

    if (
        lower.startswith("p1: near-priority")
        or lower.startswith("p1: near priority")
        or "near-priority" in lower
        or "near priority" in lower
        or "p1-border" in lower
        or "p1 border" in lower
        or "strong p2" in lower
    ):
        return "P1: Near-priority target"

    # Backward compatibility: old P1 means new P0.
    if lower.startswith("p1: high-priority") or lower.startswith("p1: high priority"):
        return "P0: Highest-priority target"

    if lower.startswith("p2") or "review p2" in lower or "worth deeper diligence" in lower:
        return "P2: Worth deeper diligence"

    if lower.startswith("p3") or "watch list" in lower or "watchlist" in lower:
        return "P3: Watch list"

    if lower.startswith("p4") or "low priority" in lower or "likely reject" in lower or "reject" in lower:
        return "P4: Low priority / likely reject"

    return text

def recommendation_for_priority(priority_level):
    code = priority_code(priority_level)

    return {
        "P0": "Strong fit, active pursuit",
        "P1": "Strong fit, near-priority diligence",
        "P2": "Possible fit, pending diligence",
        "P3": "Watch list",
        "P4": "Weak fit"
    }.get(code, "Watch list")

# -----------------------------
# Signal inference helpers
# -----------------------------

def get_scale_assessment(parsed):
    scale_assessment = parsed.get("scale_signal_assessment", {})

    if isinstance(scale_assessment, dict):
        return scale_assessment

    return {}

def infer_commercial_signal(row, parsed):
    scale_assessment = get_scale_assessment(parsed)
    explicit = normalize_signal(scale_assessment.get("commercial_scale_signal", ""))

    if explicit in ["strong", "moderate", "weak", "none"] and str(scale_assessment.get("commercial_scale_signal", "")).strip():
        return explicit

    text = " ".join([
        str(row.get("commercial_scale_finding", "")),
        str(parsed.get("commercial_scale_assessment", "")),
        str(parsed.get("pmf_scale_assessment", "")),
    ]).lower()

    weak_markers = [
        "weak public commercial",
        "weak commercial",
        "no strong public commercial",
        "no strong public commercial scale",
        "no credible public arr",
        "no public arr",
        "no company-reported arr",
        "no company-reported revenue",
        "no credible third-party revenue",
        "no credible third-party revenue estimate",
        "not well evidenced",
        "unproven publicly",
        "commercial traction remains unsubstantiated",
        "does not yet establish strong revenue quality",
        "pricing exists, but commercial traction remains unsubstantiated"
    ]

    strong_markers = [
        "strong commercial",
        "$100m",
        "$1b",
        "$500m",
        "100m revenue",
        "100m arr",
        "1b arr",
        "500m/year",
        "paid-member scale",
        "paid-user scale",
        "paying members",
        "paying subscribers",
        "subscribers",
        "first-year renewal",
        "substantial paid-user scale",
        "meaningful paid-customer scale",
        "credible estimated revenue",
        "estimated revenue",
        "revenue run-rate",
        "arr"
    ]

    moderate_markers = [
        "moderate commercial",
        "moderately evidenced",
        "paid pricing",
        "subscription model",
        "membership model",
        "test-kit",
        "consumer usage",
        "pricing and product signals",
        "visible pricing",
        "real business model"
    ]

    if text_contains_any(text, weak_markers):
        return "weak"

    if text_contains_any(text, strong_markers):
        return "strong"

    if text_contains_any(text, moderate_markers):
        return "moderate"

    return "none"

def infer_institutional_signal(row, parsed):
    scale_assessment = get_scale_assessment(parsed)
    explicit = normalize_signal(scale_assessment.get("institutional_distribution_signal", ""))

    if explicit in ["strong", "moderate", "weak", "none"] and str(scale_assessment.get("institutional_distribution_signal", "")).strip():
        return explicit

    text = " ".join([
        str(row.get("payer_institutional_finding", "")),
        str(parsed.get("pmf_scale_assessment", "")),
        str(parsed.get("business_model_classification", "")),
    ]).lower()

    weak_markers = [
        "no strong public institutional",
        "no strong institutional signal",
        "mostly d2c",
        "mostly d2c/cash-pay",
        "no public payer contracts",
        "no clear payer contracts",
        "no medicare",
        "no medicaid",
        "not broad payer",
        "not broad institutional",
        "does not surface clear payer contracts",
        "no clear evidence of payer contracts"
    ]

    strong_markers = [
        "strong institutional",
        "top health plans",
        "health plans and employers",
        "employer/health-plan",
        "employers/health plans",
        "covered lives",
        "health-plan channels",
        "enterprise clients",
        "employer customers",
        "lives covered",
        "payer contracts",
        "provider network",
        "health system"
    ]

    moderate_markers = [
        "some institutional",
        "limited partner",
        "employer-facing",
        "provider-facing",
        "b2b2c",
        "partnership",
        "employer page",
        "provider referral",
        "benefits-consultant",
        "one named plan partnership",
        "emerging payer-linked distribution"
    ]

    if text_contains_any(text, weak_markers):
        return "weak"

    if text_contains_any(text, strong_markers):
        return "strong"

    if text_contains_any(text, moderate_markers):
        return "moderate"

    return "none"

def infer_outcomes_signal(row, parsed):
    scale_assessment = get_scale_assessment(parsed)
    explicit = normalize_signal(scale_assessment.get("outcomes_signal", ""))

    if explicit in ["strong", "moderate", "weak", "none"] and str(scale_assessment.get("outcomes_signal", "")).strip():
        return explicit

    text = " ".join([
        str(row.get("outcomes_finding", "")),
        str(parsed.get("pmf_scale_assessment", "")),
    ]).lower()

    weak_markers = [
        "no strong public outcomes",
        "no peer-reviewed",
        "no clinical trials",
        "not a clinical trial",
        "no control group",
        "mostly marketing",
        "limited public evidence",
        "no meaningful outcomes",
        "not independently validated outcomes"
    ]

    strong_markers = [
        "randomized controlled trial",
        "nature medicine",
        "peer-reviewed",
        "published real-world evidence",
        "claims-based study",
        "clinical efficacy",
        "real-world evidence",
        "health improvement",
        "reduced costs",
        "improved outcomes"
    ]

    moderate_markers = [
        "mixed",
        "weak-to-moderate",
        "moderate evidence",
        "company-reported",
        "retrospective",
        "engagement-linked",
        "validation studies",
        "measurement studies",
        "behavior-change"
    ]

    if text_contains_any(text, weak_markers):
        return "weak"

    if text_contains_any(text, strong_markers):
        return "strong"

    if text_contains_any(text, moderate_markers):
        return "moderate"

    return "none"

# -----------------------------
# Deterministic adjudication logic
# -----------------------------

adjudication_rows = []

for idx, row in df.iterrows():
    company = str(row["company"]).strip()
    parsed = parse_first_json_object(row["fit_brief_json"])

    thesis = safe_int(get_score(parsed, "thesis_fit_score"))
    pmf = safe_int(get_score(parsed, "pmf_scale_score"))
    evidence = safe_int(get_score(parsed, "evidence_confidence_score"))
    role_fit = safe_int(get_score(parsed, "katelynd_role_fit_score"))
    timing = safe_int(get_score(parsed, "operator_timing_score"))

    scale_assessment = get_scale_assessment(parsed)

    commercial_signal = infer_commercial_signal(row, parsed)
    institutional_signal = infer_institutional_signal(row, parsed)
    outcomes_signal = infer_outcomes_signal(row, parsed)

    plausible_near_term_scale_path = bool_from_value(
        scale_assessment.get("plausible_near_term_scale_path"),
        default=False
    )

    if not plausible_near_term_scale_path:
        plausible_near_term_scale_path = (
            commercial_signal == "strong" or
            institutional_signal == "strong" or
            (
                outcomes_signal == "strong" and
                (
                    commercial_signal in ["moderate", "strong"] or
                    institutional_signal in ["moderate", "strong"]
                )
            )
        )

    commercial_strong_gate = commercial_signal == "strong" and evidence >= 50
    institutional_strong_gate = institutional_signal == "strong" and evidence >= 50

    outcomes_plus_scale_path_gate = (
        outcomes_signal == "strong" and
        plausible_near_term_scale_path is True and
        evidence >= 55 and
        pmf >= 70 and
        (
            commercial_signal in ["moderate", "strong"] or
            institutional_signal in ["moderate", "strong"]
        )
    )

    score_qualifies_for_p2 = pmf >= 70 and evidence >= 50

    qualifies_for_p2 = (
        score_qualifies_for_p2 or
        commercial_strong_gate or
        institutional_strong_gate or
        outcomes_plus_scale_path_gate
    )

    strong_signal_count = sum([
        commercial_signal == "strong",
        institutional_signal == "strong",
        outcomes_signal == "strong"
    ])

    moderate_or_strong_signal_count = sum([
        commercial_signal in ["moderate", "strong"],
        institutional_signal in ["moderate", "strong"],
        outcomes_signal in ["moderate", "strong"]
    ])

    qualifies_for_p1 = (
        qualifies_for_p2 and
        thesis >= 85 and
        pmf >= 74 and
        evidence >= 55 and
        role_fit >= 78 and
        timing >= 72 and
        (
            strong_signal_count >= 1 or
            moderate_or_strong_signal_count >= 2
        )
    )

    qualifies_for_p0 = (
        qualifies_for_p1 and
        thesis >= 88 and
        pmf >= 82 and
        evidence >= 75 and
        role_fit >= 80 and
        timing >= 78 and
        (
            strong_signal_count >= 3 or
            (
                institutional_signal == "strong" and
                outcomes_signal in ["moderate", "strong"] and
                commercial_signal in ["moderate", "strong"]
            ) or
            (
                commercial_signal == "strong" and
                institutional_signal == "strong"
            )
        )
    )


    qualifies_for_p4 = (
        not qualifies_for_p2 and
        (
            thesis < 55 or
            pmf < 45 or
            role_fit < 55 or
            timing < 55
        ) and
        commercial_signal in ["weak", "none"] and
        institutional_signal in ["weak", "none"]
    )

    original_priority = normalize_priority_label(parsed.get("priority_level", ""))
    original_flag = str(parsed.get("calibration_flag", "") or "").strip()

    if qualifies_for_p0:
        adjudicated_priority = "P0: Highest-priority target"
        adjudication_action = "assigned_P0"

    elif qualifies_for_p1:
        adjudicated_priority = "P1: Near-priority target"
        adjudication_action = "assigned_P1"

    elif qualifies_for_p2:
        adjudicated_priority = "P2: Worth deeper diligence"
        adjudication_action = "assigned_P2"

    elif qualifies_for_p4:
        adjudicated_priority = "P4: Low priority / likely reject"
        adjudication_action = "assigned_P4"

    else:
        adjudicated_priority = "P3: Watch list"
        adjudication_action = "assigned_P3"

    adjudicated_recommendation = recommendation_for_priority(adjudicated_priority)
    adjudicated_flag = original_flag

    if original_priority != "" and original_priority != adjudicated_priority:
        adjudicated_flag = append_flag(
            adjudicated_flag,
            f"Deterministic gate: reassigned from {original_priority} to {adjudicated_priority}."
        )

    if adjudicated_priority.startswith("P1"):
        adjudicated_flag = append_flag(
            adjudicated_flag,
            "Deterministic gate: P1 indicates near-priority / former P1-border; validate before active pursuit."
        )

    if adjudicated_priority.startswith("P2") and (evidence < 65 or pmf < 70):
        adjudicated_flag = append_flag(
            adjudicated_flag,
            "Deterministic gate: P2 has moderate evidence and/or PMF; diligence required."
        )

    parsed["priority_adjudication"] = {
        "decision_logic_version": "p0_p4_scale_engine_gate_v2",
        "commercial_scale_signal": commercial_signal,
        "institutional_distribution_signal": institutional_signal,
        "outcomes_signal": outcomes_signal,
        "plausible_near_term_scale_path": plausible_near_term_scale_path,
        "strong_signal_count": strong_signal_count,
        "moderate_or_strong_signal_count": moderate_or_strong_signal_count,
        "score_qualifies_for_p2": score_qualifies_for_p2,
        "commercial_strong_gate": commercial_strong_gate,
        "institutional_strong_gate": institutional_strong_gate,
        "outcomes_plus_scale_path_gate": outcomes_plus_scale_path_gate,
        "qualifies_for_p2": qualifies_for_p2,
        "qualifies_for_p1": qualifies_for_p1,
        "qualifies_for_p0": qualifies_for_p0,
        "qualifies_for_p4": qualifies_for_p4,
        "original_priority_level": original_priority,
        "adjudicated_priority_level": adjudicated_priority,
        "adjudication_action": adjudication_action
    }

    parsed["priority_level"] = adjudicated_priority
    parsed["final_recommendation"] = adjudicated_recommendation
    parsed["calibration_flag"] = adjudicated_flag

    if adjudicated_priority.startswith("P3"):
        parsed["final_takeaway"] = (
            f"{company} remains strategically interesting, but the current public evidence does not clear the P2 priority gate. "
            "Keep on watch list until stronger commercial traction, institutional distribution, or outcomes-plus-scale evidence emerges."
        )

    elif adjudicated_priority.startswith("P4"):
        parsed["final_takeaway"] = (
            f"{company} does not currently clear the job-search priority gate based on available evidence. "
            "Revisit only if stronger scale, outcomes, or role-fit evidence emerges."
        )

    df.loc[idx, "fit_brief_json"] = json.dumps(parsed, indent=2, ensure_ascii=False)

    adjudication_rows.append({
        "company": company,
        "thesis_fit_score": thesis,
        "pmf_scale_score": pmf,
        "evidence_confidence_score": evidence,
        "katelynd_role_fit_score": role_fit,
        "operator_timing_score": timing,
        "commercial_scale_signal": commercial_signal,
        "institutional_distribution_signal": institutional_signal,
        "outcomes_signal": outcomes_signal,
        "plausible_near_term_scale_path": plausible_near_term_scale_path,
        "strong_signal_count": strong_signal_count,
        "moderate_or_strong_signal_count": moderate_or_strong_signal_count,
        "score_qualifies_for_p2": score_qualifies_for_p2,
        "commercial_strong_gate": commercial_strong_gate,
        "institutional_strong_gate": institutional_strong_gate,
        "outcomes_plus_scale_path_gate": outcomes_plus_scale_path_gate,
        "qualifies_for_p2": qualifies_for_p2,
        "qualifies_for_p1": qualifies_for_p1,
        "qualifies_for_p0": qualifies_for_p0,
        "qualifies_for_p4": qualifies_for_p4,
        "original_priority": original_priority,
        "adjudicated_priority": adjudicated_priority,
        "adjudication_action": adjudication_action
    })

adjudication_df = pd.DataFrame(adjudication_rows)

# -----------------------------
# Save corrected checkpoint
# -----------------------------

df = df[required_current_schema_cols].copy().reset_index(drop=True)
checkpoint_df = df.copy()

Path(batch_checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
df.to_csv(batch_checkpoint_path, index=False)

Path(drive_checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
shutil.copy(batch_checkpoint_path, drive_checkpoint_path)

print("PASS: Deterministic priority adjudication applied.")
print("Local checkpoint:", batch_checkpoint_path)
print("Drive checkpoint:", drive_checkpoint_path)

print("\nAdjudication summary:")
display(adjudication_df)

# -----------------------------
# Update already-written raw/archive rows in place
# -----------------------------

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_batches_folder = drive_folder / "research_batches"
local_batches_folder = Path("research_batches")

archive_paths = [
    Path("health_tech_raw_research_ARCHIVE.csv"),
    drive_folder / "health_tech_raw_research_ARCHIVE.csv"
]

archive_paths.extend(sorted(local_batches_folder.glob(f"{BATCH_NAME}_raw_*.csv")))
archive_paths.extend(sorted(drive_batches_folder.glob(f"{BATCH_NAME}_raw_*.csv")))

updated_files = []

for archive_path in archive_paths:
    archive_path = Path(archive_path)

    if not archive_path.exists():
        continue

    archive_df = pd.read_csv(archive_path)

    if "batch_name" not in archive_df.columns or "company" not in archive_df.columns:
        continue

    batch_mask = archive_df["batch_name"].astype(str).eq(BATCH_NAME)

    if not batch_mask.any():
        continue

    for _, source_row in df.iterrows():
        company = source_row["company"]
        row_mask = batch_mask & archive_df["company"].astype(str).eq(company)

        if not row_mask.any():
            continue

        for col in required_current_schema_cols:
            if col in archive_df.columns:
                archive_df.loc[row_mask, col] = source_row[col]

    archive_df.to_csv(archive_path, index=False)
    updated_files.append(str(archive_path))

print("\nUpdated archive/current-batch files:")
for path in updated_files:
    print("-", path)

print("\nNext: rerun Step 10, then Step 10B.")
