from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .models import COTReport, COTPosition, DataSource
from .services import _asset_group, _decimal, _date


REPORT_TYPES = ("legacy", "disaggregated", "tff")


@dataclass
class ParsedFile:
    path: Path
    report_type: str
    rows: list[dict[str, Any]]
    columns: list[str]
    encoding: str | None = None
    delimiter: str | None = None
    rejected: int = 0


def classify_report(columns: list[str]) -> str:
    normalized = {column.strip().lower() for column in columns}
    if {"dealer_positions_long_all", "asset_mgr_positions_long_all", "lev_money_positions_long_all"} <= normalized:
        return "tff"
    if any("prod_merc_positions_long" in column or "swap_positions_long" in column or "m_money_positions_long" in column for column in normalized):
        return "disaggregated"
    if {"comm_positions_long_all", "noncomm_positions_long_all"} <= normalized:
        return "legacy"
    raise ValueError("Không nhận diện được loại báo cáo từ tên cột")


def _read_txt(path: Path) -> tuple[pd.DataFrame, str, str]:
    raw = path.read_bytes()
    encoding = next((candidate for candidate in ("utf-8-sig", "utf-8", "cp1252", "latin1") if _can_decode(raw, candidate)), None)
    if encoding is None:
        raise ValueError(f"Không xác định được encoding cho {path.name}")
    sample = raw.decode(encoding, errors="strict")[:8192]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    return pd.read_csv(path, encoding=encoding, sep=delimiter, dtype=object), encoding, delimiter


def _can_decode(raw: bytes, encoding: str) -> bool:
    try:
        raw.decode(encoding)
        return True
    except UnicodeDecodeError:
        return False


def read_cftc_file(path: str | Path) -> ParsedFile:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    if file_path.suffix.lower() == ".xls":
        frame = pd.read_excel(file_path, engine="xlrd", dtype=object)
        encoding = delimiter = None
    elif file_path.suffix.lower() == ".txt":
        frame, encoding, delimiter = _read_txt(file_path)
    else:
        raise ValueError(f"Chỉ hỗ trợ .xls và .txt: {file_path.name}")
    frame.columns = [str(column).strip() for column in frame.columns]
    report_type = classify_report(list(frame.columns))
    rows: list[dict[str, Any]] = []
    rejected = 0
    for record in frame.to_dict(orient="records"):
        try:
            rows.append(normalize_file_row(record, report_type, file_path.name))
        except (ValueError, TypeError):
            rejected += 1
    return ParsedFile(file_path, report_type, rows, list(frame.columns), encoding, delimiter, rejected)


def _first(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and not pd.isna(value) and str(value).strip() != "":
            return value
    return None


def normalize_file_row(row: dict[str, Any], report_type: str, source_file: str) -> dict[str, Any]:
    report_date = _file_date(_first(row, "Report_Date_as_YYYY-MM-DD", "Report_Date_as_MM_DD_YYYY", "report_date"))
    market_code = _first(row, "CFTC_Contract_Market_Code", "CFTC_Market_Code")
    market_name = _first(row, "Market_and_Exchange_Names", "Market_Name")
    if report_date is None or market_code is None or market_name is None:
        raise ValueError("Thiếu ngày báo cáo, mã thị trường hoặc tên thị trường")
    positions_by_type = {
        "tff": {"dealer": ("Dealer_Positions_Long_All", "Dealer_Positions_Short_All"), "asset_manager": ("Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All"), "leveraged_funds": ("Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All"), "other_reportable": ("Other_Rept_Positions_Long_All", "Other_Rept_Positions_Short_All"), "nonreportable": ("NonRept_Positions_Long_All", "NonRept_Positions_Short_All")},
        "legacy": {"commercial": ("Comm_Positions_Long_All", "Comm_Positions_Short_All"), "noncommercial": ("Noncomm_Positions_Long_All", "Noncomm_Positions_Short_All"), "nonreportable": ("NonRept_Positions_Long_All", "NonRept_Positions_Short_All")},
        "disaggregated": {"producer_merchant": ("Prod_Merc_Positions_Long_All", "Prod_Merc_Positions_Short_All"), "swap_dealer": ("Swap_Positions_Long_All", "Swap_Positions_Short_All"), "managed_money": ("M_Money_Positions_Long_All", "M_Money_Positions_Short_All"), "other_reportable": ("Other_Rept_Positions_Long_All", "Other_Rept_Positions_Short_All"), "nonreportable": ("NonRept_Positions_Long_All", "NonRept_Positions_Short_All")},
    }[report_type]
    positions = {group: {"long_position": _file_decimal(row.get(long_field)), "short_position": _file_decimal(row.get(short_field))} for group, (long_field, short_field) in positions_by_type.items()}
    return {"report_type": report_type, "report_date": report_date, "market_code": str(market_code).strip(), "market_name": str(market_name).strip(), "asset_group": _asset_group(str(market_name)), "open_interest": _file_decimal(_first(row, "Open_Interest_All", "open_interest")), "change_in_open_interest": _file_decimal(_first(row, "Change_in_Open_Interest_All", "change_in_open_interest")), "positions": positions, "raw_payload": {_key: _json_safe(value) for _key, value in row.items()} | {"_source_file": source_file}}


def _file_date(value: Any) -> date | None:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date()
    if isinstance(value, date):
        return value
    return _date(value)


def _file_decimal(value: Any):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return _decimal(value)


def _json_safe(value: Any):
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value


def save_parsed_files(parsed_files: list[ParsedFile], *, dry_run: bool = False, limit: int | None = None) -> dict[str, int | str | date | None]:
    from django.db import transaction

    rows = [row for parsed in parsed_files for row in parsed.rows[:limit] if parsed.report_type == row["report_type"]]
    keys: set[tuple[str, str, date, str]] = set()
    duplicates = 0
    for row in rows:
        key = (row["report_type"], row["market_code"], row["report_date"])
        if key in keys:
            duplicates += 1
        keys.add(key)
    if dry_run:
        return {"rows_read": sum(len(parsed.rows[:limit]) + parsed.rejected for parsed in parsed_files), "rows_valid": len(rows), "rows_rejected": sum(parsed.rejected for parsed in parsed_files), "duplicates": duplicates, "created": 0, "updated": 0, "latest_report_date": max((row["report_date"] for row in rows), default=None)}
    source, _ = DataSource.objects.get_or_create(dataset_code="local-tff", defaults={"name": "Local CFTC TFF file", "endpoint": "https://publicreporting.cftc.gov/", "license_name": "CFTC official downloaded file; local research use"})
    created = updated = 0
    with transaction.atomic():
        for row in rows:
            positions = row.pop("positions")
            report, was_created = COTReport.objects.update_or_create(source=source, report_type=row["report_type"], report_date=row["report_date"], market_code=row["market_code"], defaults=row)
            for group, values in positions.items():
                if values["long_position"] is not None or values["short_position"] is not None:
                    COTPosition.objects.update_or_create(report=report, trader_group=group, defaults=values)
            created += int(was_created)
            updated += int(not was_created)
    return {"rows_read": sum(len(parsed.rows[:limit]) + parsed.rejected for parsed in parsed_files), "rows_valid": len(rows), "rows_rejected": sum(parsed.rejected for parsed in parsed_files), "duplicates": duplicates, "created": created, "updated": updated, "latest_report_date": max((row["report_date"] for row in rows), default=None)}
