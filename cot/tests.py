from unittest.mock import Mock
from pathlib import Path
from django.test import Client, TestCase, override_settings
from .analytics import oi_ranking, position_dataframe, report_dataframe
from .file_import import read_cftc_file, save_parsed_files
from .models import COTPosition, COTReport, SyncRun
from .services import CFTCClient, normalize_row, sync_dataset


class CFTCIngestionTests(TestCase):
    row = {"report_date_as_yyyy_mm_dd": "2026-10-16", "market_and_exchange_names": "TEST WHEAT - CHICAGO BOARD OF TRADE", "cftc_contract_market_code": "001602", "open_interest_all": "1000", "change_in_open_interest_all": "25", "noncomm_positions_long_all": "400", "noncomm_positions_short_all": "250", "comm_positions_long_all": "500", "comm_positions_short_all": "600", "nonrept_positions_long_all": "100", "nonrept_positions_short_all": "50"}

    def test_sync_is_idempotent(self):
        client = Mock(spec=CFTCClient)
        client.fetch.return_value = [self.row]
        first = sync_dataset("legacy", client=client)
        second = sync_dataset("legacy", client=client)
        self.assertEqual(first.records_created, 1)
        self.assertEqual(second.records_created, 0)
        self.assertEqual(second.records_updated, 1)
        self.assertEqual(COTReport.objects.count(), 1)
        self.assertEqual(COTReport.objects.get().open_interest, 1000)
        self.assertEqual(COTPosition.objects.count(), 3)

    def test_failed_sync_is_recorded(self):
        client = Mock(spec=CFTCClient)
        client.fetch.side_effect = RuntimeError("temporary CFTC outage")
        with self.assertRaisesRegex(RuntimeError, "temporary CFTC outage"):
            sync_dataset("legacy", client=client)
        run = SyncRun.objects.get()
        self.assertEqual(run.status, SyncRun.Status.FAILED)
        self.assertIn("temporary CFTC outage", run.error_message)

    def test_future_report_is_rejected(self):
        source = sync_dataset("legacy", client=Mock(fetch=Mock(return_value=[]))).source
        future = dict(self.row, report_date_as_yyyy_mm_dd="2099-01-01")
        with self.assertRaisesRegex(ValueError, "not publicly available"):
            normalize_row(future, source)

    def test_analytics_calculates_weekly_change_and_net_ratio(self):
        client = Mock(spec=CFTCClient)
        client.fetch.return_value = [self.row]
        sync_dataset("legacy", client=client)
        frame = report_dataframe(COTReport.objects.all())
        positions = position_dataframe(COTReport.objects.all())
        self.assertTrue(frame["oi_change_pct"].isna().all())
        self.assertEqual(float(positions.loc[positions.trader_group == "commercial", "net_position"].iloc[0]), -100)
        self.assertEqual(float(positions.loc[positions.trader_group == "commercial", "net_oi_ratio"].iloc[0]), -10)

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_dashboard_returns_empty_state_and_latest_sync_error(self):
        client = Client()
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chưa có dữ liệu")


class CFTCFileImportTests(TestCase):
    raw_dir = Path(__file__).resolve().parent.parent / "data" / "cfc" / "raw"

    def test_xls_and_txt_are_tff_and_deduplicated(self):
        xls = read_cftc_file(self.raw_dir / "FinFutYY.xls")
        txt = read_cftc_file(self.raw_dir / "FinFutYY.txt")
        self.assertEqual(xls.report_type, "tff")
        self.assertEqual(txt.report_type, "tff")
        self.assertEqual(txt.encoding, "utf-8-sig")
        self.assertEqual(txt.delimiter, ",")
        self.assertEqual(len(xls.rows), 3625)
        self.assertEqual(len(txt.rows), 3625)
        result = save_parsed_files([xls, txt], dry_run=True, limit=2)
        self.assertEqual(result["rows_read"], 4)
        self.assertEqual(result["rows_valid"], 4)
        self.assertEqual(result["duplicates"], 2)
        self.assertEqual(result["latest_report_date"].isoformat(), "2026-10-13")

    def test_import_does_not_sum_duplicate_files(self):
        xls = read_cftc_file(self.raw_dir / "FinFutYY.xls")
        txt = read_cftc_file(self.raw_dir / "FinFutYY.txt")
        result = save_parsed_files([xls, txt], limit=2)
        self.assertEqual(result["created"], 2)
        self.assertEqual(COTReport.objects.count(), 2)
        self.assertGreater(COTPosition.objects.count(), 0)
        self.assertEqual(COTReport.objects.order_by("-report_date").first().report_type, "tff")
