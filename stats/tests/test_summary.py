"""
Tests de /stats/v1/simulations y /stats/v1/simulations/{id}/summary (docs/api-tablero.md).

Las sesiones se insertan con un resumen armado a mano, para controlar cada métrica.
"""

import uuid
from datetime import datetime, timedelta, timezone

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from telemetry import store
from telemetry.models import Simulation
from telemetry.tests.test_schema import valid_session

SIMULATION_ID = "taller-ensamblado"
BASE = f"/stats/v1/simulations/{SIMULATION_ID}"
DAY = datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc)


def summary(outcome="checked", correct=True, duration=100.0, failed=0, reasons=None,
            help_requests=0, help_seconds=0.0, consistent=True):
    return {
        "source": "client" if outcome != "none" else "events",
        "outcome": outcome,
        "completed": correct,
        "correct": correct,
        "duration_seconds": duration,
        "failed_attempts": failed,
        "failures_by_reason": reasons or {},
        "help_requests": help_requests,
        "help_seconds": help_seconds,
        "consistent": consistent,
    }


class StatsTestCase(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        cache.clear()   # el límite de solicitudes guarda sus contadores en la caché
        self.simulation = Simulation.objects.create(simulation_id=SIMULATION_ID, name="Taller de Ensamblado")
        self.client = APIClient()

    def tearDown(self):
        store.sessions_collection().delete_many({})
        Simulation.objects.all().delete()

    def add(self, status="completed", furniture="living_room_table", mobile=False, started_at=DAY,
            last_activity_at=None, events=None, participant=None, **summary_fields):
        closed = status != "active"
        document = valid_session(
            session_id=str(uuid.uuid4()),
            simulation_id=SIMULATION_ID,
            status=status,
            started_at=started_at,
            last_activity_at=last_activity_at or started_at,
            finished_at=started_at + timedelta(minutes=5) if closed else None,
            closed_by="client" if closed else None,
            context={"furniture_id": furniture, "app_version": "1.1.1", "mobile": mobile},
            summary=summary(**summary_fields) if closed else None,
            summary_version=1 if closed else None,
            participant=participant,
            events=events or [],
            event_count=len(events or []),
        )
        store.sessions_collection().insert_one(document)
        return document

    def get(self, path="/summary", **params):
        response = self.client.get(BASE + path, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()


class SimulationListTests(StatsTestCase):
    def test_lists_active_simulations(self):
        Simulation.objects.create(simulation_id="inactiva", name="Inactiva", is_active=False)
        self.add(started_at=DAY)
        self.add(started_at=DAY + timedelta(days=1))
        body = self.client.get("/stats/v1/simulations").json()
        self.assertEqual(body["simulations"], [{
            "simulation_id": SIMULATION_ID,
            "name": "Taller de Ensamblado",
            "sessions": 2,
            "last_session_at": "2026-11-21T15:00:00.000Z",
        }])


class SummaryTests(StatsTestCase):
    def test_unknown_simulation(self):
        response = self.client.get("/stats/v1/simulations/no-existe/summary")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "simulation_not_found")

    def test_without_sessions(self):
        body = self.get()
        self.assertEqual(body["sessions"]["total"], 0)
        self.assertIsNone(body["metrics"]["finish_rate"])
        self.assertEqual(body["metrics"]["duration_seconds"],
                         {"median": None, "p25": None, "p75": None, "sessions": 0})
        self.assertNotIn("groups", body)

    def test_sessions_and_outcomes(self):
        self.add(correct=True)
        self.add(correct=True)
        self.add(correct=False)
        self.add(status="abandoned", outcome="abandoned", correct=False)
        self.add(status="abandoned", outcome="none", correct=False)
        # Una sesión en curso: reciente, para que no se cierre por inactividad
        self.add(status="active", started_at=datetime.now(timezone.utc))
        sessions = self.get()["sessions"]
        self.assertEqual(sessions, {
            "total": 6, "active": 1, "completed": 3, "abandoned": 2,
            "outcomes": {"correct": 2, "incorrect": 1, "not_checked": 2},
        })

    def test_rates(self):
        self.add(correct=True)
        self.add(correct=False)
        self.add(status="abandoned", outcome="abandoned", correct=False)
        metrics = self.get()["metrics"]
        self.assertEqual(metrics["finish_rate"], 0.667)   # 2 comprobadas de 3 cerradas
        self.assertEqual(metrics["correct_rate"], 0.5)    # 1 correcta de 2 comprobadas

    def test_duration_only_counts_correct_sessions(self):
        for duration in (100.0, 120.0, 140.0, 160.0, 180.0):
            self.add(duration=duration)
        self.add(correct=False, duration=999.0)
        self.assertEqual(self.get()["metrics"]["duration_seconds"],
                         {"median": 140.0, "p25": 120.0, "p75": 160.0, "sessions": 5})

    def test_failed_attempts_and_reasons(self):
        self.add(failed=2, reasons={"position": 2})
        self.add(failed=6, reasons={"position": 4, "blocked": 2})
        self.add(status="abandoned", outcome="abandoned", correct=False, failed=9,
                 reasons={"orientation": 9})
        metrics = self.get()["metrics"]
        # failed_attempts: solo las comprobadas; failures_by_reason: todas las cerradas
        self.assertEqual(metrics["failed_attempts"], {"median": 4.0, "p25": 3.0, "p75": 5.0, "sessions": 2})
        self.assertEqual(metrics["failures_by_reason"], {"orientation": 9, "position": 6, "blocked": 2})

    def test_help(self):
        self.add(correct=True, help_requests=2, help_seconds=4.0)
        self.add(correct=False, help_requests=1, help_seconds=2.0)
        self.add(correct=True)
        self.add(correct=True)
        help_ = self.get()["metrics"]["help"]
        self.assertEqual(help_, {
            "usage_rate": 0.5,
            "median_seconds": 3.0,
            "correct_rate_with_help": 0.5,
            "correct_rate_without_help": 1.0,
        })

    def test_inconsistent_sessions(self):
        self.add(consistent=False)
        self.add()
        self.assertEqual(self.get()["metrics"]["inconsistent_sessions"], 1)

    def test_cache_control(self):
        response = self.client.get(BASE + "/summary")
        self.assertIn("max-age=60", response["Cache-Control"])
        self.assertIn("public", response["Cache-Control"])

    def test_closes_inactive_sessions_first(self):
        old = datetime.now(timezone.utc) - timedelta(hours=3)
        self.add(status="active", started_at=old, last_activity_at=old)
        sessions = self.get()["sessions"]
        self.assertEqual(sessions["active"], 0)
        self.assertEqual(sessions["abandoned"], 1)


class FilterTests(StatsTestCase):
    def setUp(self):
        super().setUp()
        self.add(furniture="living_room_table", mobile=False, started_at=DAY)
        self.add(furniture="stool", mobile=True, started_at=DAY + timedelta(days=2))
        self.add(furniture="stool", mobile=False, started_at=DAY + timedelta(days=4))

    def total(self, **params):
        return self.get(**params)["sessions"]["total"]

    def test_furniture(self):
        self.assertEqual(self.total(furniture_id="stool"), 2)

    def test_mobile(self):
        self.assertEqual(self.total(mobile="true"), 1)
        self.assertEqual(self.total(mobile="false"), 2)

    def test_dates_are_inclusive(self):
        self.assertEqual(self.total(**{"from": "2026-11-22", "to": "2026-11-22"}), 1)
        self.assertEqual(self.total(**{"from": "2026-11-21"}), 2)
        self.assertEqual(self.total(to="2026-11-20"), 1)

    def test_echoes_filters(self):
        filters = self.get(furniture_id="stool", mobile="true", **{"from": "2026-11-21"})["filters"]
        self.assertEqual(filters, {"furniture_id": "stool", "mobile": True, "app_version": None,
                                   "from": "2026-11-21", "to": None})

    def test_invalid_filters(self):
        for params in ({"mobile": "quizás"}, {"from": "ayer"}, {"group_by": "color"}):
            with self.subTest(params):
                response = self.client.get(BASE + "/summary", params)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "invalid_request")

    def test_group_by_furniture(self):
        groups = self.get(group_by="furniture_id")["groups"]
        self.assertEqual([(g["key"], g["sessions"]["total"]) for g in groups],
                         [("stool", 2), ("living_room_table", 1)])
        self.assertIn("metrics", groups[0])

    def test_group_by_mobile(self):
        groups = self.get(group_by="mobile")["groups"]
        self.assertEqual([(g["key"], g["sessions"]["total"]) for g in groups], [(False, 2), (True, 1)])
