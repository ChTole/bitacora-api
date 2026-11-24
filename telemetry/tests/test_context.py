"""El contexto de una sesión se guarda desde el primer lote que lo trae, sin esperar al cierre."""

from telemetry import store

from .test_contract import ContractTestCase, event

STARTED = {"furniture_id": "stool", "app_version": "1.1.1", "pieces": 9, "joints": 8, "mobile": True}


class EarlyContextTests(ContractTestCase):
    def setUp(self):
        super().setUp()
        self.session_id = self.new_session_id()

    def context(self):
        return store.sessions_collection().find_one({"session_id": self.session_id})["context"]

    def test_active_session_gets_context(self):
        self.send(self.session_id, [event(1, "assembly_started", STARTED)])
        self.assertEqual(self.context(), {"furniture_id": "stool", "app_version": "1.1.1",
                                          "mobile": True, "joints_total": 8})

    def test_batch_without_start_keeps_empty_context(self):
        self.send(self.session_id, [event(1)])
        self.assertEqual(self.context(), {})

    def test_context_is_not_replaced(self):
        self.send(self.session_id, [event(1, "assembly_started", STARTED)])
        self.send(self.session_id, [event(2, "assembly_started", {**STARTED, "furniture_id": "chair"})])
        self.assertEqual(self.context()["furniture_id"], "stool")
