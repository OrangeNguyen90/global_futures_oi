from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.db.models import QuerySet

from .models import COTReport, COTPosition


def report_dataframe(reports: QuerySet[COTReport] | None = None) -> pd.DataFrame:
    reports = reports if reports is not None else COTReport.objects.all()
    rows = list(reports.values("id", "source_id", "report_date", "market_code", "market_name", "asset_group", "open_interest", "change_in_open_interest"))
    if not rows:
        return pd.DataFrame(columns=["id", "source_id", "report_date", "market_code", "market_name", "asset_group", "open_interest", "change_in_open_interest", "oi_change_pct"])
    frame = pd.DataFrame(rows)
    frame["report_date"] = pd.to_datetime(frame["report_date"])
    frame["open_interest"] = pd.to_numeric(frame["open_interest"], errors="coerce")
    frame["change_in_open_interest"] = pd.to_numeric(frame["change_in_open_interest"], errors="coerce")
    frame = frame.sort_values(["source_id", "market_code", "report_date"])
    previous = frame.groupby(["source_id", "market_code"])["open_interest"].shift(1)
    frame["oi_change_pct"] = ((frame["open_interest"] - previous) / previous.replace(0, pd.NA) * 100).round(4)
    return frame


def position_dataframe(reports: QuerySet[COTReport] | None = None) -> pd.DataFrame:
    report_ids = reports.values_list("id", flat=True) if reports is not None else COTReport.objects.values_list("id", flat=True)
    rows = list(COTPosition.objects.filter(report_id__in=report_ids).values("report_id", "trader_group", "long_position", "short_position", "report__report_date", "report__market_code", "report__market_name", "report__open_interest"))
    if not rows:
        return pd.DataFrame(columns=["report_id", "trader_group", "long_position", "short_position", "net_position", "net_oi_ratio"])
    frame = pd.DataFrame(rows).rename(columns={"report__report_date": "report_date", "report__market_code": "market_code", "report__market_name": "market_name", "report__open_interest": "open_interest"})
    for column in ("long_position", "short_position", "open_interest"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["net_position"] = frame["long_position"] - frame["short_position"]
    frame["net_oi_ratio"] = (frame["net_position"] / frame["open_interest"].replace(0, pd.NA) * 100).round(4)
    return frame


def oi_ranking(reports: QuerySet[COTReport] | None = None, *, ascending: bool = False, limit: int = 20) -> list[dict]:
    frame = report_dataframe(reports).dropna(subset=["oi_change_pct"])
    if frame.empty:
        return []
    latest = frame.sort_values("report_date").groupby(["source_id", "market_code"], as_index=False).tail(1)
    latest = latest.sort_values("oi_change_pct", ascending=ascending).head(limit)
    return latest[["market_name", "report_date", "oi_change_pct"]].assign(report_date=lambda x: x["report_date"].dt.date.astype(str)).to_dict("records")


def decimal_or_none(value):
    return None if pd.isna(value) else Decimal(str(value))
