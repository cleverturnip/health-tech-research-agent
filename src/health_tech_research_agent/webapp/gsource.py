"""Google-backed dashboard source (Phase-1 Step 2).

Reads the real data on Refresh: downloads `ledger.jsonl` + the research CSV from a shared Drive folder and opens
the dashboard Google Sheet — all via a least-privilege READ-ONLY service account (P1.5) — then runs the existing
`dashboard.build_dashboard` and serves the HTML it renders. No new merge/scoring logic (Rule 1).

Auth is lazy (google libs imported only when a real build runs), so the offline unit tests here — which cover
config parsing + the Drive download logic against a fake session — need no Google credentials or gspread.
The end-to-end refresh against a live Sheet is proven by the Step-4 live verification, not offline.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .. import dashboard

_DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
_DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_DRIVE_RO = "https://www.googleapis.com/auth/drive.readonly"
# The dashboard SHEET needs write (the pursue-in-app decision, 2026-07-04) — a targeted single-cell update.
_SHEETS_RW = "https://www.googleapis.com/auth/spreadsheets"
# GATE-2 decisions write the ledger BACK to the Drive DATA folder (Phase 2, spec §4) — needs Drive write; the
# actual reach is still bounded by what's shared with the service account (the one folder). Reads use _DRIVE_RO.
_DRIVE_RW = "https://www.googleapis.com/auth/drive"
_DEFAULT_SHEET_NAME = "Health Tech Dashboard"


class SourceError(RuntimeError):
    """A configuration or data-access problem in the Google-backed source."""


# ---------------------------------------------------------------------------
# Drive download (REST, via an authorized session) — unit-tested with a fake session
# ---------------------------------------------------------------------------

def _find_file_id(session: Any, folder_id: str, name: str) -> str | None:
    q = f"'{folder_id}' in parents and name = '{name}' and trashed = false"
    resp = session.get(_DRIVE_FILES, params={
        "q": q, "fields": "files(id,name)", "pageSize": 5,
        "supportsAllDrives": True, "includeItemsFromAllDrives": True,
    })
    resp.raise_for_status()
    files = resp.json().get("files", [])
    return files[0]["id"] if files else None


def _download_file(session: Any, file_id: str, dest: Path) -> Path:
    resp = session.get(f"{_DRIVE_FILES}/{file_id}", params={"alt": "media", "supportsAllDrives": True})
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def download_data(session: Any, folder_id: str, dest_dir: str | Path, *,
                  ledger_name: str, research_name: str) -> tuple[Path, Path | None]:
    """Download the ledger (required) + research CSV (optional) from the shared folder into `dest_dir`.
    Returns `(ledger_path, research_path_or_None)`. A missing ledger RAISES (the dashboard can't render without
    it); a missing research file is tolerated (the detail cards just omit the research-evidence layer)."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    ledger_id = _find_file_id(session, folder_id, ledger_name)
    if not ledger_id:
        raise SourceError(
            f"'{ledger_name}' was not found in the shared Drive folder ({folder_id}). Check the file is in the "
            f"folder and the folder is shared with the service account (Viewer)."
        )
    ledger_path = _download_file(session, ledger_id, dest / ledger_name)

    research_path: Path | None = None
    research_id = _find_file_id(session, folder_id, research_name)
    if research_id:
        research_path = _download_file(session, research_id, dest / research_name)
    return ledger_path, research_path


# ---------------------------------------------------------------------------
# Drive write (Phase 2 — GATE-2 decisions write the ledger back) — unit-tested with a fake session
# ---------------------------------------------------------------------------

def update_drive_file(session: Any, file_id: str, content: bytes) -> None:
    """Overwrite an existing Drive file's content (files.update, media upload)."""
    resp = session.patch(f"{_DRIVE_UPLOAD}/{file_id}",
                         params={"uploadType": "media", "supportsAllDrives": True}, data=content)
    resp.raise_for_status()


def write_file_to_folder(session: Any, folder_id: str, name: str, content: bytes) -> bool:
    """Overwrite an EXISTING file in the folder with `content`, then read it back and verify (Rule 4/5). Returns
    True iff the read-back matches. A missing target RAISES (Phase-2 writes update files the pipeline already
    produced — e.g. `ledger.jsonl`)."""
    file_id = _find_file_id(session, folder_id, name)
    if not file_id:
        raise SourceError(f"Cannot write '{name}' — it is not in the shared Drive folder ({folder_id}).")
    update_drive_file(session, file_id, content)
    resp = session.get(f"{_DRIVE_FILES}/{file_id}", params={"alt": "media", "supportsAllDrives": True})
    resp.raise_for_status()
    return resp.content == content


def read_text_file(session: Any, folder_id: str, name: str) -> str:
    """Read a text file's content from the folder, or '' if it isn't there yet."""
    file_id = _find_file_id(session, folder_id, name)
    if not file_id:
        return ""
    resp = session.get(f"{_DRIVE_FILES}/{file_id}", params={"alt": "media", "supportsAllDrives": True})
    resp.raise_for_status()
    return resp.content.decode("utf-8")


