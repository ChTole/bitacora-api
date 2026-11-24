"""
Tests del analizador del Taller (docs/metricas.md). No usan la base de datos.

La sesión de ejemplo, "Tero Alegre", es una sesión real del servidor de prueba: mesa ratona,
24 eventos, con fallas, uniones deshechas y consultas a la ayuda.
"""

import copy
import json
from pathlib import Path

from django.test import SimpleTestCase

from telemetry.analyzers import get_analyzer
from telemetry.analyzers.assembly_workshop import AssemblyWorkshopAnalyzer

SAMPLE = json.loads((Path(__file__).parent / "data" / "sesion_tero_alegre.json").read_text(encoding="utf-8"))


def sample_events():
    return copy.deepcopy(SAMPLE["events"])


class AssemblyWorkshopAnalyzerTests(SimpleTestCase):
    def setUp(self):
        self.analyzer = AssemblyWorkshopAnalyzer()

    def test_is_registered(self):
        self.assertIsInstance(get_analyzer("taller-ensamblado"), AssemblyWorkshopAnalyzer)

    def test_context(self):
        self.assertEqual(self.analyzer.context(sample_events()), {
            "furniture_id": "living_room_table",
            "app_version": "1.1.1",
            "mobile": False,
            "joints_total": 4,
        })

    def test_summary_of_sample_session(self):
        # Los mismos valores de la verificación en docs/metricas.md
        self.assertEqual(self.analyzer.summary(sample_events(), "completed"), {
            "source": "client",
            "outcome": "checked",
            "completed": True,
            "correct": True,
            "duration_seconds": 166.3,
            "time_to_first_joint_seconds": 26.0,
            "joints_total": 4,
            "joints_completed": 4,
            "incorrect_joints": 0,
            "connections": 7,
            "undos": 2,
            "detaches": 1,
            "failed_attempts": 8,
            "failures_by_reason": {"blocked": 2, "position": 6},
            "help_requests": 2,
            "help_seconds": 3.1,
            "controls_views": 2,
            "controls_seconds": 6.1,
            "grabs": 52,
            "rotations": 23,
            "consistent": True,
            "discrepancies": [],
        })

    def test_without_final_event_uses_events(self):
        # Por ejemplo, si se cerró la pestaña: el último evento no llega
        events = [e for e in sample_events() if e["type"] != "assembly_checked"]
        summary = self.analyzer.summary(events, "abandoned")
        self.assertEqual(summary["source"], "events")
        self.assertEqual(summary["outcome"], "none")
        self.assertEqual(summary["joints_completed"], 4)
        self.assertEqual(summary["failed_attempts"], 8)
        self.assertEqual(summary["duration_seconds"], 165.4)   # último elapsed_seconds registrado
        self.assertIsNone(summary["grabs"])
        self.assertIsNone(summary["consistent"])
        self.assertIsNone(summary["discrepancies"])

    def test_abandoned_assembly(self):
        events = sample_events()
        events[-1]["type"] = "assembly_abandoned"
        self.assertEqual(self.analyzer.summary(events, "abandoned")["outcome"], "abandoned")

    def test_missing_event_is_a_discrepancy(self):
        events = [e for e in sample_events() if e["sequence"] != 2]   # una falla menos
        summary = self.analyzer.summary(events, "completed")
        self.assertFalse(summary["consistent"])
        self.assertEqual(summary["discrepancies"],
                         [{"field": "failed_attempts", "client": 8, "events": 7}])
        # El valor informado es el del cliente
        self.assertEqual(summary["failed_attempts"], 8)

    def test_incorrect_joint_from_events(self):
        events = [e for e in sample_events() if e["type"] != "assembly_checked"]
        for e in events:
            if e["sequence"] == 21:   # la última unión, que queda vigente
                e["data"]["expected"] = False
        summary = self.analyzer.summary(events, "abandoned")
        self.assertEqual(summary["incorrect_joints"], 1)
        self.assertTrue(summary["completed"])
        self.assertFalse(summary["correct"])

    def test_seconds_tolerate_rounding(self):
        events = sample_events()
        events[-1]["data"]["help_seconds"] = 3.2   # suma sin redondear del cliente: 3.15
        self.assertTrue(self.analyzer.summary(events, "completed")["consistent"])

    def test_no_events(self):
        self.assertEqual(self.analyzer.context([]), {})
        summary = self.analyzer.summary([], "abandoned")
        self.assertEqual(summary["source"], "events")
        self.assertIsNone(summary["joints_total"])
        self.assertFalse(summary["completed"])
        self.assertIsNone(summary["duration_seconds"])
        self.assertIsNone(summary["time_to_first_joint_seconds"])
