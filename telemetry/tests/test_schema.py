"""
Tests del validador y del índice de la colección sessions (migración 0002).
Los tests del contrato verifican, además, que el validador acepta todos los documentos que escribe la API.
"""

from django.test import SimpleTestCase
from pymongo.errors import WriteError

from telemetry import store
from telemetry.utils import utc_now


def valid_session(**changes):
    now = utc_now()
    document = {
        "session_id": "00000000-0000-0000-0000-000000000000",
        "simulation_id": "taller-ensamblado",
        "alias": "Carpincho Turquesa",
        "participant": None,
        "status": "active",
        "started_at": now,
        "finished_at": None,
        "closed_by": None,
        "last_activity_at": now,
        "event_count": 0,
        "discarded_count": 0,
        "context": {},
        "summary": None,
        "summary_version": None,
        "events": [],
    }
    document.update(changes)
    return document


class SessionValidatorTests(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        self.sessions = store.sessions_collection()

    def tearDown(self):
        self.sessions.delete_many({})

    def test_accepts_valid_document(self):
        self.sessions.insert_one(valid_session())

    def test_rejects_invalid_documents(self):
        now = utc_now()
        cases = {
            "estado desconocido": valid_session(status="paused"),
            "fecha como texto": valid_session(started_at="2026-11-24T10:00:00Z"),
            "sin alias": {k: v for k, v in valid_session().items() if k != "alias"},
            "evento sin type": valid_session(events=[{"sequence": 1, "timestamp": now, "received_at": now}]),
            "sequence cero": valid_session(events=[
                {"sequence": 0, "timestamp": now, "received_at": now, "type": "x", "data": None}]),
            "más de 2000 eventos": valid_session(event_count=2001),
        }
        for name, document in cases.items():
            with self.subTest(name), self.assertRaises(WriteError):
                self.sessions.insert_one(document)

    def test_workshop_index_exists(self):
        index = self.sessions.index_information()["session_workshop_furniture"]
        self.assertEqual(index["key"], [("context.furniture_id", 1), ("started_at", -1)])
        self.assertEqual(index["partialFilterExpression"], {"simulation_id": "taller-ensamblado"})
