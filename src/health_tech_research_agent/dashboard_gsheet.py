"""
Google-Sheet store adapter for the dashboard (interim editable surface).

The reliable version of "your editable layer is a Google Sheet" (DASHBOARD_DESIGN.md §7): a NATIVE Google Sheet
with a `Workspace` tab and a `Contacts` tab, read/written through the Sheets API (`gspread`) — so the cells you
edit ARE the data the build reads (no `.xlsx`-on-Drive conversion/sync ambiguity that lost edits in the first
live run, 2026-07-03).

INPUT-ONLY, same contract as the file store: the build reads the sheet and NEVER overwrites your edits; it only
SEEDS the two tabs once, when they don't exist yet. This module is a thin I/O adapter over a duck-typed gspread
`Spreadsheet` handle (the caller authenticates + opens it in Colab); the merge engine in `dashboard.py` stays
format-agnostic. `gspread` is NOT a hard dependency — only the caller that passes a live handle needs it.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import dashboard as dash


def _titles(spreadsheet: Any) -> set[str]:
    return {ws.title for ws in spreadsheet.worksheets()}


def store_has_workspace(spreadsheet: Any) -> bool:
    """Has the store been seeded yet? (Used to decide seed-vs-read — the build never re-seeds an existing tab.)"""
    return dash.WORKSPACE_SHEET in _titles(spreadsheet)


def read_gsheet_store(spreadsheet: Any) -> tuple[list[dict], list[dict]]:
    """Read the Workspace + Contacts tabs -> (workspace_rows, contacts_rows). A missing tab -> [] (first run)."""
    titles = _titles(spreadsheet)
    ws = spreadsheet.worksheet(dash.WORKSPACE_SHEET).get_all_records() if dash.WORKSPACE_SHEET in titles else []
    ct = spreadsheet.worksheet(dash.CONTACTS_SHEET).get_all_records() if dash.CONTACTS_SHEET in titles else []
    return list(ws), list(ct)


def _df_to_values(df: pd.DataFrame) -> list[list]:
    """A DataFrame -> a header row + string cell rows (blank for NaN) for a gspread `update`."""
    body = df.astype(object).where(df.notna(), "").values.tolist()
    return [list(df.columns)] + body


def seed_gsheet_store(spreadsheet: Any, records: list[dict]) -> bool:
    """Seed the two tabs if (and only if) they are missing. Workspace gets one row per company (tick `pursue`,
    add notes); Contacts gets just the header. Returns True if anything was created. NEVER touches an existing
    tab — your edits are safe."""
    titles = _titles(spreadsheet)
    seeded = False
    if dash.WORKSPACE_SHEET not in titles:
        df = dash.seed_workspace_sheet(records)
        ws = spreadsheet.add_worksheet(title=dash.WORKSPACE_SHEET,
                                       rows=max(len(df) + 10, 20), cols=max(len(df.columns) + 2, 10))
        ws.append_rows(_df_to_values(df))
        seeded = True
    if dash.CONTACTS_SHEET not in titles:
        df = pd.DataFrame(columns=dash.CONTACTS_COLUMNS)
        ws = spreadsheet.add_worksheet(title=dash.CONTACTS_SHEET, rows=50, cols=max(len(dash.CONTACTS_COLUMNS) + 2, 10))
        ws.append_rows(_df_to_values(df))
        seeded = True
    return seeded
