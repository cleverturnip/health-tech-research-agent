from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BatchState(str, Enum):
    CREATED = "CREATED"
    RESEARCH_RUNNING = "RESEARCH_RUNNING"
    RESEARCH_COMPLETE = "RESEARCH_COMPLETE"
    REVIEW_PACKET_READY = "REVIEW_PACKET_READY"
    AWAITING_RECOMMENDATION_APPROVAL = "AWAITING_RECOMMENDATION_APPROVAL"
    MASTER_UPDATE_RUNNING = "MASTER_UPDATE_RUNNING"
    DASHBOARD_REFRESH_RUNNING = "DASHBOARD_REFRESH_RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    ERROR_REQUIRES_REVIEW = "ERROR_REQUIRES_REVIEW"


class CompanyState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RESEARCH_COMPLETE = "RESEARCH_COMPLETE"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    REVIEW_READY = "REVIEW_READY"
    APPROVED = "APPROVED"
    HELD = "HELD"
    REJECTED = "REJECTED"
    COMMITTED = "COMMITTED"
    ERROR = "ERROR"


class WorkflowStatus(str, Enum):
    SUCCESS = "SUCCESS"
    NOOP = "NOOP"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    ERROR = "ERROR"


@dataclass
class ArtifactPaths:
    checkpoint_path: str = ""
    raw_path: str = ""
    summary_path: str = ""
    review_packet_path: str = ""
    manifest_path: str = ""
    master_backup_path: str = ""
    change_log_path: str = ""
    dashboard_path: str = ""

    def as_paths(self) -> dict[str, Path]:
        return {
            key: Path(value)
            for key, value in asdict(self).items()
            if value
        }


@dataclass
class BatchManifest:
    batch_id: str
    state: BatchState = BatchState.CREATED
    workflow_version: str = "0.1.0"
    prompt_version: str = "legacy-colab-v1"
    schema_version: str = "research-record-v1"
    companies: list[str] = field(default_factory=list)
    company_states: dict[str, str] = field(default_factory=dict)
    artifacts: ArtifactPaths = field(default_factory=ArtifactPaths)
    last_successful_step: str = ""
    resume_from: str = ""
    error: dict[str, Any] | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def set_company_state(self, company: str, state: CompanyState) -> None:
        self.company_states[company] = state.value
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BatchManifest":
        data = dict(payload)
        data["state"] = BatchState(data.get("state", BatchState.CREATED.value))
        artifacts = data.get("artifacts", {})
        if not isinstance(artifacts, ArtifactPaths):
            data["artifacts"] = ArtifactPaths(**artifacts)
        return cls(**data)


@dataclass
class WorkflowResult:
    status: WorkflowStatus
    batch_id: str
    state: BatchState
    message: str
    companies_researched: int = 0
    companies_reused: int = 0
    companies_failed: int = 0
    persistent_data_changed: bool = False
    resume_from: str = ""
    artifact_paths: dict[str, str] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def error(
        cls,
        *,
        batch_id: str,
        state: BatchState,
        message: str,
        resume_from: str = "",
        details: dict[str, Any] | None = None,
    ) -> "WorkflowResult":
        return cls(
            status=WorkflowStatus.ERROR,
            batch_id=batch_id,
            state=state,
            message=message,
            resume_from=resume_from,
            details=details or {},
        )