# GATE-1 stores its thesis + candidate list as files Katelynd OWNS (the app only UPDATES them, never creates —
# a free-Gmail service account has no storage quota, so `files.create` always 403s; see the sa-cannot-create-drive
# note). The candidate list is a single append-only `candidates.csv`, one row per approved company, dated per batch.
_CANDIDATE_COLUMNS = ("date", "company", "why", "signal")


def parse_candidate_companies(text: str) -> list:
    """The distinct company names from a candidates.csv (order-preserving, case-insensitive dedup)."""
    import csv
    import io
    if not text.strip():
        return []
    out, seen = [], set()
    for row in csv.DictReader(io.StringIO(text)):
        name = str(row.get("company", "") or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def append_candidates_csv(existing: str, rows: list, date_str: str) -> bytes:
    """Rebuild `candidates.csv` = the existing rows + the newly-approved `rows` (each stamped `date_str`), as
    bytes. Append-only: prior batches are preserved and distinguished by the `date` column. Tolerant of a
    blank/absent existing file."""
    import csv
    import io
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=_CANDIDATE_COLUMNS)
    writer.writeheader()
    if existing.strip():
        for prior in csv.DictReader(io.StringIO(existing)):
            writer.writerow({col: str(prior.get(col, "") or "") for col in _CANDIDATE_COLUMNS})
    for row in rows:
        record = {"date": date_str}
        record.update({col: str(row.get(col, "") or "") for col in ("company", "why", "signal")})
        writer.writerow(record)
    return out.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@dataclass
class GoogleSourceConfig:
    drive_folder_id: str
    work_dir: str
    sheet_name: str = _DEFAULT_SHEET_NAME
    sheet_key: str | None = None
    ledger_filename: str = "ledger.jsonl"
    research_filename: str = "research.csv"
    credentials_json: str | None = None   # the service-account JSON as a string (Render secret)
    credentials_file: str | None = None   # OR a path to the JSON key (local dev)

    def credentials_info(self) -> dict:
        # Prefer a mounted key FILE when it exists (e.g. a Render Secret File) — env-var JSON is easy to mangle
        # on paste, so the file wins if present. Fall back to the JSON string, with an actionable error if it's
        # set but unparseable (the classic "pasted the key into an env var" failure).
        if self.credentials_file and Path(self.credentials_file).exists():
            return json.loads(Path(self.credentials_file).read_text(encoding="utf-8"))
        if self.credentials_json:
            try:
                return json.loads(self.credentials_json)
            except json.JSONDecodeError as exc:
                raise SourceError(
                    "HTRA_GOOGLE_CREDENTIALS_JSON is set but is not valid JSON — pasting a service-account key "
                    "into an env var often mangles it. Use a Render Secret File + HTRA_GOOGLE_CREDENTIALS_FILE "
                    "(pointing at the mounted path, e.g. /etc/secrets/service_account.json) instead."
                ) from exc
        raise SourceError(
            "No Google credentials configured — set HTRA_GOOGLE_CREDENTIALS_FILE (a mounted key file) or "
            "HTRA_GOOGLE_CREDENTIALS_JSON (the key contents)."
        )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "GoogleSourceConfig":
        env = os.environ if env is None else env
        folder = env.get("HTRA_DRIVE_FOLDER_ID")
        creds_json = env.get("HTRA_GOOGLE_CREDENTIALS_JSON")
        creds_file = env.get("HTRA_GOOGLE_CREDENTIALS_FILE")
        missing = []
        if not folder:
            missing.append("HTRA_DRIVE_FOLDER_ID")
        if not (creds_json or creds_file):
            missing.append("HTRA_GOOGLE_CREDENTIALS_JSON or HTRA_GOOGLE_CREDENTIALS_FILE")
        if missing:
            raise RuntimeError("Missing required Google-source env var(s): " + ", ".join(missing))
        return cls(
            drive_folder_id=folder,
            work_dir=env.get("HTRA_WORK_DIR", "/tmp/htra_work"),
            sheet_name=env.get("HTRA_DASHBOARD_SHEET_NAME", _DEFAULT_SHEET_NAME),
            sheet_key=env.get("HTRA_DASHBOARD_SHEET_KEY") or None,
            ledger_filename=env.get("HTRA_LEDGER_FILENAME", "ledger.jsonl"),
            research_filename=env.get("HTRA_RESEARCH_FILENAME", "research.csv"),
            credentials_json=creds_json,
            credentials_file=creds_file,
        )


# ---------------------------------------------------------------------------
# the source
# ---------------------------------------------------------------------------

