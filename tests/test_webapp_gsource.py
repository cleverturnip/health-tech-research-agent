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
    put_file_to_folder,
    read_text_file,
    write_file_to_folder,
)
from health_tech_research_agent.webapp.source import FixtureDashboardSource

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"


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

    def __init__(self, files: dict, blobs: dict, *, swallow_writes: bool = False):
        self.files = files      # name -> id
        self.blobs = blobs      # id -> bytes
        self.swallow_writes = swallow_writes   # if True, PATCH is a no-op (simulates a failed write) -> read-back mismatch
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

    def patch(self, url, params=None, data=None, **kwargs):   # files.update (media upload)
        self.requests.append(url)
        file_id = url.rsplit("/", 1)[-1]
        if not self.swallow_writes:
            self.blobs[file_id] = data if isinstance(data, (bytes, bytearray)) else str(data).encode()
        return _FakeResp(content=b"")

    def post(self, url, params=None, data=None, headers=None, **kwargs):   # files.create (multipart)
        self.requests.append(url)
        body = data if isinstance(data, (bytes, bytearray)) else str(data).encode()
        marker = b"application/octet-stream\r\n\r\n"
        start = body.find(marker) + len(marker)
        content = body[start:body.rfind(b"\r\n--")]
        meta = re.search(rb"\{.*?\}", body[:start])
        name = json.loads(meta.group(0))["name"] if meta else "unknown"
        file_id = f"NEW{len(self.files)}"
        self.files[name] = file_id
        self.blobs[file_id] = content
        return _FakeResp(json_data={"id": file_id})


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


def test_credentials_info_prefers_file_over_json(tmp_path):
    # A mounted key file wins over a (possibly mangled) env-var JSON — the Render deploy fix.
    key = tmp_path / "service_account.json"
    key.write_text(json.dumps({"type": "service_account", "from": "file"}), encoding="utf-8")
    cfg = GoogleSourceConfig(drive_folder_id="F", work_dir="/w",
                             credentials_json="}}not-valid-json", credentials_file=str(key))
    assert cfg.credentials_info()["from"] == "file"


def test_credentials_info_bad_json_raises_actionable_error():
    cfg = GoogleSourceConfig(drive_folder_id="F", work_dir="/w", credentials_json="}}garbage")
    with pytest.raises(SourceError, match="Secret File"):
        cfg.credentials_info()


# --- Drive write-back (Phase 2) ---------------------------------------------

def test_write_file_to_folder_overwrites_and_reads_back():
    session = _FakeSession(files={"ledger.jsonl": "L1"}, blobs={"L1": b"old"})
    assert write_file_to_folder(session, "FOLDER", "ledger.jsonl", b"new-content") is True
    assert session.blobs["L1"] == b"new-content"      # the file was overwritten in place (same id)


def test_write_file_to_folder_missing_target_raises():
    session = _FakeSession(files={}, blobs={})
    with pytest.raises(SourceError, match="not in the shared Drive folder"):
        write_file_to_folder(session, "FOLDER", "ledger.jsonl", b"x")


def test_write_file_to_folder_readback_mismatch_returns_false():
    session = _FakeSession(files={"ledger.jsonl": "L1"}, blobs={"L1": b"old"}, swallow_writes=True)
    assert write_file_to_folder(session, "FOLDER", "ledger.jsonl", b"new") is False   # write didn't stick


# --- GATE-1 create-or-update + read (Phase 3) -------------------------------

def test_put_file_creates_when_missing_and_reads_back():
    session = _FakeSession(files={}, blobs={})
    assert put_file_to_folder(session, "FOLDER", "thesis.md", b"my thesis") is True
    assert read_text_file(session, "FOLDER", "thesis.md") == "my thesis"   # created + retrievable


def test_put_file_updates_when_present():
    session = _FakeSession(files={"thesis.md": "T1"}, blobs={"T1": b"old"})
    assert put_file_to_folder(session, "FOLDER", "thesis.md", b"revised") is True
    assert session.blobs["T1"] == b"revised"                               # overwrote in place (same id)


def test_put_file_readback_mismatch_returns_false():
    session = _FakeSession(files={"thesis.md": "T1"}, blobs={"T1": b"old"}, swallow_writes=True)
    assert put_file_to_folder(session, "FOLDER", "thesis.md", b"new") is False


def test_read_text_file_missing_returns_empty():
    session = _FakeSession(files={}, blobs={})
    assert read_text_file(session, "FOLDER", "thesis.md") == ""


# --- fixture review source (writable local copy, for the demo flow) ----------

def test_fixture_review_reads_pending_and_persists_writes(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path)
    entries, research = src.read_review_data()
    assert len(entries) == 5 and research is None
    # mutate + write, then re-read: the change persisted to the writable copy
    entries[0]["decision"] = {"human_override": "P1"}
    assert src.write_entries(entries) is True
    reread, _ = src.read_review_data()
    assert reread[0]["decision"]["human_override"] == "P1"


def test_fixture_thesis_and_candidates_roundtrip(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path)
    assert src.read_thesis() == ""                                    # none saved yet
    assert src.write_thesis("early-stage metabolic health") is True
    assert src.read_thesis() == "early-stage metabolic health"        # persisted + read back
    name = src.write_candidates(
        [{"company": "Acme Health", "why": "daily engagement", "signal": "Series A, $14M"}],
        date_str="2026-07-04")
    assert name == "candidates_2026-07-04.csv"
    saved = (tmp_path / name).read_text(encoding="utf-8")
    assert "Acme Health" in saved and "company,why,signal" in saved
    assert src.read_entries()[0]["company"]                           # entries available for grounding
