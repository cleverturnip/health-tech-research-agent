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
from typing import Protocol, runtime_checkable

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
                 *, title: str = "Health-tech career dashboard (demo data)") -> None:
        self._fixture = Path(fixture_path)
        self._title = title
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
