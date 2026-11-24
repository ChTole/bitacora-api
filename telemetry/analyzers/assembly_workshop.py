"""
Analizador del Taller de Ensamblado. Implementa docs/metricas.md (summary_version 1).

El resumen que envía el Taller en su evento final es la fuente principal; los eventos lo completan
y lo verifican. Sin evento final, el resumen se calcula solo con los eventos.
"""

from collections import Counter

from .base import Analyzer

FINAL_EVENTS = {"assembly_checked": "checked", "assembly_abandoned": "abandoned"}

# Campos que existen en el resumen del cliente y también se pueden calcular desde los eventos
COMPARED_COUNTS = ["joints_total", "joints_completed", "incorrect_joints", "failed_attempts",
                   "undos", "detaches", "help_requests", "controls_views"]
COMPARED_SECONDS = {"help_seconds": "help_requests", "controls_seconds": "controls_views"}

# Campos que se toman del resumen del cliente
CLIENT_FIELDS = ["completed", "correct", "duration_seconds", "joints_total", "joints_completed",
                 "incorrect_joints", "failed_attempts", "undos", "detaches", "help_requests",
                 "help_seconds", "controls_views", "controls_seconds", "grabs", "rotations"]


class AssemblyWorkshopAnalyzer(Analyzer):
    version = 1

    def context(self, events):
        started = _first(events, "assembly_started")
        if started is None:
            return {}
        data = started.get("data") or {}
        return {
            "furniture_id": data.get("furniture_id"),
            "app_version": data.get("app_version"),
            "mobile": data.get("mobile"),
            "joints_total": data.get("joints"),
        }

    def summary(self, events, status):
        derived = _from_events(events)
        final = _last_final(events)

        if final is None:
            return {
                "source": "events",
                "outcome": "none",
                **derived,
                "grabs": None,
                "rotations": None,
                "consistent": None,
                "discrepancies": None,
            }

        client = final.get("data") or {}
        discrepancies = _compare(client, derived)
        summary = {
            "source": "client",
            "outcome": FINAL_EVENTS[final["type"]],
            **derived,
        }
        for field in CLIENT_FIELDS:
            if field in client:
                summary[field] = client[field]
        summary["consistent"] = not discrepancies
        summary["discrepancies"] = discrepancies
        return summary


def _from_events(events):
    """Resumen calculado solo con los eventos (columna "Desde los eventos" de metricas.md)."""
    started = _first(events, "assembly_started")
    joints_total = (started.get("data") or {}).get("joints") if started else None

    current = {}            # uniones vigentes: (espiga, caja) → expected
    connections = 0
    first_joint_at = None
    undos = detaches = 0
    failures = Counter()
    help_requests = controls_views = 0
    help_seconds = controls_seconds = 0.0
    last_elapsed = None

    for event in events:
        data = event.get("data") or {}
        kind = event.get("type")

        if isinstance(data.get("elapsed_seconds"), (int, float)):
            last_elapsed = data["elapsed_seconds"]

        if kind == "joint_completed":
            connections += 1
            current[(data.get("tenon"), data.get("mortise"))] = bool(data.get("expected", True))
            if first_joint_at is None:
                first_joint_at = data.get("elapsed_seconds")
        elif kind == "joint_undone":
            current.pop((data.get("tenon"), data.get("mortise")), None)
            if data.get("mode") == "detach":
                detaches += 1
            else:
                undos += 1
        elif kind == "joint_attempt_failed":
            failures[data.get("reason") or "unknown"] += 1
        elif kind == "help_viewed":
            help_requests += 1
            help_seconds += data.get("duration_seconds") or 0
        elif kind == "controls_viewed":
            controls_views += 1
            controls_seconds += data.get("duration_seconds") or 0

    joints_completed = len(current)
    incorrect_joints = sum(1 for expected in current.values() if not expected)
    completed = joints_total is not None and joints_completed >= joints_total

    return {
        "completed": completed,
        "correct": completed and incorrect_joints == 0,
        "duration_seconds": _round(last_elapsed),
        "time_to_first_joint_seconds": _round(first_joint_at),
        "joints_total": joints_total,
        "joints_completed": joints_completed,
        "incorrect_joints": incorrect_joints,
        "connections": connections,
        "undos": undos,
        "detaches": detaches,
        "failed_attempts": sum(failures.values()),
        "failures_by_reason": dict(failures),
        "help_requests": help_requests,
        "help_seconds": _round(help_seconds),
        "controls_views": controls_views,
        "controls_seconds": _round(controls_seconds),
    }


def _compare(client, derived):
    """Diferencias entre el resumen del cliente y el cálculo desde los eventos."""
    discrepancies = []

    for field in COMPARED_COUNTS:
        if field in client and client[field] != derived[field]:
            discrepancies.append({"field": field, "client": client[field], "events": derived[field]})

    for field, count_field in COMPARED_SECONDS.items():
        if field not in client:
            continue
        # El cliente redondea la suma; los eventos traen cada duración redondeada.
        # La diferencia admitida es media décima por evento.
        tolerance = 0.05 * max(1, derived[count_field]) + 1e-9
        if abs(client[field] - derived[field]) > tolerance:
            discrepancies.append({"field": field, "client": client[field], "events": derived[field]})

    return discrepancies


def _first(events, kind):
    return next((event for event in events if event.get("type") == kind), None)


def _last_final(events):
    return next((event for event in reversed(events) if event.get("type") in FINAL_EVENTS), None)


def _round(value):
    return None if value is None else round(float(value), 1)
