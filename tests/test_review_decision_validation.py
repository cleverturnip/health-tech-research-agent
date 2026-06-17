from pathlib import Path

import pandas as pd
import pytest

from health_tech_research_agent.decisions import (
    DecisionValidationError,
    validate_and_build_review_decisions,
)
from health_tech_research_agent.models import (
    BatchState,
    CompanyState,
    WorkflowStatus,
)
from health_tech_research_agent.settings import load_settings
from health_tech_research_agent.state import (
    create_batch_manifest,
    load_batch_manifest,
    save_batch_manifest,
)
from health_tech_research_agent.workflow import (
    read_review_decisions_to_master_gate,
)


class FakeWorksheet:
    def __init__(self, title: str, values: list[list[str]]):
        self.title = title
        self.values = values

    def get_all_values(self):
        return [list(row) for row in self.values]


class FakeSpreadsheet:
    def __init__(self, worksheet: FakeWorksheet):
        self._worksheet = worksheet

    def worksheet(self, title: str):
        assert title == self._worksheet.title
        return self._worksheet


def _review_df(
    *,
    company_b_decision: str = "NEEDS_MORE_RESEARCH",
    company_b_ready: str = "NO",
) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "batch_name": "test_batch",
            "company": "Company A",
            "review_decision": "APPROVE",
            "reviewed_priority": "P2: Worth deeper diligence",
            "review_notes": "Approved after human review.",
            "ready_for_master_update": "YES",
            "reviewed_at": "2026-06-17",
            "step_22_status": "",
        },
        {
            "batch_name": "test_batch",
            "company": "Company B",
            "review_decision": company_b_decision,
            "reviewed_priority": "P3: Watch list",
            "review_notes": "Hold pending clean research.",
            "ready_for_master_update": company_b_ready,
            "reviewed_at": "2026-06-17",
            "step_22_status": "",
        },
    ])


def _worksheet_values(df: pd.DataFrame) -> list[list[str]]:
    return [list(df.columns)] + df.astype(str).values.tolist()


def test_validator_accepts_approve_and_needs_more_research():
    result = validate_and_build_review_decisions(
        _review_df(),
        batch_id="test_batch",
        expected_companies=["Company A", "Company B"],
    )

    assert result.approved_df["company"].tolist() == ["Company A"]
    assert result.held_df["company"].tolist() == ["Company B"]
    assert result.rejected_df.empty
    assert result.approved_df.iloc[0]["reviewed_priority_code"] == "P2"


def test_validator_rejects_blank_decision():
    df = _review_df()
    df.loc[df["company"].eq("Company B"), "review_decision"] = ""

    with pytest.raises(DecisionValidationError) as exc_info:
        validate_and_build_review_decisions(
            df,
            batch_id="test_batch",
            expected_companies=["Company A", "Company B"],
        )

    assert "Company B" in str(exc_info.value)
    assert "review_decision is blank" in str(exc_info.value)


def test_validator_rejects_approve_without_yes():
    df = _review_df(
        company_b_decision="APPROVE",
        company_b_ready="NO",
    )

    with pytest.raises(DecisionValidationError) as exc_info:
        validate_and_build_review_decisions(
            df,
            batch_id="test_batch",
            expected_companies=["Company A", "Company B"],
        )

    assert "APPROVE requires ready_for_master_update=YES" in str(
        exc_info.value
    )


def test_validator_rejects_invalid_priority():
    df = _review_df()
    df.loc[df["company"].eq("Company A"), "reviewed_priority"] = "High"

    with pytest.raises(DecisionValidationError) as exc_info:
        validate_and_build_review_decisions(
            df,
            batch_id="test_batch",
            expected_companies=["Company A", "Company B"],
        )

    assert "must include P0, P1, P2, P3, or P4" in str(exc_info.value)


def test_workflow_creates_durable_decision_artifacts(tmp_path: Path):
    settings = load_settings(
        repo_dir=tmp_path / "repo",
        drive_root=tmp_path / "drive",
    )
    settings.ensure_directories()

    manifest = create_batch_manifest(
        batch_id="test_batch",
        companies=["Company A", "Company B"],
        batches_dir=settings.research_batches_dir,
    )
    manifest.state = BatchState.AWAITING_RECOMMENDATION_APPROVAL
    manifest.resume_from = "READ_REVIEW_DECISIONS"
    save_batch_manifest(manifest)

    worksheet = FakeWorksheet(
        "Review Packet",
        _worksheet_values(_review_df()),
    )
    result = read_review_decisions_to_master_gate(
        batch_id="test_batch",
        settings=settings,
        spreadsheet=FakeSpreadsheet(worksheet),
    )

    assert result.status == WorkflowStatus.SUCCESS
    assert result.state == BatchState.MASTER_UPDATE_READY
    assert result.resume_from == "UPDATE_MASTER"
    assert result.details["approved_count"] == 1
    assert result.details["held_count"] == 1
    assert Path(result.artifact_paths["validated_decisions"]).exists()
    assert Path(result.artifact_paths["approved_decisions"]).exists()

    approved_df = pd.read_csv(result.artifact_paths["approved_decisions"])
    assert approved_df["company"].tolist() == ["Company A"]

    updated = load_batch_manifest(manifest.artifacts.manifest_path)
    assert updated.state == BatchState.MASTER_UPDATE_READY
    assert updated.resume_from == "UPDATE_MASTER"
    assert updated.company_states["Company A"] == CompanyState.APPROVED.value
    assert updated.company_states["Company B"] == CompanyState.HELD.value


def test_workflow_stops_and_records_validation_errors(tmp_path: Path):
    settings = load_settings(
        repo_dir=tmp_path / "repo",
        drive_root=tmp_path / "drive",
    )
    settings.ensure_directories()

    manifest = create_batch_manifest(
        batch_id="test_batch",
        companies=["Company A", "Company B"],
        batches_dir=settings.research_batches_dir,
    )
    manifest.state = BatchState.AWAITING_RECOMMENDATION_APPROVAL
    save_batch_manifest(manifest)

    invalid_df = _review_df()
    invalid_df.loc[
        invalid_df["company"].eq("Company A"),
        "review_decision",
    ] = ""

    result = read_review_decisions_to_master_gate(
        batch_id="test_batch",
        settings=settings,
        spreadsheet=FakeSpreadsheet(
            FakeWorksheet("Review Packet", _worksheet_values(invalid_df))
        ),
    )

    assert result.status == WorkflowStatus.ERROR
    assert result.state == BatchState.ERROR_REQUIRES_REVIEW
    assert result.resume_from == "READ_REVIEW_DECISIONS"
    assert result.details["issues"]

    updated = load_batch_manifest(manifest.artifacts.manifest_path)
    assert updated.state == BatchState.ERROR_REQUIRES_REVIEW
    assert updated.error["issues"]
