"""Dashboard render sources — what the web app serves and re-serves on Refresh.

A `DashboardSource` produces the dashboard HTML and can `refresh()` it. This is the seam the Phase-1 steps swap
behind:
- Step 1 (now): `FixtureDashboardSource` renders from the bundled sample-ledger fixture — offline, no Google.
- Step 2: a Google-backed source runs `dashboard.build_dashboard` (reads the Sheet + Drive data) on refresh.

The app depends only on this protocol, so wiring the real source later changes no route code.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .. import dashboard, dashboard_html, ledger


@runtime_checkable
class DashboardSource(Protocol):
    def html(self) -> str:
        """The current dashboard HTML (built lazily; cached until `refresh`)."""

    def refresh(self) -> None:
        """Rebuild the dashboard from its underlying data."""


class FixtureDashboardSource:
    """Demo source: renders the dashboard from a sample ledger JSONL fixture (finalized in-memory so the §1a
    gate passes). Offline and Google-free — used for the skeleton until the real source is wired (Step 2)."""

    def __init__(self, fixture_path: str | Path,
                 *, title: str = "Health-tech career dashboard (demo data)",
                 review_work_dir: str | Path | None = None) -> None:
        self._fixture = Path(fixture_path)
        self._title = title
        self._review_work_dir = Path(review_work_dir) if review_work_dir else None
        self._html: str | None = None

    def _build(self) -> str:
        entries = ledger.finalize_gate2_review(
            ledger.read_ledger(self._fixture), reviewed_date=date.today().isoformat(),
            reviewed_at_gate="fixture")
        records = dashboard.build_company_records(entries)
        return dashboard_html.render_dashboard_html(records, title=self._title)

    def html(self) -> str:
        if self._html is None:
            self._html = self._build()
        return self._html

    def refresh(self) -> None:
        self._html = self._build()

    # -- GATE-2 review (Phase 2): a WRITABLE local copy of the raw (un-finalized) fixture, for the demo flow --
    def _review_ledger_path(self) -> Path:
        import shutil
        import tempfile
        base = self._review_work_dir or Path(tempfile.gettempdir()) / "htra_review_demo"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "ledger.jsonl"
        if not path.exists():
            shutil.copy(self._fixture, path)   # seed from the raw fixture (entries un-finalized -> all pending)
        return path

    def _review_research_path(self) -> Path:
        return self._review_ledger_path().parent / "research.csv"

    def read_review_data(self) -> tuple[list, Any]:
        import pandas as pd
        path = self._review_research_path()
        research = pd.read_csv(path).fillna("") if path.exists() else None
        return ledger.read_ledger(self._review_ledger_path()), research

    def write_research(self, rows) -> bool:
        import pandas as pd
        path = self._review_research_path()
        existing = (pd.read_csv(path).fillna("") if path.exists()
                    else pd.DataFrame(columns=list(rows.columns)))
        have = set(existing["company"].astype(str).str.lower()) if "company" in existing.columns else set()
        add = rows[~rows["company"].astype(str).str.lower().isin(have)]
        pd.concat([existing, add], ignore_index=True).to_csv(path, index=False)
        return True

    def write_entries(self, entries: list) -> bool:
        ledger.write_ledger(self._review_ledger_path(), entries)
        self._html = None
        return True

    # -- GATE-1 discovery (Phase 3): local versions for the demo --
    taxonomy_dir = None

    def read_entries(self) -> list:
        return self.read_review_data()[0]

    def read_candidates(self) -> list:
        from . import gsource
        path = self._gate1_path("candidates.csv")
        return gsource.parse_candidate_companies(path.read_text(encoding="utf-8") if path.exists() else "")

    def _gate1_path(self, name: str) -> Path:
        return self._review_ledger_path().parent / name

    def read_thesis(self) -> str:
        path = self._gate1_path("thesis.md")
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def write_thesis(self, text: str) -> bool:
        self._gate1_path("thesis.md").write_text(text or "", encoding="utf-8")
        return True

    def write_candidates(self, rows: list, *, date_str: str) -> str:
        from . import gsource
        path = self._gate1_path("candidates.csv")
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        path.write_bytes(gsource.append_candidates_csv(existing, rows, date_str))
        return "candidates.csv"

    def openai_client(self):
        import openai
        return openai.OpenAI()
