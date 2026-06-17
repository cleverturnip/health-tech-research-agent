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


def update_master_transactionally(
    *,
    batch_id: str,
    settings: Settings,
    manifest_path: str | Path | None = None,
    priority_applier=None,
) -> WorkflowResult:
    from .master_update import MasterUpdateError, execute_master_update_transaction

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
            resume_from="UPDATE_MASTER",
        )

    if manifest.state not in {
        BatchState.MASTER_UPDATE_READY,
        BatchState.DASHBOARD_REFRESH_READY,
        BatchState.ERROR_REQUIRES_REVIEW,
    }:
        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=(
                "Master update cannot run from state "
                f"{manifest.state.value}. Expected MASTER_UPDATE_READY."
            ),
            resume_from="UPDATE_MASTER",
        )

    summary_path = Path(manifest.artifacts.summary_path)
    approved_path = Path(manifest.artifacts.approved_decisions_path)

    try:
        approved_df = load_csv(approved_path)
        approved_keys = {
            str(value).strip().casefold()
            for value in approved_df["company"].tolist()
        }
        manifest_approved_keys = {
            str(company).strip().casefold()
            for company, state in manifest.company_states.items()
            if state == CompanyState.APPROVED.value
        }
        if approved_keys != manifest_approved_keys:
            raise MasterUpdateError(
                "Approved decisions artifact does not match approved company states in the manifest.",
                details={
                    "artifact_approved_keys": sorted(approved_keys),
                    "manifest_approved_keys": sorted(manifest_approved_keys),
                },
            )

        result = execute_master_update_transaction(
            master_path=settings.master_path,
            summary_path=summary_path,
            approved_path=approved_path,
            batch_id=batch_id,
            artifacts_dir=settings.research_batches_dir,
            priority_applier=priority_applier,
        )

        manifest.artifacts.master_backup_path = result.backup_path
        manifest.artifacts.master_readback_path = result.readback_path
        manifest.artifacts.master_change_log_path = result.change_log_path
        manifest.artifacts.change_log_path = result.change_log_path

        for company in approved_df["company"].astype(str).tolist():
            manifest.set_company_state(company, CompanyState.COMMITTED)

        manifest.state = BatchState.DASHBOARD_REFRESH_READY
        manifest.last_successful_step = "UPDATE_MASTER"
        manifest.resume_from = "REFRESH_DASHBOARD"
        manifest.error = None
        save_batch_manifest(manifest)

        status = WorkflowStatus.SUCCESS if result.write_performed else WorkflowStatus.NOOP
        message = (
            "Master updated transactionally and verified by read-back."
            if result.write_performed
            else "Master already matched the approved transaction; no rewrite was needed."
        )
        return WorkflowResult(
            status=status,
            batch_id=batch_id,
            state=manifest.state,
            message=message,
            persistent_data_changed=True,
            resume_from=manifest.resume_from,
            artifact_paths={
                "master": str(settings.master_path),
                "master_backup": result.backup_path,
                "master_readback": result.readback_path,
                "master_change_log": result.change_log_path,
                "manifest": manifest.artifacts.manifest_path,
            },
            details={
                "write_performed": result.write_performed,
                "inserted_count": result.inserted_count,
                "updated_count": result.updated_count,
                "unchanged_count": result.unchanged_count,
                "changed_field_count": len(result.change_log_df),
            },
        )

    except MasterUpdateError as exc:
        rollback_performed = bool(exc.details.get("rollback_performed"))
        manifest.state = (
            BatchState.ERROR_REQUIRES_REVIEW
            if rollback_performed or not exc.details.get("backup_path")
            else BatchState.PARTIAL_SUCCESS
        )
        manifest.resume_from = "UPDATE_MASTER"
        manifest.error = {
            "message": str(exc),
            **exc.details,
        }
        save_batch_manifest(manifest)
        return WorkflowResult(
            status=(
                WorkflowStatus.ERROR
                if manifest.state == BatchState.ERROR_REQUIRES_REVIEW
                else WorkflowStatus.PARTIAL_SUCCESS
            ),
            batch_id=batch_id,
            state=manifest.state,
            message=str(exc),
            persistent_data_changed=bool(exc.details.get("backup_path")),
            resume_from=manifest.resume_from,
            details=exc.details,
        )

    except Exception as exc:
        manifest.state = BatchState.ERROR_REQUIRES_REVIEW
        manifest.resume_from = "UPDATE_MASTER"
        manifest.error = {"message": str(exc)}
        save_batch_manifest(manifest)
        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=str(exc),
            resume_from=manifest.resume_from,
        )


