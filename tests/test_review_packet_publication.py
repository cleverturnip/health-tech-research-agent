from pathlib import Path
import json

import pandas as pd

from health_tech_research_agent.google_sheets import (
    publish_review_packet,
)
from health_tech_research_agent.models import BatchState, WorkflowStatus
from health_tech_research_agent.settings import load_settings
from health_tech_research_agent.state import create_batch_manifest, load_batch_manifest
from health_tech_research_agent.storage import atomic_write_csv
from health_tech_research_agent.workflow import publish_review_packet_to_sheet


class FakeWorksheet:
    def __init__(self, title: str, values=None):
        self.title = title
        self.values = values or []
        self.clear_calls = 0
        self.update_calls = 0

    def get_all_values(self):
        return [list(row) for row in self.values]

    def clear(self):
        self.clear_calls += 1
        self.values = []

    def update(self, *, values, range_name):
        self.update_calls += 1
        assert range_name == "A1"
        self.values = [list(row) for row in values]


class CorruptingWorksheet(FakeWorksheet):
    def update(self, *, values, range_name):
        super().update(values=values, range_name=range_name)
        if len(self.values) > 2:
            self.values.pop()


class FakeSpreadsheet:
    def __init__(self, worksheet):
        self._worksheet = worksheet

    def worksheet(self, title):
        assert title == self._worksheet.title
        return self._worksheet


def _packet(batch_id: str):
    return pd.DataFrame([
        {
            "batch_id": batch_id,
            "company": "Company A",
            "priority_level": "P2: Worth deeper diligence",
            "review_decision": "",
            "reviewed_priority": "",
            "review_notes": "",
            "ready_for_master_update": "",
            "reviewed_at": "",
            "step_22_status": "",
        },
        {
            "batch_id": batch_id,
            "company": "Company B",
            "priority_level": "P3: Watch list",
            "review_decision": "",
            "reviewed_priority": "",
            "review_notes": "",
            "ready_for_master_update": "",
            "reviewed_at": "",
            "step_22_status": "",
        },
    ])


def test_publish_review_packet_validates_readback():
    worksheet = FakeWorksheet("Review Packet")
    spreadsheet = FakeSpreadsheet(worksheet)

    result = publish_review_packet(
        spreadsheet,
        _packet("test_batch"),
        batch_id="test_batch",
        expected_companies=["Company A", "Company B"],
        required_columns=[
            "batch_name",
            "batch_id",
            "company",
            "review_decision",
        ],
    )

    assert result.row_count == 2
    assert result.company_count == 2
    assert result.companies == ["Company A", "Company B"]


def test_workflow_publication_updates_manifest_and_saves_readback(tmp_path: Path):
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
    manifest.state = BatchState.REVIEW_PACKET_READY
    from health_tech_research_agent.state import save_batch_manifest
    save_batch_manifest(manifest)
    atomic_write_csv(manifest.artifacts.review_packet_path, _packet("test_batch"))

    previous_values = [
        ["batch_name", "company"],
        ["old_batch", "Old Company"],
    ]
    spreadsheet = FakeSpreadsheet(FakeWorksheet("Review Packet", previous_values))

    result = publish_review_packet_to_sheet(
        batch_id="test_batch",
        settings=settings,
        spreadsheet=spreadsheet,
    )

    assert result.status == WorkflowStatus.SUCCESS
    assert result.state == BatchState.AWAITING_RECOMMENDATION_APPROVAL
    assert result.resume_from == "READ_REVIEW_DECISIONS"
    assert Path(result.artifact_paths["sheet_backup"]).exists()
    assert Path(result.artifact_paths["sheet_readback"]).exists()

    updated_manifest = load_batch_manifest(manifest.artifacts.manifest_path)
    assert updated_manifest.state == BatchState.AWAITING_RECOMMENDATION_APPROVAL


def test_workflow_publication_detects_company_mismatch(tmp_path: Path):
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
    manifest.state = BatchState.REVIEW_PACKET_READY
    from health_tech_research_agent.state import save_batch_manifest
    save_batch_manifest(manifest)
    atomic_write_csv(manifest.artifacts.review_packet_path, _packet("test_batch"))

    spreadsheet = FakeSpreadsheet(CorruptingWorksheet("Review Packet"))
    result = publish_review_packet_to_sheet(
        batch_id="test_batch",
        settings=settings,
        spreadsheet=spreadsheet,
    )

    assert result.status == WorkflowStatus.ERROR
    assert result.state == BatchState.ERROR_REQUIRES_REVIEW
    assert result.resume_from == "PUBLISH_REVIEW_PACKET"


def test_workflow_adopts_matching_existing_sheet_without_overwrite(tmp_path: Path):
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
    manifest.state = BatchState.REVIEW_PACKET_READY
    from health_tech_research_agent.state import save_batch_manifest
    save_batch_manifest(manifest)
    atomic_write_csv(manifest.artifacts.review_packet_path, _packet("test_batch"))

    existing_values = [
        [
            "batch_name",
            "company",
            "priority_level",
            "review_decision",
            "reviewed_priority",
            "review_notes",
            "ready_for_master_update",
            "reviewed_at",
            "step_22_status",
        ],
        [
            "test_batch",
            "Company A",
            "P2: Worth deeper diligence",
            "Approve",
            "P2",
            "Human decision A",
            "TRUE",
            "2026-06-17",
            "",
        ],
        [
            "test_batch",
            "Company B",
            "P3: Watch list",
            "Hold",
            "P3",
            "Human decision B",
            "FALSE",
            "2026-06-17",
            "",
        ],
    ]

    worksheet = FakeWorksheet("Review Packet", existing_values)
    spreadsheet = FakeSpreadsheet(worksheet)

    result = publish_review_packet_to_sheet(
        batch_id="test_batch",
        settings=settings,
        spreadsheet=spreadsheet,
    )

    assert result.status == WorkflowStatus.NOOP
    assert result.state == BatchState.AWAITING_RECOMMENDATION_APPROVAL
    assert result.details["publication_mode"] == "validated_existing"
    assert result.details["sheet_write_performed"] is False
    assert worksheet.clear_calls == 0
    assert worksheet.update_calls == 0
    assert worksheet.values == existing_values
    assert Path(result.artifact_paths["sheet_readback"]).exists()

    updated_manifest = load_batch_manifest(manifest.artifacts.manifest_path)
    assert updated_manifest.state == BatchState.AWAITING_RECOMMENDATION_APPROVAL
    assert updated_manifest.resume_from == "READ_REVIEW_DECISIONS"
