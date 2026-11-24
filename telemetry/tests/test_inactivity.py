"""Tests del cierre de sesiones por inactividad (docs/modelo-de-datos.md, Cierre por inactividad)."""

from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command

from telemetry import store
from telemetry.utils import utc_now

from .test_contract import ContractTestCase, event


class InactivityTests(ContractTestCase):
    def setUp(self):
        super().setUp()
        self.session_id = self.new_session_id()
        self.send(self.session_id, [event(1, "assembly_started", {"furniture_id": "taburete", "joints": 8})])

    def document(self, session_id=None):
        return store.sessions_collection().find_one({"session_id": session_id or self.session_id})

    def later(self, hours):
        return utc_now() + timedelta(hours=hours)

    def test_closes_idle_session(self):
        self.assertEqual(store.close_inactive_sessions(now=self.later(3)), 1)
        document = self.document()
        self.assertEqual(document["status"], "abandoned")
        self.assertEqual(document["closed_by"], "server")
        # finished_at es la última actividad, no el momento en que se detectó
        self.assertEqual(document["finished_at"], document["last_activity_at"])
        # El resumen se calcula igual, solo con los eventos
        self.assertEqual(document["context"]["furniture_id"], "taburete")
        self.assertEqual(document["summary"]["source"], "events")

    def test_keeps_recent_session(self):
        self.assertEqual(store.close_inactive_sessions(now=self.later(1)), 0)
        self.assertEqual(self.document()["status"], "active")

    def test_ignores_finished_session(self):
        self.finish(self.session_id)
        self.assertEqual(store.close_inactive_sessions(now=self.later(3)), 0)
        self.assertEqual(self.document()["closed_by"], "client")

    def test_events_after_closing_are_rejected(self):
        store.close_inactive_sessions(now=self.later(3))
        self.assertContractError(self.send(self.session_id, [event(2)]), 409, "session_finished")

    def test_client_finish_after_closing_returns_server_close(self):
        store.close_inactive_sessions(now=self.later(3))
        response = self.finish(self.session_id, "completed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "abandoned")

    def test_session_with_new_events_is_not_closed(self):
        # Llega un lote entre la búsqueda y el cierre: la sesión ya no está inactiva
        real_find_one = store.sessions_collection().find_one
        received = []

        def find_then_receive(*args, **kwargs):
            document = real_find_one(*args, **kwargs)
            if not received:   # solo la primera lectura, la del cierre
                received.append(True)
                self.send(self.session_id, [event(2)])
            return document

        collection = store.sessions_collection()
        with mock.patch.object(store, "sessions_collection", return_value=collection), \
                mock.patch.object(collection, "find_one", side_effect=find_then_receive):
            closed = store.close_inactive_sessions(now=self.later(3))
        self.assertEqual(closed, 0)
        self.assertEqual(self.document()["status"], "active")
        self.assertEqual(self.document()["event_count"], 2)

    def test_command(self):
        output = StringIO()
        call_command("close_inactive_sessions", "--hours", "0", stdout=output)
        self.assertIn("1", output.getvalue())
        self.assertEqual(self.document()["status"], "abandoned")
