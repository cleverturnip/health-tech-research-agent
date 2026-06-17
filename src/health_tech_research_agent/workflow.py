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


def publish_review_packet_to_sheet(
    *,
    batch_id: str,
    settings: Settings,
    spreadsheet: object,
    manifest_path: str | Path | None = None,
) -> WorkflowResult:
    from datetime import datetime, timezone

    from .google_sheets import (
        dataframe_from_worksheet,
        publish_review_packet,
        validate_review_packet_readback,
    )
    from .storage import atomic_write_csv

    resolved_manifest_path = Path(
        manifest_path
        or settings.research_batches_dir / f"{batch_id}_manifest.json"
    )

    try:
        manifest = load_batch_manifest(resolved_manifest_path)
    except Exception as exc:
        return WorkflowResult.error(
            batch_id=batch_id,
            state=BatchState.ERROR_REQUIRES_REVIEW,
            message=f"Could not load batch manifest: {exc}",
            resume_from="PUBLISH_REVIEW_PACKET",
        )

    if manifest.state not in {
        BatchState.REVIEW_PACKET_READY,
        BatchState.ERROR_REQUIRES_REVIEW,
    }:
        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=(
                "Review packet cannot be published from state "
                f"{manifest.state.value}. Expected REVIEW_PACKET_READY."
            ),
            resume_from="PUBLISH_REVIEW_PACKET",
        )

    packet_path = Path(manifest.artifacts.review_packet_path)
    if not packet_path.exists():
        manifest.state = BatchState.ERROR_REQUIRES_REVIEW
        manifest.resume_from = "BUILD_REVIEW_PACKET"
        manifest.error = {
            "message": f"Review packet file not found: {packet_path}"
        }
        save_batch_manifest(manifest)
        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=manifest.error["message"],
            resume_from=manifest.resume_from,
        )

    try:
        packet_df = load_csv(packet_path)
        review_ws = spreadsheet.worksheet(settings.review_packet_tab)
        existing_df = dataframe_from_worksheet(review_ws)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        required_review_columns = [
            "company",
            "review_decision",
            "reviewed_priority",
            "review_notes",
            "ready_for_master_update",
            "reviewed_at",
            "step_22_status",
        ]

        # Idempotent path:
        # If the live sheet already contains the correct batch and exact company set,
        # preserve it as-is. This protects completed human review decisions from being
        # erased by a regenerated packet with blank review fields.
        if not existing_df.empty:
            try:
                validate_review_packet_readback(
                    existing_df,
                    batch_id=batch_id,
                    expected_companies=manifest.companies,
                    required_columns=required_review_columns,
                )

                readback_path = settings.research_batches_dir / (
                    f"{batch_id}_review_packet_sheet_readback_{timestamp}.csv"
                )
                atomic_write_csv(readback_path, existing_df)
                manifest.artifacts.review_sheet_readback_path = str(readback_path)

                manifest.state = BatchState.AWAITING_RECOMMENDATION_APPROVAL
                manifest.last_successful_step = "PUBLISH_REVIEW_PACKET"
                manifest.resume_from = "READ_REVIEW_DECISIONS"
                manifest.error = None
                save_batch_manifest(manifest)

                return WorkflowResult(
                    status=WorkflowStatus.NOOP,
                    batch_id=batch_id,
                    state=manifest.state,
                    message=(
                        "Existing Review Packet already matches the batch and "
                        "was adopted without overwriting the sheet."
                    ),
                    persistent_data_changed=True,
                    resume_from=manifest.resume_from,
                    artifact_paths={
                        "review_packet": manifest.artifacts.review_packet_path,
                        "sheet_readback": manifest.artifacts.review_sheet_readback_path,
                        "manifest": manifest.artifacts.manifest_path,
                    },
                    details={
                        "worksheet_title": review_ws.title,
                        "row_count": len(existing_df),
                        "company_count": existing_df["company"].nunique(),
                        "companies": existing_df["company"].astype(str).tolist(),
                        "publication_mode": "validated_existing",
                        "sheet_write_performed": False,
                    },
                )
            except Exception:
                # Existing sheet is stale or structurally invalid.
                # Back it up before replacing it with the canonical packet.
                backup_path = settings.research_batches_dir / (
                    f"{batch_id}_review_packet_sheet_backup_{timestamp}.csv"
                )
                atomic_write_csv(backup_path, existing_df)
                manifest.artifacts.review_sheet_backup_path = str(backup_path)

        publication = publish_review_packet(
            spreadsheet,
            packet_df,
            batch_id=batch_id,
            expected_companies=manifest.companies,
            worksheet_title=settings.review_packet_tab,
            required_columns=required_review_columns,
        )

        readback_path = settings.research_batches_dir / (
            f"{batch_id}_review_packet_sheet_readback_{timestamp}.csv"
        )
        atomic_write_csv(readback_path, publication.readback_df)
        manifest.artifacts.review_sheet_readback_path = str(readback_path)

        manifest.state = BatchState.AWAITING_RECOMMENDATION_APPROVAL
        manifest.last_successful_step = "PUBLISH_REVIEW_PACKET"
        manifest.resume_from = "READ_REVIEW_DECISIONS"
        manifest.error = None
        save_batch_manifest(manifest)

        return WorkflowResult(
            status=WorkflowStatus.SUCCESS,
            batch_id=batch_id,
            state=manifest.state,
            message=(
                "Review Packet published and validated by read-back."
            ),
            persistent_data_changed=True,
            resume_from=manifest.resume_from,
            artifact_paths={
                "review_packet": manifest.artifacts.review_packet_path,
                "sheet_backup": manifest.artifacts.review_sheet_backup_path,
                "sheet_readback": manifest.artifacts.review_sheet_readback_path,
                "manifest": manifest.artifacts.manifest_path,
            },
            details={
                "worksheet_title": publication.worksheet_title,
                "row_count": publication.row_count,
                "company_count": publication.company_count,
                "companies": publication.companies,
                "publication_mode": "published_new",
                "sheet_write_performed": True,
            },
        )

    except Exception as exc:
        manifest.state = BatchState.ERROR_REQUIRES_REVIEW
        manifest.resume_from = "PUBLISH_REVIEW_PACKET"
        manifest.error = {
            "message": str(exc),
            "persistent_data_may_have_changed": True,
        }
        save_batch_manifest(manifest)

        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=str(exc),
            resume_from=manifest.resume_from,
            details={
                "persistent_data_may_have_changed": True,
                "sheet_backup": manifest.artifacts.review_sheet_backup_path,
            },
        )


