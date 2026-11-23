"""
Tests del contrato de Bitácora (API.md, versión 1.1).

Usan la base de prueba de MongoDB que crea Django (test_<nombre>), así que necesitan el contenedor:
    dc exec api python manage.py test telemetry
"""

import uuid
from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from telemetry import contract, store
from telemetry.aliases import COMBINATIONS, pick_alias
from telemetry.models import Session, Simulation
from telemetry.utils import utc_now

SIMULATION_ID = "taller-ensamblado"


def create_simulation(simulation_id, name):
    """Crea una simulación y devuelve (simulación, clave)."""
    simulation = Simulation.objects.create(simulation_id=simulation_id, name=name)
    return simulation, simulation.new_api_key


def delete_all():
    store.sessions_collection().delete_many({})
    Simulation.objects.all().delete()


def event(sequence, type_="test_event", data=None, timestamp="2026-11-23T18:11:49.019Z"):
    return {"sequence": sequence, "timestamp": timestamp, "type": type_, "data": data}


class ContractTestCase(SimpleTestCase):
    # SimpleTestCase y no TestCase: el registro de eventos escribe con PyMongo, fuera de una
    # transacción, así que los datos se borran a mano después de cada test.
    databases = {"default"}

    def setUp(self):
        self.simulation, self.key = create_simulation(SIMULATION_ID, "Taller de Ensamblado")
        self.other_simulation, self.other_key = create_simulation("otra-simulacion", "Otra")
        self.client = APIClient(HTTP_X_API_KEY=self.key)

    def tearDown(self):
        delete_all()

    # ───────────── Ayudas ─────────────

    def assertContractError(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.content)
        self.assertEqual(response.json()["error"]["code"], code)
        self.assertTrue(response.json()["error"]["message"])

    def create_session(self, client=None, simulation_id=SIMULATION_ID, participant=None):
        client = client or self.client
        return client.post("/v1/sessions", {"simulation_id": simulation_id, "participant": participant},
                           format="json")

    def new_session_id(self):
        response = self.create_session()
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["session_id"]

    def send(self, session_id, events, client=None):
        client = client or self.client
        return client.post(f"/v1/sessions/{session_id}/events", {"events": events}, format="json")

    def finish(self, session_id, status="completed", client=None):
        client = client or self.client
        return client.post(f"/v1/sessions/{session_id}/finish", {"status": status}, format="json")


