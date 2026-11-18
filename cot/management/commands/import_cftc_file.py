from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from cot.file_import import read_cftc_file, save_parsed_files


class Command(BaseCommand):
    help = "Import CFTC official .xls/.txt files after detecting their report type from headers."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+", type=Path)
        parser.add_argument("--dry-run", action="store_true", help="Parse and validate without writing PostgreSQL")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        parsed_files = []
        for path in options["paths"]:
            try:
                parsed = read_cftc_file(path)
            except (FileNotFoundError, ValueError, ImportError) as exc:
                raise CommandError(str(exc)) from exc
            parsed_files.append(parsed)
            self.stdout.write(f"{path}: type={parsed.report_type}, rows={len(parsed.rows)}, rejected={parsed.rejected}, encoding={parsed.encoding or 'binary-xls'}, delimiter={parsed.delimiter or 'n/a'}")
        result = save_parsed_files(parsed_files, dry_run=options["dry_run"], limit=options["limit"])
        mode = "DRY-RUN" if options["dry_run"] else "IMPORTED"
        self.stdout.write(self.style.SUCCESS(f"{mode}: read={result['rows_read']} valid={result['rows_valid']} rejected={result['rows_rejected']} duplicates={result['duplicates']} created={result['created']} updated={result['updated']} latest={result['latest_report_date']}"))
