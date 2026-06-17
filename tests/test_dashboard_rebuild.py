"""Regression tests for the package-level dashboard rebuild (Section 3).

Covers the state machine and the read-back validation gate:
- happy path rebuilds from the verified master and advances to COMPLETE, with a
  completion report carrying the calibration and override-reconciliation figures;
- the two blocking field-level checks have teeth: an injected surviving stale
  flag and an injected override-segment mismatch each force ERROR_REQUIRES_REVIEW
  and do NOT mark the batch COMPLETE;
- on failure the master file and the prior workbook are byte-for-byte untouched;
- the entrypoint refuses to run from a wrong state.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd

from health_tech_research_agent.models import BatchState, WorkflowStatus
from health_tech_research_agent.priority import safe_text
from health_tech_research_agent.settings import Settings
from health_tech_research_agent.state import (
    create_batch_manifest,
    load_batch_manifest,
    save_batch_manifest,
)
from health_tech_research_agent.storage import load_workbook_sheets
from health_tech_research_agent.workflow import run_dashboard_refresh

REPO_TAXONOMY = Path(__file__).resolve().parents[1] / "taxonomy"
BATCH_ID = "dashboard_rebuild_test_batch"


def _settings(tmp_path):
    drive = tmp_path / "drive"
    batches = drive / "research_batches"
    repo = tmp_path / "repo"
    for directory in (drive, batches, repo):
        directory.mkdir(parents=True, exist_ok=True)
    return Settings(
        repo_dir=repo,
        drive_root=drive,
        research_batches_dir=batches,
        master_path=drive / "health_tech_master.csv",
        raw_archive_path=drive / "raw_archive.csv",
        batch_control_sheet_url="https://example.test/sheet",
    )


def _write_master(settings):
    # Function Health: human-reviewed up to P0 -> its stored P2 flag is now stale.
    # Levels Health: still P2 with low evidence -> flag still valid.
    # Mental Co: model-segmented, P1, clean.
    df = pd.DataFrame([
        {
            "company": "Function Health",
            "priority_level": "P2: Worth deeper diligence",
            "reviewed_priority_level": "P0: Highest-priority target",
            "primary_market_segment": "",
            "evidence_confidence_score": 40,
            "pmf_scale_score": 85,
            "business_model_classification": "B2B2C payer-contracted",
            "calibration_flag": "CHECK: P2 with low evidence",
        },
        {
            "company": "Levels Health",
            "priority_level": "P2: Worth deeper diligence",
            "reviewed_priority_level": "",
            "primary_market_segment": "",
            "evidence_confidence_score": 40,
            "pmf_scale_score": 85,
            "business_model_classification": "B2B2C payer-contracted",
            "calibration_flag": "CHECK: P2 with low evidence",
        },
        {
            "company": "Mental Co",
            "priority_level": "P1: Near-priority target",
            "reviewed_priority_level": "",
            "primary_market_segment": "MENTAL_BEHAVIORAL_HEALTH",
            "evidence_confidence_score": 80,
            "pmf_scale_score": 85,
            "business_model_classification": "B2B2C payer-contracted",
            "calibration_flag": "",
        },
    ])
    df.to_csv(settings.master_path, index=False)
    return df


def _ready_manifest(settings):
    manifest = create_batch_manifest(
        batch_id=BATCH_ID,
        companies=["Function Health", "Levels Health", "Mental Co"],
        batches_dir=settings.research_batches_dir,
    )
    manifest.state = BatchState.DASHBOARD_REFRESH_READY
    manifest.resume_from = "REFRESH_DASHBOARD"
    save_batch_manifest(manifest)
    return manifest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(settings, **kwargs):
    return run_dashboard_refresh(
        batch_id=BATCH_ID,
        settings=settings,
        taxonomy_dir=REPO_TAXONOMY,
        **kwargs,
    )


# Fault-injection hooks (simulate a build/write path that let a defect through).

def _inject_stale_flag(df):
    out = df.copy()
    # Function Health is P0 now, so the recompute cleared its flag. Force a
    # stale P2 flag back onto it to simulate a surviving stale flag.
    out.loc[out["company"] == "Function Health", "calibration_flag"] = "CHECK: P2 with low evidence"
    return out


def _inject_override_mismatch(df):
    out = df.copy()
    # Function Health's human override is CONSUMER_HEALTH_OPTIMIZATION; force a
    # conflicting model segment to simulate the override being ignored.
    out.loc[out["company"] == "Function Health", "primary_market_segment_code"] = "DIAGNOSTICS_LIFE_SCIENCES"
    return out


# ---------------------------------------------------------------------------
# Happy path.
# ---------------------------------------------------------------------------

def test_happy_path_rebuild_advances_to_complete(tmp_path):
    settings = _settings(tmp_path)
    _write_master(settings)
    _ready_manifest(settings)

    result = _run(settings)

    assert result.status == WorkflowStatus.SUCCESS
    assert result.state == BatchState.COMPLETE

    manifest = load_batch_manifest(settings.research_batches_dir / f"{BATCH_ID}_manifest.json")
    assert manifest.state == BatchState.COMPLETE
    assert manifest.resume_from == ""
    assert manifest.artifacts.dashboard_path
    assert manifest.artifacts.completion_report_path

    # The dashboard workbook exists and contains every expected sheet.
    workbook = Path(manifest.artifacts.dashboard_path)
    assert workbook.exists()
    sheets = load_workbook_sheets(workbook)
    for sheet in ["Master Dashboard", "Priority Summary", "Segment Summary", "Calibration Review"]:
        assert sheet in sheets

    md = sheets["Master Dashboard"]
    assert set(md["company"]) == {"Function Health", "Levels Health", "Mental Co"}

    fh = md[md["company"] == "Function Health"].iloc[0]
    assert safe_text(fh["calibration_flag"]) == ""  # stale P2 flag cleared at P0
    assert safe_text(fh["primary_market_segment_code"]) == "CONSUMER_HEALTH_OPTIMIZATION"  # override honored


def test_completion_report_records_figures(tmp_path):
    settings = _settings(tmp_path)
    _write_master(settings)
    _ready_manifest(settings)

    _run(settings)

    report_path = settings.research_batches_dir / f"{BATCH_ID}_dashboard_completion_report.json"
    report = json.loads(report_path.read_text())

    assert report["status"] == "COMPLETE"
    assert report["validation"]["passed"] is True
    assert report["validation"]["issue_count"] == 0
    # Function Health's stale flag was cleared by the recompute.
    assert report["calibration_changes"]["flags_cleared"] == 1
    # Both override companies present (Function Health, Levels Health) matched.
    assert report["override_reconciliation"]["checked"] == 2
    assert report["override_reconciliation"]["matched"] == 2
    assert report["override_reconciliation"]["mismatch_count"] == 0


# ---------------------------------------------------------------------------
# The gate has teeth: injected defects force ERROR and never reach COMPLETE.
# ---------------------------------------------------------------------------

def test_injected_stale_flag_forces_error_not_complete(tmp_path):
    settings = _settings(tmp_path)
    _write_master(settings)
    _ready_manifest(settings)

    result = _run(settings, frame_hook=_inject_stale_flag)

    assert result.status == WorkflowStatus.ERROR
    assert result.state == BatchState.ERROR_REQUIRES_REVIEW

    manifest = load_batch_manifest(settings.research_batches_dir / f"{BATCH_ID}_manifest.json")
    assert manifest.state == BatchState.ERROR_REQUIRES_REVIEW
    assert manifest.state != BatchState.COMPLETE
    assert manifest.resume_from == "REFRESH_DASHBOARD"

    checks = {issue["check"] for issue in manifest.error["issues"]}
    assert "stale_calibration_flag" in checks

    # The final dashboard was never promoted into place.
    assert not (settings.drive_root / "health_tech_market_dashboard.xlsx").exists()


def test_injected_override_mismatch_forces_error_not_complete(tmp_path):
    settings = _settings(tmp_path)
    _write_master(settings)
    _ready_manifest(settings)

    result = _run(settings, frame_hook=_inject_override_mismatch)

    assert result.status == WorkflowStatus.ERROR
    assert result.state == BatchState.ERROR_REQUIRES_REVIEW

    manifest = load_batch_manifest(settings.research_batches_dir / f"{BATCH_ID}_manifest.json")
    assert manifest.state == BatchState.ERROR_REQUIRES_REVIEW
    assert manifest.state != BatchState.COMPLETE

    issues = manifest.error["issues"]
    mismatch = [i for i in issues if i["check"] == "override_segment_mismatch"]
    assert mismatch
    assert mismatch[0]["company"] == "Function Health"
    assert mismatch[0]["expected_segment"] == "CONSUMER_HEALTH_OPTIMIZATION"


# ---------------------------------------------------------------------------
# On failure, the master and prior workbook are byte-for-byte untouched.
# ---------------------------------------------------------------------------

def test_master_and_prior_workbook_untouched_on_failure(tmp_path):
    settings = _settings(tmp_path)
    _write_master(settings)
    _ready_manifest(settings)

    # A prior dashboard already exists at the final path.
    prior_dashboard = settings.drive_root / "health_tech_market_dashboard.xlsx"
    prior_dashboard.write_bytes(b"PRIOR-DASHBOARD-SENTINEL")

    master_digest_before = _sha256(settings.master_path)
    prior_digest_before = _sha256(prior_dashboard)

    result = _run(settings, frame_hook=_inject_stale_flag)

    assert result.state == BatchState.ERROR_REQUIRES_REVIEW
    assert _sha256(settings.master_path) == master_digest_before
    assert _sha256(prior_dashboard) == prior_digest_before


# ---------------------------------------------------------------------------
# State guard.
# ---------------------------------------------------------------------------

def test_refuses_to_run_from_wrong_state(tmp_path):
    settings = _settings(tmp_path)
    _write_master(settings)
    # Manifest left in CREATED (not a valid resume point for the rebuild).
    create_batch_manifest(
        batch_id=BATCH_ID,
        companies=["Function Health"],
        batches_dir=settings.research_batches_dir,
    )

    result = _run(settings)

    assert result.status == WorkflowStatus.ERROR
    manifest = load_batch_manifest(settings.research_batches_dir / f"{BATCH_ID}_manifest.json")
    assert manifest.state == BatchState.CREATED  # unchanged; guard returned before doing work
