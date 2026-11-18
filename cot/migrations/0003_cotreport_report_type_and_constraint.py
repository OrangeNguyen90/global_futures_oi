from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cot", "0002_cotreport_asset_group_datasource_license_name_and_more")]

    operations = [
        migrations.AddField(
            model_name="cotrePort".lower(),
            name="report_type",
            field=models.CharField(choices=[("legacy", "Legacy"), ("disaggregated", "Disaggregated"), ("tff", "Traders in Financial Futures"), ("unknown", "Unknown")], default="unknown", max_length=20),
        ),
        migrations.RemoveConstraint(model_name="cotrePort".lower(), name="unique_cot_source_date_market"),
        migrations.AddConstraint(
            model_name="cotrePort".lower(),
            constraint=models.UniqueConstraint(fields=("source", "report_type", "report_date", "market_code"), name="unique_cot_source_type_date_market"),
        ),
    ]
