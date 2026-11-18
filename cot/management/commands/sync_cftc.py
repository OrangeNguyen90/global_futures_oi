from django.core.management.base import BaseCommand, CommandError
from cot.services import DATASETS, sync_dataset


class Command(BaseCommand):
    help = "Sync one or all public CFTC datasets into the database."

    def add_arguments(self, parser):
        parser.add_argument("dataset", choices=["all", *DATASETS], nargs="?", default="all")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        keys = DATASETS if options["dataset"] == "all" else {options["dataset"]: DATASETS[options["dataset"]]}
        for key in keys:
            try:
                run = sync_dataset(key, limit=options["limit"])
            except Exception as exc:
                raise CommandError(f"Sync failed for {key}: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(f"{key}: {run.records_seen} seen, {run.records_created} created, {run.records_updated} updated"))

