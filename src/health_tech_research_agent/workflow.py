from __future__ import annotations

from pathlib import Path

from .models import (
    BatchManifest,
    BatchState,
    CompanyState,
    WorkflowResult,
    WorkflowStatus,
)
from .review import (
    build_review_packet,
    build_summary,
    validate_completed_research,
    write_review_packet,
)
from .settings import Settings
from .state import load_batch_manifest, save_batch_manifest
from .storage import atomic_write_csv, load_csv


def restore_completed_batch(
    *,
    batch_id: str,
    settings: Settings,
    manifest_path: str | Path | None = None,
) -> tuple[BatchManifest, object]:
    resolved_manifest_path = Path(
        manifest_path
        or settings.research_batches_dir / f"{batch_id}_manifest.json"
    )

    if not resolved_manifest_path.exists():
        raise FileNotFoundError(
            f"Batch manifest not found: {resolved_manifest_path}"
        )

    manifest = load_batch_manifest(resolved_manifest_path)
    checkpoint_path = Path(manifest.artifacts.checkpoint_path)

    if not checkpoint_path.exists():
        fallback = (
            settings.research_batches_dir
            / f"{batch_id}_checkpoint.csv"
        )
        if fallback.exists():
            checkpoint_path = fallback
            manifest.artifacts.checkpoint_path = str(fallback)
        else:
            raise FileNotFoundError(
                f"Checkpoint not found for batch {batch_id}. "
                f"Checked {manifest.artifacts.checkpoint_path} and {fallback}."
            )

    checkpoint_df = load_csv(checkpoint_path)

    issues = validate_completed_research(
        checkpoint_df,
        expected_companies=manifest.companies,
    )
    if issues:
        manifest.state = BatchState.ERROR_REQUIRES_REVIEW
        manifest.resume_from = "VALIDATE_COMPLETED_RESEARCH"
        manifest.error = {
            "message": "Completed research validation failed.",
            "issues": issues,
        }
        save_batch_manifest(manifest)
        raise RuntimeError(
            "Completed research validation failed: "
            + "; ".join(
                f"{item['company']}: {item['issue']}"
                for item in issues
            )
        )

    for company in manifest.companies:
        manifest.set_company_state(
            company,
            CompanyState.RESEARCH_COMPLETE,
        )

    manifest.state = BatchState.RESEARCH_COMPLETE
    manifest.last_successful_step = "VALIDATE_COMPLETED_RESEARCH"
    manifest.resume_from = "BUILD_REVIEW_PACKET"
    manifest.error = None
    save_batch_manifest(manifest)

    return manifest, checkpoint_df


def run_research_to_review_gate(
    *,
    batch_id: str,
    settings: Settings,
    research_enabled: bool = False,
    manifest_path: str | Path | None = None,
) -> WorkflowResult:
    try:
        manifest, checkpoint_df = restore_completed_batch(
            batch_id=batch_id,
            settings=settings,
            manifest_path=manifest_path,
        )
    except Exception as exc:
        return WorkflowResult.error(
            batch_id=batch_id,
            state=BatchState.ERROR_REQUIRES_REVIEW,
            message=str(exc),
            resume_from="RESTORE_COMPLETED_BATCH",
        )

    if research_enabled:
        return WorkflowResult.error(
            batch_id=batch_id,
            state=BatchState.ERROR_REQUIRES_REVIEW,
            message=(
                "Research execution is intentionally not implemented in "
                "stabilization milestone 1."
            ),
            resume_from="RESEARCH_BATCH",
        )

    try:
        summary_df = build_summary(checkpoint_df)
        packet_df = build_review_packet(
            summary_df,
            batch_id=batch_id,
        )

        atomic_write_csv(
            manifest.artifacts.summary_path,
            summary_df,
        )
        write_review_packet(
            packet_df,
            output_path=manifest.artifacts.review_packet_path,
        )

        for company in manifest.companies:
            manifest.set_company_state(
                company,
                CompanyState.REVIEW_READY,
            )

        manifest.state = BatchState.REVIEW_PACKET_READY
        manifest.last_successful_step = "BUILD_REVIEW_PACKET"
        manifest.resume_from = "PUBLISH_REVIEW_PACKET"
        manifest.error = None
        save_batch_manifest(manifest)

        return WorkflowResult(
            status=WorkflowStatus.SUCCESS,
            batch_id=batch_id,
            state=manifest.state,
            message=(
                "Completed research restored and review packet created "
                "without rerunning research."
            ),
            companies_researched=0,
            companies_reused=len(manifest.companies),
            persistent_data_changed=True,
            resume_from=manifest.resume_from,
            artifact_paths={
                "checkpoint": manifest.artifacts.checkpoint_path,
                "summary": manifest.artifacts.summary_path,
                "review_packet": manifest.artifacts.review_packet_path,
                "manifest": manifest.artifacts.manifest_path,
            },
        )

    except Exception as exc:
        manifest.state = BatchState.ERROR_REQUIRES_REVIEW
        manifest.resume_from = "BUILD_REVIEW_PACKET"
        manifest.error = {
            "message": str(exc),
        }
        save_batch_manifest(manifest)

        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=str(exc),
            resume_from=manifest.resume_from,
        )
