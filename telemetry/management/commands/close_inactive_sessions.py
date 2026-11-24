from datetime import timedelta

from django.core.management.base import BaseCommand

from telemetry import store
from telemetry.models import Session
from telemetry.utils import utc_now


class Command(BaseCommand):
    help = ("Cierra como abandonadas las sesiones activas sin actividad reciente, por ejemplo las de una "
            "pestaña del navegador que se cerró. También se ejecuta antes de cada consulta de métricas.")

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=float, default=store.INACTIVITY_TIMEOUT.total_seconds() / 3600,
                            help="Horas sin actividad para considerar abandonada una sesión (por defecto, 2).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Muestra cuántas sesiones se cerrarían, sin cerrarlas.")

    def handle(self, *args, hours, dry_run, **options):
        timeout = timedelta(hours=hours)

        if dry_run:
            cutoff = utc_now() - timeout
            count = store.sessions_collection().count_documents(
                {"status": Session.Status.ACTIVE, "last_activity_at": {"$lt": cutoff}})
            self.stdout.write(f"Sesiones inactivas por más de {hours:g} h: {count}.")
            return

        total = 0
        while True:
            closed = store.close_inactive_sessions(timeout=timeout)
            total += closed
            if closed < store.INACTIVE_BATCH:
                break
        self.stdout.write(self.style.SUCCESS(f"Sesiones cerradas por inactividad: {total}."))
