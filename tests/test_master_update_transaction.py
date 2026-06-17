from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from health_tech_research_agent.master_update import (
    MasterUpdateError,
    build_proposed_master,
    execute_master_update_transaction,
    validate_master_readback,
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
from health_tech_research_agent.storage import atomic_write_csv
from health_tech_research_agent.workflow import update_master_transactionally


def priority_applier(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["final_priority_level"] = out["reviewed_priority_level"].where(
        out["reviewed_priority_level"].fillna("").astype(str).str.strip().ne(""),
        out["priority_level"],
    )
    out["priority_source"] = "Human Reviewed"
    out["final_priority_code"] = out["final_priority_level"].str.extract(
        r"\b(P[0-4])\b", expand=False
    )
    out["final_priority_rank"] = out["final_priority_code"].map(
        {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
    )
    return out


def master_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "company": "company a",
            "priority_level": "P3: Watch list",
            "reviewed_priority_level": "P2: Worth deeper diligence",
            "review_status": "Human reviewed",
            "review_notes": "Approved A",
            "priority_review_note": "Approved A",
            "primary_market_segment_code": "PRIMARY_LONGITUDINAL_CARE",
            "subsegment_tags": "",
            "final_priority_level": "P2: Worth deeper diligence",
            "priority_source": "Human Reviewed",
            "final_priority_code": "P2",
            "final_priority_rank": 2,
            "final_priority_patch_batch": "test_batch",
            "final_priority_patch_updated_at": "2026-06-17T00:00:00+00:00",
        }
    ])


def summary_df(*, taxonomy="PRIMARY_LONGITUDINAL_CARE") -> pd.DataFrame:
    return pd.DataFrame([
        {
            "company": "Company A",
            "priority_level": "P3: Watch list",
            "primary_market_segment_code": taxonomy,
            "subsegment_tags": "virtual_care",
        }
    ])


def approved_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "batch_id": "test_batch",
            "company": "Company A",
            "reviewed_priority_level": "P2: Worth deeper diligence",
            "review_status": "Human reviewed",
            "review_notes": "Approved A",
            "priority_review_note": "Approved A",
        }
    ])


def test_build_proposal_preserves_model_priority_and_applies_human_final_priority():
    proposed, changes, counts = build_proposed_master(
        master_df=master_df(),
        summary_df=summary_df(),
        approved_df=approved_df(),
        batch_id="test_batch",
        priority_applier=priority_applier,
        updated_at="2026-06-18T00:00:00+00:00",
    )
    row = proposed.iloc[0]
    assert row["priority_level"] == "P3: Watch list"
    assert row["reviewed_priority_level"] == "P2: Worth deeper diligence"
    assert row["final_priority_level"] == "P2: Worth deeper diligence"
    assert row["final_priority_code"] == "P2"
    assert row["subsegment_tags"] == "virtual_care"
    assert counts == {"inserted_count": 0, "updated_count": 1, "unchanged_count": 0}
    assert not changes.empty


def test_build_proposal_inserts_new_company():
    current = master_df()
    summary = pd.concat([
        summary_df(),
        pd.DataFrame([{
            "company": "Company B",
            "priority_level": "P2: Worth deeper diligence",
            "primary_market_segment_code": "CARE_NAVIGATION_ACCESS",
            "subsegment_tags": "navigation",
        }]),
    ], ignore_index=True)
    approved = pd.concat([
        approved_df(),
        pd.DataFrame([{
            "batch_id": "test_batch",
            "company": "Company B",
            "reviewed_priority_level": "P3: Watch list",
            "review_status": "Human reviewed",
            "review_notes": "Approved B",
            "priority_review_note": "Approved B",
        }]),
    ], ignore_index=True)
    proposed, changes, counts = build_proposed_master(
        master_df=current,
        summary_df=summary,
        approved_df=approved,
        batch_id="test_batch",
        priority_applier=priority_applier,
    )
    assert len(proposed) == 2
    row = proposed.loc[proposed["company"].eq("Company B")].iloc[0]
    assert row["priority_level"] == "P2: Worth deeper diligence"
    assert row["reviewed_priority_level"] == "P3: Watch list"
    assert row["final_priority_code"] == "P3"
    assert counts["inserted_count"] == 1
    assert set(changes["action"]) >= {"INSERT"}


def test_duplicate_master_stops_before_proposal():
    duplicated = pd.concat([master_df(), master_df()], ignore_index=True)
    with pytest.raises(MasterUpdateError, match="duplicate companies"):
        build_proposed_master(
            master_df=duplicated,
            summary_df=summary_df(),
            approved_df=approved_df(),
            batch_id="test_batch",
            priority_applier=priority_applier,
        )


