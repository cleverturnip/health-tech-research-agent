from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pandas as pd


DEFAULT_BATCH_CONTROL_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1psVpW5SddVlgbnwkToXjbMvL0NWuyM3feyY5fwKCjjY/edit"
)
DEFAULT_REVIEW_PACKET_TAB = "Review Packet"


class WorksheetLike(Protocol):
    title: str

    def get_all_values(self) -> list[list[str]]: ...

    def clear(self) -> Any: ...

    def update(self, *, values: list[list[Any]], range_name: str) -> Any: ...


class SpreadsheetLike(Protocol):
    def worksheet(self, title: str) -> WorksheetLike: ...


class SheetPublicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewPacketPublication:
    batch_id: str
    worksheet_title: str
    row_count: int
    company_count: int
    companies: list[str]
    readback_df: pd.DataFrame


def safe_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def dataframe_from_worksheet(worksheet: WorksheetLike) -> pd.DataFrame:
    values = worksheet.get_all_values()
    if not values:
        return pd.DataFrame()

    headers = [safe_text(header) for header in values[0]]
    if any(header == "" for header in headers):
        raise SheetPublicationError(
            f"Worksheet '{worksheet.title}' contains blank header cells."
        )
    if len(headers) != len(set(headers)):
        raise SheetPublicationError(
            f"Worksheet '{worksheet.title}' contains duplicate headers."
        )

    rows: list[list[str]] = []
    for raw_row in values[1:]:
        padded = list(raw_row) + [""] * max(0, len(headers) - len(raw_row))
        rows.append(padded[: len(headers)])

    return pd.DataFrame(rows, columns=headers)


def _cell_value(value: Any) -> Any:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    return value


def dataframe_to_values(
    df: pd.DataFrame,
    *,
    headers: list[str] | None = None,
) -> list[list[Any]]:
    selected_headers = headers or list(df.columns)
    missing = [column for column in selected_headers if column not in df.columns]
    if missing:
        raise SheetPublicationError(
            f"Dataframe is missing publication columns: {missing}"
        )

    output: list[list[Any]] = [selected_headers]
    for row in df[selected_headers].itertuples(index=False, name=None):
        output.append([_cell_value(value) for value in row])

    return output


def write_dataframe_to_worksheet(
    worksheet: WorksheetLike,
    df: pd.DataFrame,
    *,
    headers: list[str] | None = None,
) -> None:
    values = dataframe_to_values(df, headers=headers)
    worksheet.clear()
    worksheet.update(values=values, range_name="A1")


def prepare_review_packet_for_sheet(
    packet_df: pd.DataFrame,
    *,
    batch_id: str,
) -> pd.DataFrame:
    if packet_df.empty:
        raise SheetPublicationError("Review packet is empty.")
    if "company" not in packet_df.columns:
        raise SheetPublicationError("Review packet is missing company column.")

    prepared = packet_df.copy()
    prepared["batch_id"] = batch_id
    prepared["batch_name"] = batch_id

    if prepared["company"].astype(str).duplicated().any():
        duplicates = sorted(
            set(
                prepared.loc[
                    prepared["company"].astype(str).duplicated(keep=False),
                    "company",
                ].astype(str)
            )
        )
        raise SheetPublicationError(
            f"Duplicate companies in review packet: {duplicates}"
        )

    ordered = ["batch_name", "batch_id", "company"]
    ordered.extend(
        column
        for column in prepared.columns
        if column not in ordered
    )
    return prepared[ordered]


def validate_review_packet_readback(
    readback_df: pd.DataFrame,
    *,
    batch_id: str,
    expected_companies: list[str],
    required_columns: list[str] | None = None,
) -> None:
    if readback_df.empty:
        raise SheetPublicationError("Review Packet read-back is empty.")

    batch_column = "batch_id" if "batch_id" in readback_df.columns else "batch_name"
    if batch_column not in readback_df.columns:
        raise SheetPublicationError(
            "Review Packet read-back is missing batch_id and batch_name."
        )
    if "company" not in readback_df.columns:
        raise SheetPublicationError("Review Packet read-back is missing company.")

    batch_values = {
        safe_text(value)
        for value in readback_df[batch_column].tolist()
        if safe_text(value)
    }
    if batch_values != {batch_id}:
        raise SheetPublicationError(
            f"Review Packet batch mismatch. Expected {batch_id!r}; "
            f"found {sorted(batch_values)!r}."
        )

    actual_companies = [
        safe_text(value)
        for value in readback_df["company"].tolist()
        if safe_text(value)
    ]
    expected_set = set(expected_companies)
    actual_set = set(actual_companies)

    if len(actual_companies) != len(actual_set):
        raise SheetPublicationError(
            "Review Packet read-back contains duplicate companies."
        )
    if actual_set != expected_set:
        missing = sorted(expected_set - actual_set)
        unexpected = sorted(actual_set - expected_set)
        raise SheetPublicationError(
            "Review Packet company mismatch. "
            f"Missing={missing}; unexpected={unexpected}."
        )
    if len(actual_companies) != len(expected_companies):
        raise SheetPublicationError(
            "Review Packet row count does not match expected company count."
        )

    for column in required_columns or []:
        if column not in readback_df.columns:
            raise SheetPublicationError(
                f"Review Packet read-back is missing required column: {column}"
            )


def publish_review_packet(
    spreadsheet: SpreadsheetLike,
    packet_df: pd.DataFrame,
    *,
    batch_id: str,
    expected_companies: list[str],
    worksheet_title: str = DEFAULT_REVIEW_PACKET_TAB,
    required_columns: list[str] | None = None,
) -> ReviewPacketPublication:
    worksheet = spreadsheet.worksheet(worksheet_title)
    prepared = prepare_review_packet_for_sheet(packet_df, batch_id=batch_id)

    write_dataframe_to_worksheet(worksheet, prepared)
    readback_df = dataframe_from_worksheet(worksheet)
    validate_review_packet_readback(
        readback_df,
        batch_id=batch_id,
        expected_companies=expected_companies,
        required_columns=required_columns,
    )

    return ReviewPacketPublication(
        batch_id=batch_id,
        worksheet_title=worksheet_title,
        row_count=len(readback_df),
        company_count=readback_df["company"].nunique(),
        companies=readback_df["company"].astype(str).tolist(),
        readback_df=readback_df,
    )


def authenticate_colab_gspread() -> Any:
    try:
        import gspread
        import google.auth
        from google.colab import auth
    except ImportError as exc:
        raise RuntimeError(
            "Google Sheets publication requires gspread, google-auth, and Colab."
        ) from exc

    auth.authenticate_user()
    credentials, _ = google.auth.default()
    return gspread.authorize(credentials)