class HealthTests(ContractTestCase):
    def test_ok_with_key(self):
        response = self.client.get("/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_without_key(self):
        self.assertContractError(APIClient().get("/v1/health"), 401, "invalid_api_key")

    def test_wrong_key(self):
        self.assertContractError(APIClient(HTTP_X_API_KEY="bk_otra").get("/v1/health"), 401, "invalid_api_key")

    def test_inactive_simulation(self):
        self.simulation.is_active = False
        self.simulation.save()
        self.assertContractError(self.client.get("/v1/health"), 401, "invalid_api_key")


class CreateSessionTests(ContractTestCase):
    def test_creates_anonymous_session(self):
        response = self.create_session()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        uuid.UUID(body["session_id"])
        self.assertIn(body["alias"], COMBINATIONS)
        self.assertTrue(body["started_at"].endswith("Z"))

    def test_creates_identified_session(self):
        response = self.create_session(participant={"type": "email", "value": " persona@ejemplo.com "})
        self.assertEqual(response.status_code, 201)
        document = store.sessions_collection().find_one({"session_id": response.json()["session_id"]})
        self.assertEqual(document["participant"], {"type": "email", "value": "persona@ejemplo.com"})

    def test_invalid_participant(self):
        response = self.create_session(participant={"type": "telefono", "value": "123"})
        self.assertContractError(response, 400, "invalid_request")

    def test_missing_simulation_id(self):
        response = self.client.post("/v1/sessions", {"participant": None}, format="json")
        self.assertContractError(response, 400, "invalid_request")

    def test_key_of_another_simulation(self):
        response = self.create_session(client=APIClient(HTTP_X_API_KEY=self.other_key))
        self.assertContractError(response, 401, "invalid_api_key")

    def test_invalid_json(self):
        response = self.client.post("/v1/sessions", "{no es json", content_type="application/json")
        self.assertContractError(response, 400, "invalid_request")


class SendEventsTests(ContractTestCase):
    def setUp(self):
        super().setUp()
        self.session_id = self.new_session_id()

    def stored_sequences(self):
        document = store.sessions_collection().find_one({"session_id": self.session_id})
        return [e["sequence"] for e in document["events"]]

    def test_accepts_batch(self):
        response = self.send(self.session_id, [event(1, data={"joint": 1}), event(2)])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"accepted": 2, "duplicates": 0, "discarded": 0})

    def test_resending_counts_duplicates(self):
        self.send(self.session_id, [event(1), event(2)])
        response = self.send(self.session_id, [event(1), event(2), event(3)])
        self.assertEqual(response.json(), {"accepted": 1, "duplicates": 2, "discarded": 0})
        self.assertEqual(self.stored_sequences(), [1, 2, 3])

    def test_duplicates_within_batch(self):
        response = self.send(self.session_id, [event(1), event(1)])
        self.assertEqual(response.json(), {"accepted": 1, "duplicates": 1, "discarded": 0})

    def test_events_are_stored_in_order(self):
        self.send(self.session_id, [event(3), event(1)])
        self.send(self.session_id, [event(2)])
        self.assertEqual(self.stored_sequences(), [1, 2, 3])

    def test_empty_batch(self):
        response = self.send(self.session_id, [])
        self.assertEqual(response.json(), {"accepted": 0, "duplicates": 0, "discarded": 0})

    def test_batch_too_large(self):
        events = [event(i) for i in range(1, contract.MAX_BATCH_EVENTS + 2)]
        self.assertContractError(self.send(self.session_id, events), 413, "batch_too_large")

    def test_invalid_events(self):
        cases = {
            "sequence cero": event(0),
            "sequence booleano": {**event(1), "sequence": True},
            "sequence texto": {**event(1), "sequence": "1"},
            "timestamp sin Z": event(1, timestamp="2026-11-23T18:11:49"),
            "type con mayúsculas": event(1, type_="JointCompleted"),
            "type largo": event(1, type_="a" * (contract.MAX_TYPE_LENGTH + 1)),
            "data no objeto": event(1, data=[1, 2]),
            "data grande": event(1, data={"x": "a" * contract.MAX_DATA_BYTES}),
        }
        for name, invalid in cases.items():
            with self.subTest(name):
                self.assertContractError(self.send(self.session_id, [invalid]), 400, "invalid_request")
        self.assertEqual(self.stored_sequences(), [])

    def test_error_message_names_the_field(self):
        response = self.send(self.session_id, [event(1), event(2, timestamp="ayer")])
        self.assertIn("events.1.timestamp", response.json()["error"]["message"])

    def test_body_without_events(self):
        response = self.client.post(f"/v1/sessions/{self.session_id}/events", {}, format="json")
        self.assertContractError(response, 400, "invalid_request")

    def test_unknown_session(self):
        self.assertContractError(self.send(str(uuid.uuid4()), [event(1)]), 404, "session_not_found")

    def test_session_of_another_simulation(self):
        response = self.send(self.session_id, [event(1)], client=APIClient(HTTP_X_API_KEY=self.other_key))
        self.assertContractError(response, 404, "session_not_found")

    def test_finished_session(self):
        self.finish(self.session_id)
        self.assertContractError(self.send(self.session_id, [event(1)]), 409, "session_finished")

    def test_updates_last_activity(self):
        before = store.sessions_collection().find_one({"session_id": self.session_id})["last_activity_at"]
        self.send(self.session_id, [event(1)])
        after = store.sessions_collection().find_one({"session_id": self.session_id})["last_activity_at"]
        self.assertGreaterEqual(after, before)


@mock.patch.object(contract, "MAX_SESSION_EVENTS", 5)
class SessionFullTests(ContractTestCase):
    def setUp(self):
        super().setUp()
        self.session_id = self.new_session_id()

    def test_partial_batch_is_discarded(self):
        self.send(self.session_id, [event(1), event(2), event(3)])
        response = self.send(self.session_id, [event(3), event(4), event(5), event(7), event(6)])
        # 3 es duplicado; entran 4 y 5; 6 y 7 se descartan
        self.assertEqual(response.json(), {"accepted": 2, "duplicates": 1, "discarded": 2})
        document = store.sessions_collection().find_one({"session_id": self.session_id})
        self.assertEqual([e["sequence"] for e in document["events"]], [1, 2, 3, 4, 5])
        self.assertEqual(document["discarded_count"], 2)

    def test_full_session_rejects_new_events(self):
        self.send(self.session_id, [event(i) for i in range(1, 6)])
        self.assertContractError(self.send(self.session_id, [event(6)]), 409, "session_full")

    def test_full_session_accepts_resend_of_duplicates(self):
        self.send(self.session_id, [event(i) for i in range(1, 6)])
        response = self.send(self.session_id, [event(4), event(5)])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"accepted": 0, "duplicates": 2, "discarded": 0})


