from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import COTPosition, COTReport, DataSource, SyncRun

logger = logging.getLogger("global_futures_oi.cftc")
DATASETS = {"legacy": ("Legacy Futures Only", "6dca-aqww"), "disaggregated": ("Disaggregated Futures Only", "72hh-3qpy"), "financial": ("Traders in Financial Futures", "gpe5-46if")}
TRADER_GROUP_FIELDS = {
    "legacy": {"commercial": ("comm_positions_long_all", "comm_positions_short_all"), "noncommercial": ("noncomm_positions_long_all", "noncomm_positions_short_all"), "nonreportable": ("nonrept_positions_long_all", "nonrept_positions_short_all")},
    "disaggregated": {"producer_merchant": ("prod_merc_positions_long", "prod_merc_positions_short"), "swap_dealer": ("swap_positions_long_all", "swap_positions_short_all"), "managed_money": ("m_money_positions_long", "m_money_positions_short"), "other_reportable": ("other_rept_positions_long", "other_rept_positions_short"), "nonreportable": ("nonrept_positions_long_all", "nonrept_positions_short_all")},
    "financial": {"dealer_intermediary": ("dealer_positions_long_all", "dealer_positions_short_all"), "asset_manager": ("asset_mgr_positions_long_all", "asset_mgr_positions_short_all"), "leveraged_funds": ("lev_money_positions_long_all", "lev_money_positions_short_all"), "other_reportable": ("other_rept_positions_long_all", "other_rept_positions_short_all"), "nonreportable": ("nonrept_positions_long_all", "nonrept_positions_short_all")},
}


def _first(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if row.get(name) not in (None, ""):
            return row[name]
    return None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:26], fmt).date()
        except ValueError:
            continue
    return None


def _asset_group(market_name: str) -> str:
    name = market_name.upper()
    if any(word in name for word in ("CORN", "WHEAT", "SOY", "COCOA", "COFFEE", "SUGAR", "COTTON", "LIVESTOCK", "CATTLE", "HOG")):
        return "commodities"
    if any(word in name for word in ("TREASURY", "EURODOLLAR", "SOFR", "S&P", "NASDAQ", "DOW", "CURRENCY", "BITCOIN")):
        return "financials"
    return "other"


def normalize_row(row: dict[str, Any], source: DataSource, dataset_key: str = "legacy") -> dict[str, Any]:
    report_date = _date(_first(row, "report_date_as_yyyy_mm_dd", "as_of_date_in_form_yyyymmdd", "report_date"))
    if report_date is None:
        raise ValueError("CFTC row has no recognizable report date")
    market_name = str(_first(row, "market_and_exchange_names", "market_name", "contract_market_name") or "Unknown")
    market_code = str(_first(row, "cftc_contract_market_code", "cftc_market_code", "market_code") or market_name)
    publication_date = _date(_first(row, "publication_date", "published_date", "publication_date_as_yyyy_mm_dd"))
    if report_date > timezone.localdate() or (publication_date and publication_date > timezone.localdate()):
        raise ValueError("CFTC row is not publicly available yet")
    positions = {group: {"long_position": _decimal(row.get(long_name)), "short_position": _decimal(row.get(short_name))} for group, (long_name, short_name) in TRADER_GROUP_FIELDS.get(dataset_key, {}).items()}
    return {"source": source, "report_date": report_date, "publication_date": publication_date, "market_code": market_code, "market_name": market_name, "contract_market_name": str(row.get("contract_market_name") or ""), "asset_group": _asset_group(market_name), "open_interest": _decimal(_first(row, "open_interest_all", "open_interest")), "change_in_open_interest": _decimal(_first(row, "change_in_open_interest_all", "change_in_open_interest")), "noncommercial_long": _decimal(_first(row, "noncomm_positions_long_all", "noncommercial_long")), "noncommercial_short": _decimal(_first(row, "noncomm_positions_short_all", "noncommercial_short")), "commercial_long": _decimal(_first(row, "comm_positions_long_all", "commercial_long")), "commercial_short": _decimal(_first(row, "comm_positions_short_all", "commercial_short")), "positions": positions, "raw_payload": row}


class CFTCClient:
    base_url = "https://publicreporting.cftc.gov/resource"

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": settings.CFTC_USER_AGENT})

    def fetch(self, dataset_code: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        page_size = min(limit or settings.CFTC_API_PAGE_SIZE, settings.CFTC_API_PAGE_SIZE)
        rows: list[dict[str, Any]] = []
        offset = 0
        while limit is None or len(rows) < limit:
            page_limit = min(page_size, limit - len(rows)) if limit else page_size
            for attempt in range(3):
                try:
                    response = self.session.get(f"{self.base_url}/{dataset_code}.json", params={"$limit": page_limit, "$offset": offset}, timeout=settings.CFTC_API_TIMEOUT_SECONDS)
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, list):
                        raise ValueError("CFTC API response must be a JSON list")
                    break
                except (requests.RequestException, ValueError):
                    if attempt == 2:
                        raise
                    logger.warning("Retry CFTC request dataset=%s attempt=%s", dataset_code, attempt + 1)
            rows.extend(data)
            if len(data) < page_limit:
                break
            offset += len(data)
        return rows[:limit] if limit else rows


def sync_dataset(dataset_key: str, *, client: CFTCClient | None = None, limit: int | None = None) -> SyncRun:
    if dataset_key not in DATASETS:
        raise ValueError(f"Unknown CFTC dataset: {dataset_key}")
    name, code = DATASETS[dataset_key]
    source, _ = DataSource.objects.get_or_create(dataset_code=code, defaults={"name": name, "endpoint": f"{CFTCClient.base_url}/{code}.json"})
    run = SyncRun.objects.create(source=source)
    try:
        rows = (client or CFTCClient()).fetch(code, limit=limit)
        created = updated = 0
        with transaction.atomic():
            for row in rows:
                values = normalize_row(row, source, dataset_key)
                positions = values.pop("positions")
                report_date = values.pop("report_date")
                market_code = values.pop("market_code")
                _, was_created = COTReport.objects.update_or_create(source=source, report_date=report_date, market_code=market_code, defaults=values)
                report = COTReport.objects.get(source=source, report_date=report_date, market_code=market_code)
                for group, position in positions.items():
                    if position["long_position"] is not None or position["short_position"] is not None:
                        COTPosition.objects.update_or_create(report=report, trader_group=group, defaults=position)
                created += int(was_created)
                updated += int(not was_created)
        run.records_seen = len(rows)
        run.records_created = created
        run.records_updated = updated
        run.status = SyncRun.Status.SUCCESS
    except Exception as exc:
        logger.exception("CFTC sync failed for %s", dataset_key)
        run.status = SyncRun.Status.FAILED
        run.error_message = str(exc)
        raise
    finally:
        run.finished_at = timezone.now()
        run.save(update_fields=["records_seen", "records_created", "records_updated", "status", "error_message", "finished_at"])
    return run