def run_dashboard_refresh(
    *,
    batch_id: str,
    settings: Settings,
    manifest_path: str | Path | None = None,
    taxonomy_dir: str | Path | None = None,
    frame_hook=None,
) -> WorkflowResult:
    """Rebuild the dashboard workbook from the verified master and advance to
    COMPLETE only after a written-workbook read-back passes validation.

    Runs from DASHBOARD_REFRESH_READY, or from ERROR_REQUIRES_REVIEW when the
    resume point is REFRESH_DASHBOARD. On any failure the manifest returns to
    ERROR_REQUIRES_REVIEW and the master and prior workbook are left untouched
    (the new workbook is promoted into place only after validation passes).

    `frame_hook` is an optional transform applied to the dashboard frame before
    writing; it exists for fault-injection tests and is unused in production.
    """
    import os

    from .dashboard import (
        build_dashboard_frame,
        build_workbook_sheets,
        reconcile_override_segments,
        summarize_calibration_changes,
        validate_dashboard_workbook,
    )
    from .models import utc_now_iso
    from .storage import atomic_write_json, atomic_write_workbook, load_workbook_sheets

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
            resume_from="REFRESH_DASHBOARD",
        )

    resume_ok = manifest.state == BatchState.DASHBOARD_REFRESH_READY or (
        manifest.state == BatchState.ERROR_REQUIRES_REVIEW
        and manifest.resume_from == "REFRESH_DASHBOARD"
    )
    if not resume_ok:
        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=(
                "Dashboard refresh cannot run from state "
                f"{manifest.state.value} (resume_from={manifest.resume_from!r}). "
                "Expected DASHBOARD_REFRESH_READY or ERROR_REQUIRES_REVIEW "
                "resuming at REFRESH_DASHBOARD."
            ),
            resume_from="REFRESH_DASHBOARD",
        )

    completion_report_path = (
        settings.research_batches_dir / f"{batch_id}_dashboard_completion_report.json"
    )
    candidate_path = settings.research_batches_dir / f"{batch_id}_dashboard_candidate.xlsx"
    final_dashboard_path = settings.drive_root / "health_tech_market_dashboard.xlsx"

    manifest.state = BatchState.DASHBOARD_REFRESH_RUNNING
    manifest.touch()
    save_batch_manifest(manifest)

    try:
        master_df = load_csv(settings.master_path, required_columns=["company"])

        dashboard_df = build_dashboard_frame(master_df, taxonomy_dir=taxonomy_dir)
        if frame_hook is not None:
            dashboard_df = frame_hook(dashboard_df)

        sheets = build_workbook_sheets(dashboard_df)
        atomic_write_workbook(candidate_path, sheets)

        # Read-back: reopen every written sheet and validate against the master.
        readback = load_workbook_sheets(candidate_path)
        issues = validate_dashboard_workbook(
            readback, master_df=master_df, taxonomy_dir=taxonomy_dir
        )

        reconciliation = reconcile_override_segments(dashboard_df, taxonomy_dir=taxonomy_dir)
        calibration_changes = summarize_calibration_changes(master_df, dashboard_df)
        priority_counts = (
            dashboard_df["final_priority_code"].fillna("").replace("", "UNCODED").value_counts().to_dict()
            if "final_priority_code" in dashboard_df.columns
            else {}
        )

        report = {
            "batch_id": batch_id,
            "generated_at": utc_now_iso(),
            "company_count": int(len(dashboard_df)),
            "priority_counts": {str(k): int(v) for k, v in priority_counts.items()},
            "calibration_changes": calibration_changes,
            "override_reconciliation": {
                "checked": reconciliation["checked"],
                "matched": reconciliation["matched"],
                "mismatch_count": len(reconciliation["mismatches"]),
                "mismatches": reconciliation["mismatches"],
            },
            "validation": {
                "passed": not issues,
                "issue_count": len(issues),
                "issues": issues,
            },
            "sheets_written": list(sheets.keys()),
        }

        if issues:
            report["status"] = BatchState.ERROR_REQUIRES_REVIEW.value
            report["workbook_path"] = str(candidate_path)
            atomic_write_json(completion_report_path, report)

            manifest.artifacts.completion_report_path = str(completion_report_path)
            manifest.state = BatchState.ERROR_REQUIRES_REVIEW
            manifest.resume_from = "REFRESH_DASHBOARD"
            manifest.error = {
                "message": "Dashboard workbook failed read-back validation.",
                "issues": issues,
            }
            save_batch_manifest(manifest)

            return WorkflowResult.error(
                batch_id=batch_id,
                state=manifest.state,
                message="Dashboard workbook failed read-back validation.",
                resume_from=manifest.resume_from,
                details={
                    "issues": issues,
                    "completion_report": str(completion_report_path),
                },
            )

        # Validation passed: promote the candidate into place atomically.
        final_dashboard_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate_path, final_dashboard_path)

        report["status"] = BatchState.COMPLETE.value
        report["workbook_path"] = str(final_dashboard_path)
        atomic_write_json(completion_report_path, report)

        manifest.artifacts.dashboard_path = str(final_dashboard_path)
        manifest.artifacts.completion_report_path = str(completion_report_path)
        manifest.state = BatchState.COMPLETE
        manifest.last_successful_step = "REFRESH_DASHBOARD"
        manifest.resume_from = ""
        manifest.error = None
        save_batch_manifest(manifest)

        return WorkflowResult(
            status=WorkflowStatus.SUCCESS,
            batch_id=batch_id,
            state=manifest.state,
            message="Dashboard rebuilt and verified by read-back; batch COMPLETE.",
            persistent_data_changed=True,
            resume_from="",
            artifact_paths={
                "dashboard": str(final_dashboard_path),
                "completion_report": str(completion_report_path),
                "manifest": manifest.artifacts.manifest_path,
            },
            details={
                "company_count": report["company_count"],
                "calibration_changes": calibration_changes,
                "override_reconciliation": report["override_reconciliation"],
            },
        )

    except Exception as exc:
        manifest.state = BatchState.ERROR_REQUIRES_REVIEW
        manifest.resume_from = "REFRESH_DASHBOARD"
        manifest.error = {"message": str(exc)}
        save_batch_manifest(manifest)
        return WorkflowResult.error(
            batch_id=batch_id,
            state=manifest.state,
            message=str(exc),
            resume_from=manifest.resume_from,
        )
