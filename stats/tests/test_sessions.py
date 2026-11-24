"""Tests de /timeline, /failures, /sessions y del detalle de una sesión (docs/api-tablero.md)."""

from datetime import datetime, timedelta, timezone

from bson import ObjectId

from telemetry.models import Simulation

from .test_summary import BASE, DAY, StatsTestCase


def failure(sequence, mortise, reason, at=DAY):
    return {"sequence": sequence, "timestamp": at, "received_at": at, "type": "joint_attempt_failed",
            "data": {"tenon": "Leg/TenonRef", "mortise": mortise, "reason": reason, "elapsed_seconds": 10.0}}


def started(sequence=1, at=DAY):
    return {"sequence": sequence, "timestamp": at, "received_at": at, "type": "assembly_started",
            "data": {"furniture_id": "living_room_table", "joints": 4}}


class TimelineTests(StatsTestCase):
    def test_groups_by_day(self):
        self.add(started_at=DAY, correct=True)
        self.add(started_at=DAY + timedelta(hours=2), correct=False)
        self.add(started_at=DAY + timedelta(days=1), status="abandoned", outcome="abandoned", correct=False)
        body = self.get("/timeline")
        self.assertEqual(body["tz"], "UTC")
        self.assertEqual(body["days"], [
            {"date": "2026-11-20", "sessions": 2, "checked": 2, "correct": 1},
            {"date": "2026-11-21", "sessions": 1, "checked": 0, "correct": 0},
        ])

    def test_time_zone_moves_the_day(self):
        # 01:00 UTC del 21 es el 20 a las 22:00 en Buenos Aires
        self.add(started_at=datetime(2026, 11, 21, 1, 0, tzinfo=timezone.utc))
        body = self.get("/timeline", tz="America/Argentina/Buenos_Aires")
        self.assertEqual([day["date"] for day in body["days"]], ["2026-11-20"])

    def test_invalid_time_zone(self):
        response = self.client.get(BASE + "/timeline", {"tz": "Marte/Base"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_request")

    def test_applies_filters(self):
        self.add(furniture="stool")
        self.add(furniture="living_room_table")
        days = self.get("/timeline", furniture_id="stool")["days"]
        self.assertEqual(days[0]["sessions"], 1)


class FailuresTests(StatsTestCase):
    def test_failures_by_mortise(self):
        self.add(events=[started(), failure(2, "Table/Mortise_BR", "position"),
                         failure(3, "Table/Mortise_BR", "blocked"), failure(4, "Table/Mortise_FL", "position")])
        self.add(events=[started(), failure(2, "Table/Mortise_BR", "position")])
        mortises = self.get("/failures")["mortises"]
        self.assertEqual(mortises, [
            {"mortise": "Table/Mortise_BR", "failures": 3, "sessions": 2, "by_reason": {"position": 2, "blocked": 1}},
            {"mortise": "Table/Mortise_FL", "failures": 1, "sessions": 1, "by_reason": {"position": 1}},
        ])

    def test_applies_filters(self):
        self.add(furniture="stool", events=[failure(1, "Seat/Mortise_A", "orientation")])
        self.add(furniture="living_room_table", events=[failure(1, "Table/Mortise_BR", "position")])
        mortises = self.get("/failures", furniture_id="stool")["mortises"]
        self.assertEqual([m["mortise"] for m in mortises], ["Seat/Mortise_A"])

    def test_only_for_the_workshop(self):
        Simulation.objects.create(simulation_id="otra-simulacion", name="Otra")
        response = self.client.get("/stats/v1/simulations/otra-simulacion/failures")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")


class SessionListTests(StatsTestCase):
    def test_lists_closed_sessions_newest_first(self):
        older = self.add(started_at=DAY)
        newer = self.add(started_at=DAY + timedelta(hours=1))
        self.add(status="active", started_at=datetime.now(timezone.utc))
        body = self.get("/sessions")
        self.assertEqual([s["id"] for s in body["sessions"]], [str(newer["_id"]), str(older["_id"])])
        self.assertIsNone(body["next"])

    def test_never_exposes_private_fields(self):
        self.add(participant={"type": "email", "value": "persona@ejemplo.com"})
        item = self.get("/sessions")["sessions"][0]
        self.assertNotIn("participant", item)
        self.assertNotIn("session_id", item)
        self.assertNotIn("events", item)
        self.assertEqual(set(item), {"id", "alias", "status", "closed_by", "started_at", "finished_at",
                                     "event_count", "context", "summary"})

    def test_search_by_alias_ignores_case(self):
        target = self.add()
        self.add()
        alias = target["alias"]
        found = self.get("/sessions", alias=alias.upper())["sessions"]
        self.assertTrue(found)
        self.assertTrue(all(s["alias"] == alias for s in found))

    def test_alias_is_not_a_pattern(self):
        self.add()
        self.assertEqual(self.get("/sessions", alias=".*")["sessions"], [])

    def test_pagination(self):
        for hour in range(5):
            self.add(started_at=DAY + timedelta(hours=hour))
        first = self.get("/sessions", limit=2)
        self.assertEqual(len(first["sessions"]), 2)
        self.assertEqual(first["next"], first["sessions"][-1]["started_at"])

        second = self.get("/sessions", limit=2, before=first["next"])
        third = self.get("/sessions", limit=2, before=second["next"])
        ids = [s["id"] for page in (first, second, third) for s in page["sessions"]]
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(set(ids)), 5)
        self.assertIsNone(third["next"])

    def test_invalid_limit(self):
        response = self.client.get(BASE + "/sessions", {"limit": 500})
        self.assertEqual(response.status_code, 400)


class SessionDetailTests(StatsTestCase):
    def test_detail_with_events(self):
        document = self.add(events=[started(), failure(2, "Table/Mortise_BR", "position")])
        body = self.get(f"/sessions/{document['_id']}")
        self.assertEqual(body["id"], str(document["_id"]))
        self.assertEqual([e["type"] for e in body["events"]], ["assembly_started", "joint_attempt_failed"])
        self.assertEqual(set(body["events"][0]), {"sequence", "timestamp", "type", "data"})
        self.assertTrue(body["events"][0]["timestamp"].endswith("Z"))
        self.assertNotIn("participant", body)

    def test_active_session_is_not_found(self):
        document = self.add(status="active", started_at=datetime.now(timezone.utc))
        response = self.client.get(BASE + f"/sessions/{document['_id']}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "session_not_found")

    def test_unknown_or_invalid_id(self):
        for session_pk in (str(ObjectId()), "no-es-un-id"):
            with self.subTest(session_pk):
                response = self.client.get(BASE + f"/sessions/{session_pk}")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["error"]["code"], "session_not_found")
