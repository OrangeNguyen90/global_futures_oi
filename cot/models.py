from django.db import models


class DataSource(models.Model):
    class Dataset(models.TextChoices):
        LEGACY = "legacy", "Legacy Futures Only"
        DISAGGREGATED = "disaggregated", "Disaggregated Futures Only"
        FINANCIAL = "financial", "Traders in Financial Futures"

    name = models.CharField(max_length=120, unique=True)
    dataset_code = models.CharField(max_length=20, unique=True)
    endpoint = models.URLField()
    license_name = models.CharField(max_length=255, default="CFTC public data / U.S. Government work")
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SyncRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    source = models.ForeignKey(DataSource, on_delete=models.PROTECT, related_name="sync_runs")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    records_seen = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)


class COTReport(models.Model):
    class ReportType(models.TextChoices):
        LEGACY = "legacy", "Legacy"
        DISAGGREGATED = "disaggregated", "Disaggregated"
        TFF = "tff", "Traders in Financial Futures"
        UNKNOWN = "unknown", "Unknown"

    source = models.ForeignKey(DataSource, on_delete=models.PROTECT, related_name="reports")
    report_type = models.CharField(max_length=20, choices=ReportType.choices, default=ReportType.UNKNOWN)
    report_date = models.DateField()
    publication_date = models.DateField(null=True, blank=True)
    market_code = models.CharField(max_length=80)
    market_name = models.CharField(max_length=255)
    contract_market_name = models.CharField(max_length=255, blank=True)
    asset_group = models.CharField(max_length=80, blank=True)
    open_interest = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    change_in_open_interest = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    noncommercial_long = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    noncommercial_short = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    commercial_long = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    commercial_short = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    raw_payload = models.JSONField(default=dict)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("source", "report_type", "report_date", "market_code"), name="unique_cot_source_type_date_market")]
        indexes = [models.Index(fields=("market_code", "report_date")), models.Index(fields=("source", "report_date"))]


class COTPosition(models.Model):
    """Normalized long/short positions for a trader group in one CFTC report."""

    report = models.ForeignKey(COTReport, on_delete=models.CASCADE, related_name="positions")
    trader_group = models.CharField(max_length=100)
    long_position = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    short_position = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("report", "trader_group"), name="unique_cot_report_trader_group")]
        indexes = [models.Index(fields=("trader_group", "report"))]

    @property
    def net_position(self):
        if self.long_position is None or self.short_position is None:
            return None
        return self.long_position - self.short_position
