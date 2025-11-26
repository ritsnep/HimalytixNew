import json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from utils.maintenance import get_maintenance_state, set_maintenance_state


class Command(BaseCommand):
    help = "Toggle maintenance mode and update its message/status/app version."

    def add_arguments(self, parser):
        parser.add_argument(
            "mode",
            choices=["on", "off", "status"],
            help="Turn maintenance mode on/off or show current status.",
        )
        parser.add_argument(
            "--message",
            dest="message",
            help="User-facing maintenance message.",
        )
        parser.add_argument(
            "--status-text",
            dest="status_text",
            help="Short status text (e.g. 'System upgrade in progress — est. 5 minutes').",
        )
        parser.add_argument(
            "--retry-after",
            type=int,
            dest="retry_after",
            help="Retry-After seconds to send with 503 responses.",
        )
        parser.add_argument(
            "--app-version",
            dest="app_version",
            help="Override the app/static version (clients will auto-refresh on change).",
        )
        parser.add_argument(
            "--bump-version",
            action="store_true",
            dest="bump_version",
            help="Auto-set app version to current UTC timestamp.",
        )

    def handle(self, *args, **options):
        mode = options["mode"]
        if mode == "status":
            state = get_maintenance_state()
            self.stdout.write(json.dumps(state, indent=2))
            return

        if mode not in {"on", "off"}:
            raise CommandError("Mode must be 'on', 'off', or 'status'.")

        app_version = options.get("app_version")
        if options.get("bump_version"):
            app_version = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        updated_state = set_maintenance_state(
            enabled=(mode == "on"),
            message=options.get("message"),
            status_text=options.get("status_text"),
            app_version=app_version,
            retry_after=options.get("retry_after"),
        )
        self.stdout.write(self.style.SUCCESS(f"Maintenance mode set to {mode.upper()}:"))
        self.stdout.write(json.dumps(updated_state, indent=2))
