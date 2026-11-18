from django.shortcuts import render
from django.db.models import Q
from django.utils import timezone

from .analytics import oi_ranking, position_dataframe, report_dataframe
from .models import COTReport, SyncRun


def dashboard(request):
    market = request.GET.get("market", "").strip()
    asset_group = request.GET.get("asset_group", "").strip()
    reports = COTReport.objects.filter(Q(publication_date__isnull=True) | Q(publication_date__lte=timezone.localdate())).order_by("-report_date")
    if market:
        reports = reports.filter(market_code=market)
    if asset_group:
        reports = reports.filter(asset_group=asset_group)
    report_frame = report_dataframe(reports)
    position_frame = position_dataframe(reports)
    records = report_frame.sort_values("report_date", ascending=False).head(100).where(lambda x: x.notna(), None).to_dict("records") if not report_frame.empty else []
    for record in records:
        record["report_date"] = record["report_date"].date().isoformat()
    history = []
    if not report_frame.empty:
        history = report_frame.sort_values("report_date")[['report_date', 'open_interest']].dropna().assign(report_date=lambda x: x['report_date'].dt.strftime('%Y-%m-%d')).to_dict('records')
    position_records = position_frame.sort_values("report_date", ascending=False).head(100).where(lambda x: x.notna(), None).to_dict("records") if not position_frame.empty else []
    for record in position_records:
        record["report_date"] = str(record["report_date"])
    latest_sync = SyncRun.objects.select_related("source").order_by("-started_at").first()
    context = {"records": records, "position_records": position_records, "history_json": history, "markets": COTReport.objects.values("market_code", "market_name").distinct().order_by("market_name"), "asset_groups": COTReport.objects.exclude(asset_group="").values_list("asset_group", flat=True).distinct().order_by("asset_group"), "selected_market": market, "selected_asset_group": asset_group, "top_increases": oi_ranking(reports), "top_decreases": oi_ranking(reports, ascending=True), "has_positions": not position_frame.empty, "last_updated": COTReport.objects.order_by("-synced_at").values_list("synced_at", flat=True).first(), "latest_sync": latest_sync}
    return render(request, "cot/dashboard.html", context)
