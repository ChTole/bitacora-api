"""
Genera sesiones de ejemplo del Taller de Ensamblado, para probar el tablero en desarrollo sin
resolver la simulación decenas de veces.

Los eventos imitan los del Taller (docs/metricas.md) y el resumen lo calcula el analizador real,
igual que con una sesión de verdad. Las sesiones quedan marcadas con "demo": true para borrarlas
con --clear. Los identificadores de las cajas y espigas del taburete y la silla son ilustrativos.
"""

import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from telemetry import store
from telemetry.aliases import pick_alias
from telemetry.analyzers import get_analyzer
from telemetry.models import Session
from telemetry.utils import utc_now

SIMULATION_ID = "taller-ensamblado"

# Mueble: (cajas, peso en el sorteo, dificultad)
FURNITURE = {
    "living_room_table": ([f"Table/Mortise_{c}" for c in ("FL", "FR", "BL", "BR")], 0.5, 1.0),
    "stool": ([f"Seat/Mortise_{i}" for i in range(1, 5)] + [f"Leg_{c}/Mortise_Rail" for c in "ABCD"], 0.3, 1.6),
    "chair": ([f"Seat/Mortise_{i}" for i in range(1, 5)] + [f"Leg_{c}/Mortise_Rail" for c in "ABCD"]
              + [f"Backrest/Mortise_{i}" for i in range(1, 3)], 0.2, 2.2),
}
REASONS = (["position"] * 60) + (["blocked"] * 20) + (["orientation"] * 15) + (["incompatible"] * 5)


class Command(BaseCommand):
    help = "Genera sesiones de ejemplo del Taller para probar el tablero (solo en desarrollo)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=150, help="Cantidad de sesiones (por defecto, 150).")
        parser.add_argument("--days", type=int, default=21, help="Días hacia atrás en los que se reparten.")
        parser.add_argument("--seed", type=int, default=None, help="Semilla, para generar siempre los mismos datos.")
        parser.add_argument("--clear", action="store_true", help="Borra las sesiones de ejemplo y termina.")
        parser.add_argument("--allow-production", action="store_true",
                            help="Permite ejecutarlo con DEBUG=False. No usar contra la base de producción.")

    def handle(self, *args, count, days, seed, clear, allow_production, **options):
        if not settings.DEBUG and not allow_production:
            raise CommandError("Solo se ejecuta con DEBUG=True, para no mezclar datos inventados con los reales.")

        sessions = store.sessions_collection()
        if clear:
            deleted = sessions.delete_many({"demo": True}).deleted_count
            self.stdout.write(self.style.SUCCESS(f"Sesiones de ejemplo borradas: {deleted}."))
            return

        rng = random.Random(seed)
        analyzer = get_analyzer(SIMULATION_ID)
        now = utc_now()
        for _ in range(count):
            document = build_session(rng, now, days)
            document["alias"] = pick_alias(sessions, SIMULATION_ID, document["started_at"], rng)
            if document["status"] != Session.Status.ACTIVE:
                document["context"] = analyzer.context(document["events"])
                document["summary"] = analyzer.summary(document["events"], document["status"])
                document["summary_version"] = analyzer.version
            sessions.insert_one(document)

        self.stdout.write(self.style.SUCCESS(f"Sesiones de ejemplo creadas: {count}."))


