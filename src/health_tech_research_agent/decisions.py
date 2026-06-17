from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import pandas as pd

from .google_sheets import safe_text, validate_review_packet_readback
from .models import CompanyState


class DecisionValidationError(ValueError):
    def __init__(self, issues: list[dict[str, str]]):
        self.issues = issues
        summary = "; ".join(
            f"{item.get('company') or '[batch]'}: {item['issue']}"
            for item in issues
        )
        super().__init__(f"Review decision validation failed: {summary}")


@dataclass(frozen=True)
class ValidatedReviewDecisions:
    batch_id: str
    decisions_df: pd.DataFrame
    approved_df: pd.DataFrame
    held_df: pd.DataFrame
    rejected_df: pd.DataFrame


_DECISION_ALIASES = {
    "approve": "APPROVE",
    "approved": "APPROVE",
    "include": "APPROVE",
    "update": "APPROVE",
    "add": "APPROVE",
    "downgrade": "APPROVE",
    "hold": "HOLD",
    "held": "HOLD",
    "needs_more_research": "HOLD",
    "needs more research": "HOLD",
    "needs-more-research": "HOLD",
    "reject": "REJECT",
    "rejected": "REJECT",
    "exclude": "REJECT",
    "skip": "REJECT",
}

_READY_ALIASES = {
    "yes": "YES",
    "y": "YES",
    "true": "YES",
    "1": "YES",
    "no": "NO",
    "n": "NO",
    "false": "NO",
    "0": "NO",
}

_PRIORITY_PATTERN = re.compile(r"\bP[0-4]\b", re.IGNORECASE)


def normalize_review_decision(value: Any) -> str:
    text = safe_text(value).lower()
    return _DECISION_ALIASES.get(text, "")


def normalize_ready_for_master(value: Any) -> str:
    text = safe_text(value).lower()
    return _READY_ALIASES.get(text, "")


def extract_priority_code(value: Any) -> str:
    match = _PRIORITY_PATTERN.search(safe_text(value))
    return match.group(0).upper() if match else ""


def _issue(company: str, message: str) -> dict[str, str]:
    return {"company": company, "issue": message}


def validate_and_build_review_decisions(
    review_df: pd.DataFrame,
    *,
    batch_id: str,
    expected_companies: list[str],
) -> ValidatedReviewDecisions:
    required_columns = [
        "company",
        "review_decision",
        "reviewed_priority",
        "review_notes",
        "ready_for_master_update",
        "reviewed_at",
    ]

    try:
        validate_review_packet_readback(
            review_df,
            batch_id=batch_id,
            expected_companies=expected_companies,
            required_columns=required_columns,
        )
    except Exception as exc:
        raise DecisionValidationError([
            _issue("", str(exc)),
        ]) from exc

    issues: list[dict[str, str]] = []
    decision_rows: list[dict[str, str]] = []
    approved_rows: list[dict[str, str]] = []

    for _, row in review_df.iterrows():
        company = safe_text(row.get("company"))
        raw_decision = safe_text(row.get("review_decision"))
        normalized_decision = normalize_review_decision(raw_decision)
        ready = normalize_ready_for_master(
            row.get("ready_for_master_update")
        )
        reviewed_priority = safe_text(row.get("reviewed_priority"))
        priority_code = extract_priority_code(reviewed_priority)
        review_notes = safe_text(row.get("review_notes"))
        priority_review_note = (
            safe_text(row.get("priority_review_note")) or review_notes
        )
        reviewed_at = safe_text(row.get("reviewed_at"))

        if not raw_decision:
            issues.append(_issue(company, "review_decision is blank."))
        elif not normalized_decision:
            issues.append(
                _issue(
                    company,
                    f"unsupported review_decision={raw_decision!r}.",
                )
            )

        if not ready:
            issues.append(
                _issue(
                    company,
                    "ready_for_master_update must explicitly be YES or NO.",
                )
            )

        if normalized_decision == "APPROVE" and ready != "YES":
            issues.append(
                _issue(
                    company,
                    "APPROVE requires ready_for_master_update=YES.",
                )
            )
        if normalized_decision in {"HOLD", "REJECT"} and ready != "NO":
            issues.append(
                _issue(
                    company,
                    f"{normalized_decision} requires ready_for_master_update=NO.",
                )
            )

        if normalized_decision == "APPROVE" and not reviewed_priority:
            issues.append(
                _issue(company, "approved company has blank reviewed_priority.")
            )
        if reviewed_priority and not priority_code:
            issues.append(
                _issue(
                    company,
                    "reviewed_priority must include P0, P1, P2, P3, or P4.",
                )
            )

        if not review_notes:
            issues.append(_issue(company, "review_notes is blank."))
        if not reviewed_at:
            issues.append(_issue(company, "reviewed_at is blank."))

        if normalized_decision == "APPROVE":
            company_state = CompanyState.APPROVED.value
            master_action = "UPSERT"
            step_status = "READY_FOR_MASTER_UPDATE"
        elif normalized_decision == "REJECT":
            company_state = CompanyState.REJECTED.value
            master_action = "REJECT"
            step_status = "REJECTED_FROM_MASTER_UPDATE"
        else:
            company_state = CompanyState.HELD.value
            master_action = "HOLD"
            step_status = "HELD_FROM_MASTER_UPDATE"

        decision_rows.append({
            "batch_id": batch_id,
            "company": company,
            "raw_review_decision": raw_decision,
            "normalized_decision": normalized_decision,
            "reviewed_priority_level": reviewed_priority,
            "reviewed_priority_code": priority_code,
            "review_notes": review_notes,
            "priority_review_note": priority_review_note,
            "ready_for_master_update": ready,
            "reviewed_at": reviewed_at,
            "company_state": company_state,
            "master_action": master_action,
            "decision_status": step_status,
        })

        if normalized_decision == "APPROVE" and ready == "YES":
            approved_rows.append({
                "batch_id": batch_id,
                "company": company,
                "decision": "approve",
                "reviewed_priority_level": reviewed_priority,
                "reviewed_priority_code": priority_code,
                "review_status": "Human reviewed",
                "review_notes": review_notes,
                "priority_review_note": priority_review_note,
                "ready_for_master_update": ready,
                "reviewed_at": reviewed_at,
            })

    if issues:
        raise DecisionValidationError(issues)

    decisions_df = pd.DataFrame(decision_rows)
    approved_df = pd.DataFrame(approved_rows, columns=[
        "batch_id",
        "company",
        "decision",
        "reviewed_priority_level",
        "reviewed_priority_code",
        "review_status",
        "review_notes",
        "priority_review_note",
        "ready_for_master_update",
        "reviewed_at",
    ])

    return ValidatedReviewDecisions(
        batch_id=batch_id,
        decisions_df=decisions_df,
        approved_df=approved_df,
        held_df=decisions_df[
            decisions_df["normalized_decision"].eq("HOLD")
        ].reset_index(drop=True),
        rejected_df=decisions_df[
            decisions_df["normalized_decision"].eq("REJECT")
        ].reset_index(drop=True),
    )
