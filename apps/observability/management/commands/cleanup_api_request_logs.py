from django.core.management.base import BaseCommand

from apps.observability.services import cleanup_old_request_logs


class Command(BaseCommand):
    help = "Delete old API request logs according to the configured retention policy."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None)

    def handle(self, *args, **options):
        deleted = cleanup_old_request_logs(days=options["days"])
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} old API request log row(s)."))