def build_session(rng, now, days):
    furniture_id = rng.choices(list(FURNITURE), weights=[f[1] for f in FURNITURE.values()])[0]
    mortises, _, difficulty = FURNITURE[furniture_id]
    mobile = rng.random() < 0.3

    # Inicio: más sesiones en los días recientes, entre las 9 y las 21 de Argentina (12 a 24 UTC)
    day = min(int(rng.expovariate(1 / (days / 3))), days - 1)
    started_at = (now - timedelta(days=day)).replace(hour=rng.randint(12, 23), minute=rng.randint(0, 59),
                                                    second=rng.randint(0, 59), microsecond=0)
    if started_at > now:
        started_at -= timedelta(days=1)

    # Cómo termina: comprobada, abandonada desde el menú o con la pestaña cerrada (sin evento final)
    ending = rng.choices(["checked", "abandoned", "closed_tab"],
                         weights=[0.8 - 0.12 * difficulty, 0.15 + 0.1 * difficulty, 0.05])[0]
    joints_to_do = len(mortises) if ending == "checked" else rng.randint(0, len(mortises) - 1)
    incorrect = ending == "checked" and rng.random() < 0.08 * difficulty

    events, elapsed = [], 0.0
    counters = {"failed": 0, "help": 0, "help_s": 0.0, "controls": 0, "controls_s": 0.0, "undos": 0}

    def add(type_, data):
        events.append({"type": type_, "elapsed": elapsed, "data": data})

    add("assembly_started", {"furniture_id": furniture_id, "app_version": "1.1.1",
                             "pieces": len(mortises) + 1, "joints": len(mortises), "mobile": mobile})
    if rng.random() < 0.3:
        elapsed += rng.uniform(3, 10)
        duration = round(rng.uniform(2, 8), 1)
        add("controls_viewed", {"duration_seconds": duration, "elapsed_seconds": round(elapsed, 1)})
        counters["controls"] += 1
        counters["controls_s"] += duration

    order = rng.sample(mortises, len(mortises))
    for index, mortise in enumerate(order[:joints_to_do]):
        tenon = f"Piece_{index}/TenonRef"
        for _ in range(int(rng.expovariate(1 / (1.2 * difficulty)))):
            elapsed += rng.uniform(4, 14)
            add("joint_attempt_failed", {"tenon": tenon, "mortise": mortise, "reason": rng.choice(REASONS),
                                         "elapsed_seconds": round(elapsed, 1)})
            counters["failed"] += 1
        if rng.random() < 0.12 * difficulty:
            elapsed += rng.uniform(2, 6)
            duration = round(rng.uniform(0.8, 6), 1)
            add("help_viewed", {"duration_seconds": duration, "elapsed_seconds": round(elapsed, 1)})
            counters["help"] += 1
            counters["help_s"] += duration
        elapsed += rng.uniform(8, 25) * (0.8 + 0.2 * difficulty)
        expected = not (incorrect and index == joints_to_do - 1)
        add("joint_completed", {"tenon": tenon, "mortise": mortise, "expected": expected,
                                "elapsed_seconds": round(elapsed, 1), "previous_failures": 0})
        if rng.random() < 0.05:
            elapsed += rng.uniform(2, 5)
            add("joint_undone", {"tenon": tenon, "mortise": mortise, "mode": "undo", "elapsed_seconds": round(elapsed, 1)})
            elapsed += rng.uniform(2, 6)
            add("joint_completed", {"tenon": tenon, "mortise": mortise, "expected": expected,
                                    "elapsed_seconds": round(elapsed, 1), "previous_failures": 0})
            counters["undos"] += 1

    if ending != "closed_tab":
        elapsed += rng.uniform(2, 6)
        final_type = "assembly_checked" if ending == "checked" else "assembly_abandoned"
        add(final_type, {
            "furniture_id": furniture_id,
            "completed": joints_to_do == len(mortises),
            "duration_seconds": round(elapsed, 1),
            "joints_completed": joints_to_do,
            "joints_total": len(mortises),
            "incorrect_joints": 1 if incorrect else 0,
            "correct": ending == "checked" and not incorrect,
            "failed_attempts": counters["failed"],
            "grabs": joints_to_do * rng.randint(3, 8) + counters["failed"],
            "rotations": joints_to_do * rng.randint(1, 5),
            "undos": counters["undos"],
            "detaches": 0,
            "help_requests": counters["help"],
            "help_seconds": round(counters["help_s"], 1),
            "controls_views": counters["controls"],
            "controls_seconds": round(counters["controls_s"], 1),
        })

    # Un 3 % de sesiones pierde un evento, para que el tablero muestre alguna inconsistencia
    if ending == "checked" and len(events) > 3 and rng.random() < 0.03:
        events.pop(rng.randint(1, len(events) - 2))

    stored, last_at = [], started_at
    for sequence, event in enumerate(events, start=1):
        timestamp = started_at + timedelta(seconds=event["elapsed"])
        last_at = timestamp + timedelta(seconds=rng.uniform(0.1, 5))
        stored.append({"sequence": sequence, "timestamp": timestamp, "received_at": last_at,
                       "type": event["type"], "data": event["data"]})

    # Una sesión de hoy puede seguir en curso
    active = day == 0 and ending == "closed_tab"
    status = Session.Status.ACTIVE if active else (
        Session.Status.COMPLETED if ending == "checked" else Session.Status.ABANDONED)
    closed_by = None if active else (Session.ClosedBy.SERVER if ending == "closed_tab" else Session.ClosedBy.CLIENT)

    return {
        "session_id": Session._meta.get_field("session_id").get_default(),
        "simulation_id": SIMULATION_ID,
        "alias": "",
        "participant": None,
        "status": status,
        "started_at": started_at,
        "finished_at": None if active else last_at,
        "closed_by": closed_by,
        "last_activity_at": utc_now() if active else last_at,
        "event_count": len(stored),
        "discarded_count": 0,
        "context": {},
        "summary": None,
        "summary_version": None,
        "events": stored,
        "demo": True,
    }
