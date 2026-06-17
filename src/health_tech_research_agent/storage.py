from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import tempfile
from typing import Any

import pandas as pd


class StorageError(RuntimeError):
    pass


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(destination.parent),
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        tmp_path.write_text(text, encoding=encoding)
        os.replace(tmp_path, destination)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    return destination


def atomic_write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    return atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
    )


def atomic_write_csv(path: str | Path, df: pd.DataFrame) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(destination.parent),
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, destination)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    return destination


def copy_with_backup(
    source: str | Path,
    destination: str | Path,
    *,
    backup_path: str | Path | None = None,
) -> Path:
    source_path = Path(source)
    destination_path = Path(destination)

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if destination_path.exists() and backup_path:
        backup = Path(backup_path)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination_path, backup)

    shutil.copy2(source_path, destination_path)
    return destination_path


def load_csv(path: str | Path, *, required_columns: list[str] | None = None) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    if required_columns:
        missing = [column for column in required_columns if column not in df.columns]
        if missing:
            raise StorageError(
                f"{csv_path} is missing required columns: {missing}"
            )

    return df


def load_json(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StorageError(f"Invalid JSON in {json_path}: {exc}") from exc
