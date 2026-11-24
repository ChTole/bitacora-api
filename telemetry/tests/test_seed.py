"""Tests del comando seed_sessions (datos de ejemplo para el tablero)."""

from io import StringIO

from django.core.management import CommandError, call_command
from django.test import override_settings

from telemetry import store

from .test_contract import ContractTestCase


@override_settings(DEBUG=True)
class SeedSessionsTests(ContractTestCase):
    def seed(self, *args):
        call_command("seed_sessions", *args, stdout=StringIO())

    def test_creates_sessions_with_summary(self):
        self.seed("--count", "40", "--seed", "7")
        sessions = list(store.sessions_collection().find({"demo": True}))
        self.assertEqual(len(sessions), 40)
        closed = [s for s in sessions if s["status"] != "active"]
        self.assertTrue(closed)
        for session in closed:
            self.assertIn(session["context"]["furniture_id"], {"living_room_table", "stool", "chair"})
            self.assertEqual(session["summary_version"], 1)
            self.assertEqual(session["event_count"], len(session["events"]))
        # Hay sesiones correctas, con errores y sin comprobar
        outcomes = {(s["summary"]["outcome"], s["summary"]["correct"]) for s in closed}
        self.assertIn(("checked", True), outcomes)

    def test_clear_only_deletes_demo_sessions(self):
        real = self.new_session_id()
        self.seed("--count", "5", "--seed", "1")
        self.seed("--clear")
        self.assertEqual(store.sessions_collection().count_documents({"demo": True}), 0)
        self.assertIsNotNone(store.sessions_collection().find_one({"session_id": real}))

    @override_settings(DEBUG=False)
    def test_refuses_without_debug(self):
        with self.assertRaises(CommandError):
            self.seed("--count", "1")
