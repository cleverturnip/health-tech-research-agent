from __future__ import annotations

from pathlib import Path

from .models import BatchManifest, BatchState, CompanyState
from .storage import atomic_write_json, load_json


def build_batch_paths(batch_id: str, batches_dir: str | Path) -> dict[str, Path]:
    root = Path(batches_dir)
    root.mkdir(parents=True, exist_ok=True)

    return {
        "checkpoint_path": root / f"{batch_id}_checkpoint.csv",
        "raw_path": root / f"{batch_id}_raw.csv",
        "summary_path": root / f"{batch_id}_summary.csv",
        "review_packet_path": root / f"{batch_id}_human_review_packet.csv",
        "manifest_path": root / f"{batch_id}_manifest.json",
    }


def save_batch_manifest(manifest: BatchManifest) -> Path:
    manifest.touch()
    if not manifest.artifacts.manifest_path:
        raise ValueError("Manifest path is not configured.")

    return atomic_write_json(
        manifest.artifacts.manifest_path,
        manifest.to_dict(),
    )


def load_batch_manifest(path: str | Path) -> BatchManifest:
    return BatchManifest.from_dict(load_json(path))


def create_batch_manifest(
    *,
    batch_id: str,
    companies: list[str],
    batches_dir: str | Path,
    workflow_version: str = "0.1.0",
    prompt_version: str = "legacy-colab-v1",
    schema_version: str = "research-record-v1",
) -> BatchManifest:
    from .models import ArtifactPaths

    paths = build_batch_paths(batch_id, batches_dir)
    manifest = BatchManifest(
        batch_id=batch_id,
        state=BatchState.CREATED,
        workflow_version=workflow_version,
        prompt_version=prompt_version,
        schema_version=schema_version,
        companies=companies,
        company_states={
            company: CompanyState.PENDING.value
            for company in companies
        },
        artifacts=ArtifactPaths(
            checkpoint_path=str(paths["checkpoint_path"]),
            raw_path=str(paths["raw_path"]),
            summary_path=str(paths["summary_path"]),
            review_packet_path=str(paths["review_packet_path"]),
            manifest_path=str(paths["manifest_path"]),
        ),
    )
    save_batch_manifest(manifest)
    return manifest