class GoogleDashboardSource:
    """Builds the dashboard from live Google data. `refresh()` re-downloads + rebuilds; `html()` builds lazily."""

    def __init__(self, config: GoogleSourceConfig, *, taxonomy_dir: str | Path | None = None,
                 title: str = "Katelynd Career Research Dashboard") -> None:
        self.config = config
        self.taxonomy_dir = taxonomy_dir
        self.title = title
        self._html: str | None = None

    # -- google clients (lazy imports so offline tests need no google libs) --
    def _credentials(self, scopes: list[str]):
        from google.oauth2.service_account import Credentials
        return Credentials.from_service_account_info(self.config.credentials_info(), scopes=scopes)

    def _drive_session(self):
        from google.auth.transport.requests import AuthorizedSession
        return AuthorizedSession(self._credentials([_DRIVE_RO]))

    def _open_sheet(self):
        import gspread
        gc = gspread.authorize(self._credentials([_SHEETS_RW, _DRIVE_RO]))
        if self.config.sheet_key:
            return gc.open_by_key(self.config.sheet_key)
        return gc.open(self.config.sheet_name)

    def _build(self) -> str:
        work = Path(self.config.work_dir)
        ledger_path, research_path = download_data(
            self._drive_session(), self.config.drive_folder_id, work / "data",
            ledger_name=self.config.ledger_filename, research_name=self.config.research_filename)
        sheet = self._open_sheet()
        result = dashboard.build_dashboard(
            ledger_path, research=(str(research_path) if research_path else None),
            out_dir=work / "out", gsheet=sheet, taxonomy_dir=self.taxonomy_dir, title=self.title,
            skip_unreviewed=True)   # hosted flow: show reviewed companies; pending research batches live in GATE-2
        if not result.readback_ok:
            raise SourceError("Dashboard build failed read-back validation (Rule 5) — not serving a stale render.")
        return Path(result.html_path).read_text(encoding="utf-8")

    def html(self) -> str:
        if self._html is None:
            self._html = self._build()
        return self._html

    def refresh(self) -> None:
        self._html = self._build()

    def set_pursue(self, company: str, pursue: bool) -> bool:
        """Toggle a company's `pursue` flag in the Sheet (the one in-app write). Invalidates the cached render so
        the next `html()` rebuilds from the now-updated Sheet (All + Pursuit tabs stay consistent)."""
        from .. import dashboard_gsheet as gs
        ok = gs.set_pursue(self._open_sheet(), company, pursue)
        self._html = None
        return ok

    # -- GATE-2 review (Phase 2): read the ledger, write decisions back to the Drive folder --
    def _drive_write_session(self):
        from google.auth.transport.requests import AuthorizedSession
        return AuthorizedSession(self._credentials([_DRIVE_RW]))

    def read_review_data(self) -> tuple[list, Any]:
        """Download the ledger + research from Drive -> (ledger entries, research DataFrame|None)."""
        from .. import ledger, storage
        work = Path(self.config.work_dir)
        ledger_path, research_path = download_data(
            self._drive_session(), self.config.drive_folder_id, work / "data",
            ledger_name=self.config.ledger_filename, research_name=self.config.research_filename)
        research = storage.load_csv(research_path).fillna("") if research_path else None
        return ledger.read_ledger(ledger_path), research

    def write_entries(self, entries: list) -> bool:
        """Write the (decision-updated) ledger back to Drive — a targeted overwrite of `ledger.jsonl`, read-back
        verified (Rule 4/5). Invalidates the dashboard cache since the ledger changed."""
        content = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries).encode("utf-8")
        ok = write_file_to_folder(self._drive_write_session(), self.config.drive_folder_id,
                                  self.config.ledger_filename, content)
        self._html = None
        return ok

    # -- GATE-1 discovery (Phase 3): entries (grounding), the saved thesis, the approved candidate list, OpenAI --
    def read_entries(self) -> list:
        return self.read_review_data()[0]

    def read_candidates(self) -> list:
        return parse_candidate_companies(
            read_text_file(self._drive_session(), self.config.drive_folder_id, "candidates.csv"))

    def read_thesis(self) -> str:
        return read_text_file(self._drive_session(), self.config.drive_folder_id, "thesis.md")

    def write_thesis(self, text: str) -> bool:
        # UPDATE-only: `thesis.md` must already exist in the folder (Katelynd-owned); the app cannot create it.
        return write_file_to_folder(self._drive_write_session(), self.config.drive_folder_id,
                                    "thesis.md", (text or "").encode("utf-8"))

    def write_candidates(self, rows: list, *, date_str: str) -> str:
        # Append the approved rows to the existing (Katelynd-owned) `candidates.csv` and UPDATE it in place.
        existing = read_text_file(self._drive_session(), self.config.drive_folder_id, "candidates.csv")
        content = append_candidates_csv(existing, rows, date_str)
        if not write_file_to_folder(self._drive_write_session(), self.config.drive_folder_id,
                                    "candidates.csv", content):
            raise SourceError("Approved candidate-list write failed read-back validation — not saved.")
        return "candidates.csv"

    def openai_client(self):
        import openai
        return openai.OpenAI()  # reads OPENAI_API_KEY from the environment (Render secret / local env)