class FinishSessionTests(ContractTestCase):
    def setUp(self):
        super().setUp()
        self.session_id = self.new_session_id()

    def test_finishes(self):
        response = self.finish(self.session_id, "abandoned")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["session_id"], self.session_id)
        self.assertEqual(body["status"], "abandoned")
        self.assertTrue(body["finished_at"].endswith("Z"))
        document = store.sessions_collection().find_one({"session_id": self.session_id})
        self.assertEqual(document["closed_by"], "client")

    def test_second_finish_returns_first(self):
        first = self.finish(self.session_id, "completed").json()
        second = self.finish(self.session_id, "abandoned")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), first)

    def test_invalid_status(self):
        self.assertContractError(self.finish(self.session_id, "terminada"), 400, "invalid_request")

    def test_unknown_session(self):
        self.assertContractError(self.finish(str(uuid.uuid4())), 404, "session_not_found")


class ConcurrencyTests(ContractTestCase):
    """La escritura condicional falla si otra solicitud cambió la sesión: se reintenta."""

    def setUp(self):
        super().setUp()
        self.session_id = self.new_session_id()

    def patch_updates(self, failures):
        real = store.sessions_collection
        calls = {"count": 0}

        class Collection:
            def __init__(self, collection):
                self._collection = collection

            def __getattr__(self, name):
                return getattr(self._collection, name)

            def update_one(self, *args, **kwargs):
                calls["count"] += 1
                if calls["count"] <= failures:
                    return mock.Mock(matched_count=0)
                return self._collection.update_one(*args, **kwargs)

        return mock.patch.object(store, "sessions_collection", lambda: Collection(real()))

    def test_retries_after_conflict(self):
        with self.patch_updates(failures=2):
            response = self.send(self.session_id, [event(1)])
        self.assertEqual(response.json(), {"accepted": 1, "duplicates": 0, "discarded": 0})

    def test_gives_up_with_503(self):
        with self.patch_updates(failures=store.MAX_WRITE_ATTEMPTS):
            response = self.send(self.session_id, [event(1)])
        self.assertContractError(response, 503, "server_error")


class OrmCompatibilityTests(ContractTestCase):
    """Los documentos escritos con PyMongo se leen con el ORM (admin, tablero)."""

    def test_orm_reads_session_and_events(self):
        session_id = self.new_session_id()
        self.send(session_id, [event(1, "assembly_started", {"furniture_id": "taburete"}), event(2)])
        self.finish(session_id)

        session = Session.objects.get(session_id=session_id)
        self.assertEqual(session.status, Session.Status.COMPLETED)
        self.assertEqual(session.event_count, 2)
        self.assertEqual([e.sequence for e in session.events], [1, 2])
        self.assertEqual(session.events[0].data, {"furniture_id": "taburete"})
        self.assertIsNotNone(session.started_at.tzinfo)


class AliasTests(SimpleTestCase):
    class FakeSessions:
        def __init__(self, used):
            self.used = used

        def distinct(self, field, query):
            return self.used

    def test_avoids_recent_aliases(self):
        used = COMBINATIONS[:-1]
        self.assertEqual(pick_alias(self.FakeSessions(used), SIMULATION_ID, utc_now()), COMBINATIONS[-1])

    def test_adds_number_when_exhausted(self):
        alias = pick_alias(self.FakeSessions(COMBINATIONS), SIMULATION_ID, utc_now())
        name, number = alias.rsplit(" ", 1)
        self.assertIn(name, COMBINATIONS)
        self.assertTrue(number.isdigit())

    def test_only_recent_sessions_count(self):
        captured = {}

        class Sessions:
            def distinct(self, field, query):
                captured.update(query)
                return []

        now = utc_now()
        pick_alias(Sessions(), SIMULATION_ID, now)
        self.assertEqual(captured["simulation_id"], SIMULATION_ID)
        self.assertEqual(captured["started_at"]["$gte"], now - timedelta(days=30))
