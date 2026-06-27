from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

import pandas as pd

from .storage import atomic_write_csv


REQUIRED_RESEARCH_COLUMNS = [
    "company",
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "growth_finding",
    "paying_finding",
    "org_events_finding",
    "operating_characteristics_finding",
    "fit_brief_json",
]


class ReviewPacketError(RuntimeError):
    pass


def clean_json_text(text: Any) -> str:
    value = str(text).strip()
    value = re.sub(r"^```json", "", value)
    value = re.sub(r"^```", "", value)
    value = re.sub(r"```$", "", value)
    return value.strip()


def parse_first_json_object(text: Any) -> dict[str, Any]:
    raw = clean_json_text(text)
    start = raw.find("{")
    if start == -1:
        raise ValueError("No JSON object found.")

    decoder = json.JSONDecoder()
    parsed, _ = decoder.raw_decode(raw[start:])

    if not isinstance(parsed, dict):
        raise ValueError("Fit brief JSON root must be an object.")

    return parsed


def validate_completed_research(
    df: pd.DataFrame,
    *,
    expected_companies: list[str] | None = None,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    missing_columns = [
        column for column in REQUIRED_RESEARCH_COLUMNS
        if column not in df.columns
    ]
    if missing_columns:
        return [{
            "company": "BATCH",
            "issue": f"Missing required columns: {missing_columns}",
        }]

    if expected_companies is not None:
        actual = set(df["company"].astype(str))
        expected = set(expected_companies)

        for company in sorted(expected - actual):
            issues.append({
                "company": company,
                "issue": "Missing expected company.",
            })

        for company in sorted(actual - expected):
            issues.append({
                "company": company,
                "issue": "Unexpected company present.",
            })

    duplicate_mask = df["company"].astype(str).duplicated(keep=False)
    for company in sorted(set(df.loc[duplicate_mask, "company"].astype(str))):
        issues.append({
            "company": company,
            "issue": "Duplicate company row.",
        })

    for _, row in df.iterrows():
        company = str(row["company"])

        for column in REQUIRED_RESEARCH_COLUMNS:
            value = row.get(column, "")
            if pd.isna(value) or str(value).strip() == "":
                issues.append({
                    "company": company,
                    "issue": f"Blank required field: {column}",
                })

        try:
            parse_first_json_object(row["fit_brief_json"])
        except Exception as exc:
            issues.append({
                "company": company,
                "issue": f"Invalid fit_brief_json: {exc}",
            })

    return issues


def _score(parsed: dict[str, Any], key: str) -> Any:
    value = parsed.get("scores", {}).get(key, "")
    if isinstance(value, dict):
        return value.get("score", "")
    return value


def _join_tags(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    return "" if value is None else str(value).strip()


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, raw_row in df.iterrows():
        parsed = parse_first_json_object(raw_row["fit_brief_json"])
        taxonomy = parsed.get("taxonomy_classification", {})
        if not isinstance(taxonomy, dict):
            taxonomy = {}

        scale = parsed.get("scale_signal_assessment", {})
        if not isinstance(scale, dict):
            scale = {}

        timing = parsed.get("role_timing_assessment", {})
        if not isinstance(timing, dict):
            timing = {}

        rows.append({
            "company": str(raw_row["company"]).strip(),
            "thesis_fit_score": _score(parsed, "thesis_fit_score"),
            "pmf_scale_score": _score(parsed, "pmf_scale_score"),
            "evidence_confidence_score": _score(parsed, "evidence_confidence_score"),
            "katelynd_role_fit_score": _score(parsed, "katelynd_role_fit_score"),
            "operator_timing_score": _score(parsed, "operator_timing_score"),
            "final_recommendation": parsed.get("final_recommendation", ""),
            "priority_level": parsed.get("priority_level", ""),
            "business_model_classification": parsed.get(
                "business_model_classification", ""
            ),
            "primary_market_segment_code": taxonomy.get(
                "primary_market_segment", ""
            ),
            "subsegment_tags": _join_tags(taxonomy.get("subsegment_tags", [])),
            "product_model_tags": _join_tags(taxonomy.get("product_model_tags", [])),
            "distribution_model_tags": _join_tags(
                taxonomy.get("distribution_model_tags", [])
            ),
            "data_input_tags": _join_tags(taxonomy.get("data_input_tags", [])),
            "taxonomy_assignment_method": (
                "llm_fit_brief"
                if taxonomy.get("primary_market_segment")
                else ""
            ),
            "taxonomy_assignment_basis": taxonomy.get(
                "classification_rationale", ""
            ),
            "commercial_scale_assessment": parsed.get(
                "commercial_scale_assessment", ""
            ),
            "pmf_scale_assessment": parsed.get("pmf_scale_assessment", ""),
            "commercial_scale_signal": scale.get("commercial_scale_signal", ""),
            "institutional_distribution_signal": scale.get(
                "institutional_distribution_signal", ""
            ),
            "outcomes_signal": scale.get("outcomes_signal", ""),
            "scale_engine_type": scale.get("scale_engine_type", ""),
            "plausible_near_term_scale_path": scale.get(
                "plausible_near_term_scale_path", ""
            ),
            "company_maturity_read": timing.get("company_maturity_read", ""),
            "likely_agency_level": timing.get("likely_agency_level", ""),
            "stage_timing_fit": timing.get("stage_timing_fit", ""),
            "why_now_or_why_not": timing.get("why_now_or_why_not", ""),
            "calibration_flag": parsed.get("calibration_flag", ""),
            "entity_review_needed": parsed.get("entity_review_needed", ""),
            "final_takeaway": parsed.get("final_takeaway", ""),
            "funding_finding": raw_row.get("funding_finding", ""),
            "payer_institutional_finding": raw_row.get(
                "payer_institutional_finding", ""
            ),
            "outcomes_finding": raw_row.get("outcomes_finding", ""),
            "commercial_scale_finding": raw_row.get(
                "commercial_scale_finding", ""
            ),
        })

    summary = pd.DataFrame(rows)

    for column in [
        "thesis_fit_score",
        "pmf_scale_score",
        "evidence_confidence_score",
        "katelynd_role_fit_score",
        "operator_timing_score",
    ]:
        summary[column] = pd.to_numeric(summary[column], errors="coerce")

    return summary


def build_review_packet(
    summary_df: pd.DataFrame,
    *,
    batch_id: str,
) -> pd.DataFrame:
    packet = summary_df.copy()
    packet.insert(0, "batch_id", batch_id)

    for column in [
        "review_decision",
        "reviewed_priority",
        "review_notes",
        "ready_for_master_update",
        "reviewed_at",
        "step_22_status",
    ]:
        if column not in packet.columns:
            packet[column] = ""

    return packet


def write_review_packet(
    packet_df: pd.DataFrame,
    *,
    output_path: str | Path,
) -> Path:
    if packet_df.empty:
        raise ReviewPacketError("Review packet is empty.")

    if packet_df["company"].duplicated().any():
        duplicates = packet_df.loc[
            packet_df["company"].duplicated(keep=False),
            "company",
        ].tolist()
        raise ReviewPacketError(
            f"Duplicate companies in review packet: {duplicates}"
        )

    return atomic_write_csv(output_path, packet_df)