def test_missing_summary_stops_before_write():
    with pytest.raises(MasterUpdateError, match="missing from summary"):
        build_proposed_master(
            master_df=master_df(),
            summary_df=pd.DataFrame([{
                "company": "Other",
                "primary_market_segment_code": "OTHER_REVIEW",
            }]),
            approved_df=approved_df(),
            batch_id="test_batch",
            priority_applier=priority_applier,
        )


def test_blank_taxonomy_stops_before_write():
    current = master_df()
    current["primary_market_segment_code"] = ""
    with pytest.raises(MasterUpdateError, match="blank primary_market_segment_code"):
        build_proposed_master(
            master_df=current,
            summary_df=summary_df(taxonomy=""),
            approved_df=approved_df(),
            batch_id="test_batch",
            priority_applier=priority_applier,
        )


def test_transaction_noop_when_master_already_matches(tmp_path: Path):
    master = master_df()
    # Match summary too, so no controlled fields differ.
    master["subsegment_tags"] = "virtual_care"
    master_path = tmp_path / "master.csv"
    summary_path = tmp_path / "summary.csv"
    approved_path = tmp_path / "approved.csv"
    atomic_write_csv(master_path, master)
    atomic_write_csv(summary_path, summary_df())
    atomic_write_csv(approved_path, approved_df())

    result = execute_master_update_transaction(
        master_path=master_path,
        summary_path=summary_path,
        approved_path=approved_path,
        batch_id="test_batch",
        artifacts_dir=tmp_path,
        priority_applier=priority_applier,
    )
    assert result.write_performed is False
    assert result.unchanged_count == 1
    assert result.change_log_df.empty
    assert result.backup_path == ""
    assert Path(result.readback_path).exists()


def test_transaction_writes_backup_and_verifies(tmp_path: Path):
    master_path = tmp_path / "master.csv"
    summary_path = tmp_path / "summary.csv"
    approved_path = tmp_path / "approved.csv"
    atomic_write_csv(master_path, master_df())
    atomic_write_csv(summary_path, summary_df())
    atomic_write_csv(approved_path, approved_df())

    result = execute_master_update_transaction(
        master_path=master_path,
        summary_path=summary_path,
        approved_path=approved_path,
        batch_id="test_batch",
        artifacts_dir=tmp_path,
        priority_applier=priority_applier,
    )
    assert result.write_performed is True
    assert Path(result.backup_path).exists()
    assert Path(result.readback_path).exists()
    assert Path(result.change_log_path).exists()
    readback = pd.read_csv(master_path)
    assert readback.iloc[0]["subsegment_tags"] == "virtual_care"


def test_transaction_rolls_back_on_readback_mismatch(tmp_path: Path):
    master_path = tmp_path / "master.csv"
    summary_path = tmp_path / "summary.csv"
    approved_path = tmp_path / "approved.csv"
    original = master_df()
    atomic_write_csv(master_path, original)
    atomic_write_csv(summary_path, summary_df())
    atomic_write_csv(approved_path, approved_df())

    calls = {"master_writes": 0}
    def corrupting_writer(path, df):
        path = Path(path)
        if path == master_path:
            calls["master_writes"] += 1
            corrupt = df.copy()
            corrupt.loc[0, "company"] = "CORRUPTED"
            return atomic_write_csv(path, corrupt)
        return atomic_write_csv(path, df)

    with pytest.raises(MasterUpdateError) as exc_info:
        execute_master_update_transaction(
            master_path=master_path,
            summary_path=summary_path,
            approved_path=approved_path,
            batch_id="test_batch",
            artifacts_dir=tmp_path,
            priority_applier=priority_applier,
            writer=corrupting_writer,
        )
    assert exc_info.value.details["rollback_performed"] is True
    restored = pd.read_csv(master_path)
    pd.testing.assert_frame_equal(
        restored.fillna(""), original.fillna(""), check_dtype=False
    )


def test_workflow_advances_manifest_after_transaction(tmp_path: Path):
    settings = load_settings(repo_dir=tmp_path / "repo", drive_root=tmp_path / "drive")
    settings.ensure_directories()
    manifest = create_batch_manifest(
        batch_id="test_batch",
        companies=["Company A"],
        batches_dir=settings.research_batches_dir,
    )
    manifest.state = BatchState.MASTER_UPDATE_READY
    manifest.resume_from = "UPDATE_MASTER"
    manifest.company_states["Company A"] = CompanyState.APPROVED.value
    save_batch_manifest(manifest)
    atomic_write_csv(manifest.artifacts.summary_path, summary_df())
    atomic_write_csv(manifest.artifacts.approved_decisions_path, approved_df())
    atomic_write_csv(settings.master_path, master_df())

    result = update_master_transactionally(
        batch_id="test_batch",
        settings=settings,
        priority_applier=priority_applier,
    )
    assert result.status == WorkflowStatus.SUCCESS
    assert result.state == BatchState.DASHBOARD_REFRESH_READY
    assert result.resume_from == "REFRESH_DASHBOARD"
    updated = load_batch_manifest(manifest.artifacts.manifest_path)
    assert updated.company_states["Company A"] == CompanyState.COMMITTED.value
    assert Path(result.artifact_paths["master_backup"]).exists()


