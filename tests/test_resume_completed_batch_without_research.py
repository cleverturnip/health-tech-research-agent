from pathlib import Path
import json

import pandas as pd

from health_tech_research_agent.models import BatchState, WorkflowStatus
from health_tech_research_agent.settings import load_settings
from health_tech_research_agent.state import create_batch_manifest
from health_tech_research_agent.storage import atomic_write_csv
from health_tech_research_agent.workflow import run_research_to_review_gate


def _fit_brief(company: str) -> str:
    return json.dumps({
        "company": company,
        "verified_facts_with_sources": [],
        "inferences": [],
        "unverified_or_weak_claims": [],
        "business_model_classification": "B2B2C virtual care",
        "taxonomy_classification": {
            "primary_market_segment": "PRIMARY_LONGITUDINAL_CARE",
            "subsegment_tags": [],
            "product_model_tags": ["VIRTUAL_CARE"],
            "distribution_model_tags": ["B2B2C"],
            "data_input_tags": ["PATIENT_REPORTED"],
            "classification_rationale": "Test classification",
        },
        "commercial_scale_assessment": "Test",
        "pmf_scale_assessment": "Test",
        "role_timing_assessment": {
            "company_maturity_read": "early-growth",
            "likely_agency_level": "high",
            "stage_timing_fit": "ideal",
            "why_now_or_why_not": "Test",
            "timing_penalty_applied": False,
        },
        "scale_signal_assessment": {
            "commercial_scale_signal": "moderate",
            "institutional_distribution_signal": "strong",
            "outcomes_signal": "moderate",
            "scale_engine_type": "institutional",
            "plausible_near_term_scale_path": True,
        },
        "scores": {
            "thesis_fit_score": {"score": 80, "rationale": "Test"},
            "pmf_scale_score": {"score": 75, "rationale": "Test"},
            "evidence_confidence_score": {"score": 60, "rationale": "Test"},
            "katelynd_role_fit_score": {"score": 78, "rationale": "Test"},
            "operator_timing_score": {"score": 76, "rationale": "Test"},
        },
        "final_recommendation": "Possible fit, pending diligence",
        "priority_level": "P2: Worth deeper diligence",
        "calibration_flag": "",
        "final_takeaway": "Test",
    })


def test_resume_completed_batch_without_research(tmp_path: Path):
    settings = load_settings(
        repo_dir=tmp_path / "repo",
        drive_root=tmp_path / "drive",
    )
    settings.ensure_directories()

    companies = ["Company A", "Company B"]
    manifest = create_batch_manifest(
        batch_id="test_batch",
        companies=companies,
        batches_dir=settings.research_batches_dir,
    )

    checkpoint = pd.DataFrame([
        {
            "company": company,
            "date_researched": "2026-06-17",
            "funding_finding": "Funding",
            "payer_institutional_finding": "Distribution",
            "outcomes_finding": "Outcomes",
            "commercial_scale_finding": "Commercial",
            "growth_finding": "Growth",
            "paying_finding": "Paying",
            "org_events_finding": "Org events",
            "operating_characteristics_finding": "Operating characteristics",
            "fit_brief_json": _fit_brief(company),
        }
        for company in companies
    ])
    atomic_write_csv(
        manifest.artifacts.checkpoint_path,
        checkpoint,
    )

    result = run_research_to_review_gate(
        batch_id="test_batch",
        settings=settings,
        research_enabled=False,
    )

    assert result.status == WorkflowStatus.SUCCESS
    assert result.state == BatchState.REVIEW_PACKET_READY
    assert result.companies_researched == 0
    assert result.companies_reused == 2
    assert Path(result.artifact_paths["review_packet"]).exists()
    assert Path(result.artifact_paths["summary"]).exists()