def read_review_decisions_to_master_gate(
    *,
    batch_id: str,
    settings: Settings,
    spreadsheet: object,
    manifest_path: str | Path | None = None,
) -> WorkflowResult:
    from datetime import datetime, timezone

    from .decisions import (
        DecisionValidationError,
        validate_and_build_review_decisions,
    )
    from .google_sheets import dataframe_from_worksheet

    resolved_manifest_path = Path(
        manifest_path
        or settings.research_batches_dir / f"{batch_id}_manifest.json"
    )

    try:
        manifest = load_batch_manifest(resolved_manifest_path)
    except Exception as exc:
        return WorkflowResult.error(
            batch_id=batch_id,
            state=BatchState.ERROR_REQUIRES_REVIEW,
            message=f"Could not load batch manifest: {exc}",
            resume_from="READ_REVIEW_DECISIONS",
        )

    if manifest.state not in {
        BatchState.AWAITING_RECOMMENDATION_APPROVAL,
        BatchState.MASTER_UPDATE_READY,
        BatchState.ERROR_REQUIRES_REVIEW,
    }:
        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=(
                "Review decisions cannot be read from state "
                f"{manifest.state.value}. Expected "
                "AWAITING_RECOMMENDATION_APPROVAL."
            ),
            resume_from="READ_REVIEW_DECISIONS",
        )

    try:
        review_ws = spreadsheet.worksheet(settings.review_packet_tab)
        review_df = dataframe_from_worksheet(review_ws)

        validated = validate_and_build_review_decisions(
            review_df,
            batch_id=batch_id,
            expected_companies=manifest.companies,
        )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        readback_path = settings.research_batches_dir / (
            f"{batch_id}_review_decisions_sheet_readback_{timestamp}.csv"
        )
        validated_path = settings.research_batches_dir / (
            f"{batch_id}_validated_review_decisions.csv"
        )
        approved_path = settings.research_batches_dir / (
            f"{batch_id}_approved_master_updates.csv"
        )

        atomic_write_csv(readback_path, review_df)
        atomic_write_csv(validated_path, validated.decisions_df)
        atomic_write_csv(approved_path, validated.approved_df)

        manifest.artifacts.review_decision_readback_path = str(readback_path)
        manifest.artifacts.validated_decisions_path = str(validated_path)
        manifest.artifacts.approved_decisions_path = str(approved_path)

        for row in validated.decisions_df.to_dict(orient="records"):
            manifest.company_states[row["company"]] = row["company_state"]

        manifest.state = BatchState.MASTER_UPDATE_READY
        manifest.last_successful_step = "READ_REVIEW_DECISIONS"
        manifest.resume_from = "UPDATE_MASTER"
        manifest.error = None
        save_batch_manifest(manifest)

        return WorkflowResult(
            status=WorkflowStatus.SUCCESS,
            batch_id=batch_id,
            state=manifest.state,
            message=(
                "Human review decisions validated and durable master-update "
                "artifacts created."
            ),
            persistent_data_changed=True,
            resume_from=manifest.resume_from,
            artifact_paths={
                "decision_readback": str(readback_path),
                "validated_decisions": str(validated_path),
                "approved_decisions": str(approved_path),
                "manifest": manifest.artifacts.manifest_path,
            },
            details={
                "worksheet_title": review_ws.title,
                "decision_count": len(validated.decisions_df),
                "approved_count": len(validated.approved_df),
                "held_count": len(validated.held_df),
                "rejected_count": len(validated.rejected_df),
                "approved_companies": validated.approved_df[
                    "company"
                ].tolist(),
                "held_companies": validated.held_df["company"].tolist(),
                "rejected_companies": validated.rejected_df[
                    "company"
                ].tolist(),
            },
        )

    except DecisionValidationError as exc:
        manifest.state = BatchState.ERROR_REQUIRES_REVIEW
        manifest.resume_from = "READ_REVIEW_DECISIONS"
        manifest.error = {
            "message": str(exc),
            "issues": exc.issues,
        }
        save_batch_manifest(manifest)

        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=str(exc),
            resume_from=manifest.resume_from,
            details={"issues": exc.issues},
        )

    except Exception as exc:
        manifest.state = BatchState.ERROR_REQUIRES_REVIEW
        manifest.resume_from = "READ_REVIEW_DECISIONS"
        manifest.error = {"message": str(exc)}
        save_batch_manifest(manifest)

        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=str(exc),
            resume_from=manifest.resume_from,
        )
