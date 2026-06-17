from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    repo_dir: Path
    drive_root: Path
    research_batches_dir: Path
    master_path: Path
    raw_archive_path: Path
    workflow_version: str = "0.1.0"

    def ensure_directories(self) -> None:
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        self.research_batches_dir.mkdir(parents=True, exist_ok=True)
        self.drive_root.mkdir(parents=True, exist_ok=True)


def load_settings(
    *,
    repo_dir: str | Path | None = None,
    drive_root: str | Path | None = None,
) -> Settings:
    resolved_repo = Path(
        repo_dir
        or os.environ.get("HTRA_REPO_DIR")
        or "/content/health-tech-research-agent"
    )

    resolved_drive = Path(
        drive_root
        or os.environ.get("HTRA_DRIVE_ROOT")
        or "/content/drive/MyDrive/Job Search/Health Tech Research"
    )

    return Settings(
        repo_dir=resolved_repo,
        drive_root=resolved_drive,
        research_batches_dir=resolved_drive / "research_batches",
        master_path=resolved_drive / "health_tech_market_research_summary_MASTER.csv",
        raw_archive_path=resolved_drive / "health_tech_raw_research_ARCHIVE.csv",
    )
