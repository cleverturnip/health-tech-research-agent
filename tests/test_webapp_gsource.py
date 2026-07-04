"""Phase-1 Step 2 — the Google-backed source: config parsing + Drive download logic.

Offline only: exercises the pieces that don't need Google (config, credential resolution, the Drive REST
download against a fake authorized session). The end-to-end build against a live Sheet is proven by the
Step-4 live verification, not here.
"""

import json
import re
from pathlib import Path

import pytest

from health_tech_research_agent.webapp.gsource import (
    GoogleSourceConfig,
    SourceError,
    download_data,
)


# --- a fake authorized session (Drive REST) ---------------------------------

class _FakeResp:
    def __init__(self, *, json_data=None, content=b""):
        self._json = json_data
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._json


class _FakeSession:
    """Answers the two Drive calls download_data makes: a name->id lookup, and an id->bytes media fetch."""

    def __init__(self, files: dict, blobs: dict):
        self.files = files      # name -> id
        self.blobs = blobs      # id -> bytes
        self.requests: list[str] = []

    def get(self, url, params=None, **kwargs):
        params = params or {}
        self.requests.append(url)
        if url.endswith("/files"):
            match = re.search(r"name = '([^']+)'", params.get("q", ""))
            name = match.group(1) if match else None
            file_id = self.files.get(name)
            return _FakeResp(json_data={"files": [{"id": file_id, "name": name}] if file_id else []})
        file_id = url.rsplit("/", 1)[-1]
        return _FakeResp(content=self.blobs.get(file_id, b""))


def test_download_data_writes_ledger_and_research(tmp_path):
    session = _FakeSession(
        files={"ledger.jsonl": "L1", "research.csv": "R1"},
        blobs={"L1": b'{"company": "x"}\n', "R1": b"company,x\nacme,1\n"},
    )
    ledger_path, research_path = download_data(
        session, "FOLDER", tmp_path, ledger_name="ledger.jsonl", research_name="research.csv")
    assert ledger_path == tmp_path / "ledger.jsonl"
    assert ledger_path.read_bytes() == b'{"company": "x"}\n'
    assert research_path == tmp_path / "research.csv"
    assert research_path.read_bytes() == b"company,x\nacme,1\n"


def test_download_data_research_optional(tmp_path):
    session = _FakeSession(files={"ledger.jsonl": "L1"}, blobs={"L1": b"{}"})
    ledger_path, research_path = download_data(
        session, "FOLDER", tmp_path, ledger_name="ledger.jsonl", research_name="research.csv")
    assert ledger_path.exists()
    assert research_path is None


def test_download_data_missing_ledger_raises(tmp_path):
    session = _FakeSession(files={}, blobs={})
    with pytest.raises(SourceError, match="ledger.jsonl"):
        download_data(session, "FOLDER", tmp_path, ledger_name="ledger.jsonl", research_name="research.csv")


# --- config -----------------------------------------------------------------

def test_config_from_env_reads_all_fields():
    cfg = GoogleSourceConfig.from_env({
        "HTRA_DRIVE_FOLDER_ID": "FID",
        "HTRA_GOOGLE_CREDENTIALS_FILE": "/x/key.json",
        "HTRA_DASHBOARD_SHEET_NAME": "My Sheet",
        "HTRA_WORK_DIR": "/work",
    })
    assert cfg.drive_folder_id == "FID"
    assert cfg.sheet_name == "My Sheet"
    assert cfg.work_dir == "/work"
    assert cfg.ledger_filename == "ledger.jsonl"      # default
    assert cfg.research_filename == "research.csv"    # default


def test_config_from_env_missing_required_raises():
    with pytest.raises(RuntimeError, match="HTRA_DRIVE_FOLDER_ID"):
        GoogleSourceConfig.from_env({"HTRA_GOOGLE_CREDENTIALS_FILE": "/x/key.json"})
    with pytest.raises(RuntimeError, match="CREDENTIALS"):
        GoogleSourceConfig.from_env({"HTRA_DRIVE_FOLDER_ID": "FID"})


def test_credentials_info_from_json_string():
    payload = {"type": "service_account", "client_email": "r@x.iam.gserviceaccount.com"}
    cfg = GoogleSourceConfig(drive_folder_id="F", work_dir="/w", credentials_json=json.dumps(payload))
    assert cfg.credentials_info() == payload


def test_credentials_info_from_file(tmp_path):
    key = tmp_path / "key.json"
    key.write_text(json.dumps({"type": "service_account"}), encoding="utf-8")
    cfg = GoogleSourceConfig(drive_folder_id="F", work_dir="/w", credentials_file=str(key))
    assert cfg.credentials_info()["type"] == "service_account"


def test_credentials_info_none_raises():
    cfg = GoogleSourceConfig(drive_folder_id="F", work_dir="/w")
    with pytest.raises(SourceError, match="No Google credentials"):
        cfg.credentials_info()