def test_workflow_noop_still_advances_manifest(tmp_path: Path):
    settings = load_settings(repo_dir=tmp_path / "repo", drive_root=tmp_path / "drive")
    settings.ensure_directories()
    manifest = create_batch_manifest(
        batch_id="test_batch",
        companies=["Company A"],
        batches_dir=settings.research_batches_dir,
    )
    manifest.state = BatchState.MASTER_UPDATE_READY
    manifest.company_states["Company A"] = CompanyState.APPROVED.value
    save_batch_manifest(manifest)
    current = master_df()
    current["subsegment_tags"] = "virtual_care"
    atomic_write_csv(manifest.artifacts.summary_path, summary_df())
    atomic_write_csv(manifest.artifacts.approved_decisions_path, approved_df())
    atomic_write_csv(settings.master_path, current)

    result = update_master_transactionally(
        batch_id="test_batch",
        settings=settings,
        priority_applier=priority_applier,
    )
    assert result.status == WorkflowStatus.NOOP
    assert result.state == BatchState.DASHBOARD_REFRESH_READY
    assert result.details["write_performed"] is False


def test_existing_human_taxonomy_override_wins_over_summary():
    current = master_df()
    current["taxonomy_assignment_method"] = "human_override"
    current["taxonomy_assignment_basis"] = "Reviewed by human"
    current["primary_market_segment_code"] = "PRIMARY_LONGITUDINAL_CARE"
    current["subsegment_tags"] = "human_tag"

    summary = summary_df(taxonomy="CARE_NAVIGATION_ACCESS")
    summary["taxonomy_assignment_method"] = "llm_fit_brief"
    summary["taxonomy_assignment_basis"] = "Model classification"
    summary["subsegment_tags"] = "model_tag"

    proposed, changes, counts = build_proposed_master(
        master_df=current,
        summary_df=summary,
        approved_df=approved_df(),
        batch_id="test_batch",
        priority_applier=priority_applier,
        updated_at="2026-06-18T00:00:00+00:00",
    )

    row = proposed.iloc[0]
    assert row["primary_market_segment_code"] == "PRIMARY_LONGITUDINAL_CARE"
    assert row["taxonomy_assignment_method"] == "human_override"
    assert row["taxonomy_assignment_basis"] == "Reviewed by human"
    assert row["subsegment_tags"] == "human_tag"

    taxonomy_fields = {
        "primary_market_segment_code",
        "taxonomy_assignment_method",
        "taxonomy_assignment_basis",
        "subsegment_tags",
    }
    changed_fields = set(changes["field"]) if not changes.empty else set()
    assert changed_fields.isdisjoint(taxonomy_fields)


def test_non_human_taxonomy_can_be_refreshed_from_summary():
    current = master_df()
    current["taxonomy_assignment_method"] = "llm_fit_brief"
    current["taxonomy_assignment_basis"] = "Old model classification"

    summary = summary_df(taxonomy="CARE_NAVIGATION_ACCESS")
    summary["taxonomy_assignment_method"] = "llm_fit_brief"
    summary["taxonomy_assignment_basis"] = "New model classification"

    proposed, _, _ = build_proposed_master(
        master_df=current,
        summary_df=summary,
        approved_df=approved_df(),
        batch_id="test_batch",
        priority_applier=priority_applier,
    )

    row = proposed.iloc[0]
    assert row["primary_market_segment_code"] == "CARE_NAVIGATION_ACCESS"
    assert row["taxonomy_assignment_basis"] == "New model classification"


def test_readback_accepts_integer_to_float_csv_roundtrip():
    proposed = pd.DataFrame({
        "company": ["Company A", "Company B"],
        "final_priority_rank": [2, ""],
        "final_priority_code": ["P2", ""],
    })
    readback = pd.DataFrame({
        "company": ["Company A", "Company B"],
        "final_priority_rank": [2.0, float("nan")],
        "final_priority_code": ["P2", float("nan")],
    })

    validate_master_readback(
        proposed_df=proposed,
        readback_df=readback,
        approved_companies=["Company A"],
    )


def test_readback_still_rejects_real_content_mismatch():
    proposed = pd.DataFrame({
        "company": ["Company A"],
        "final_priority_rank": [2],
    })
    readback = pd.DataFrame({
        "company": ["Company A"],
        "final_priority_rank": [3.0],
    })

    with pytest.raises(MasterUpdateError, match="content does not match"):
        validate_master_readback(
            proposed_df=proposed,
            readback_df=readback,
            approved_companies=["Company A"],
        )
