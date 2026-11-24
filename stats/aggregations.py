"""
Agregaciones de métricas sobre la colección sessions. Ver docs/api-tablero.md (Métricas generales).

MongoDB cuenta y junta los valores en un solo $group; los cuartiles se calculan en Python
sobre los valores ya filtrados, que a esta escala son pocos miles como máximo.
"""

import statistics
from collections import Counter

from telemetry.store import sessions_collection

# Condiciones de cada grupo de sesiones (ver la tabla de métricas en api-tablero.md)
CLOSED = {"$ne": ["$status", "active"]}
CHECKED = {"$and": [CLOSED, {"$eq": ["$summary.outcome", "checked"]}]}
CORRECT = {"$and": [CHECKED, {"$eq": ["$summary.correct", True]}]}
USED_HELP = {"$gt": ["$summary.help_requests", 0]}


def _count(condition):
    return {"$sum": {"$cond": [condition, 1, 0]}}


def _values(condition, field):
    return {"$push": {"$cond": [condition, f"$summary.{field}", None]}}


def _and(*conditions):
    return {"$and": list(conditions)}


def summarize(match, group_field=None):
    """
    Bloques de sesiones y métricas: [(clave, {"sessions": ..., "metrics": ...})].
    Sin group_field, un solo bloque con clave None.
    """
    group = {
        "_id": f"$context.{group_field}" if group_field else None,
        "total": {"$sum": 1},
        "active": _count({"$eq": ["$status", "active"]}),
        "completed": _count({"$eq": ["$status", "completed"]}),
        "abandoned": _count({"$eq": ["$status", "abandoned"]}),
        "closed": _count(CLOSED),
        "checked": _count(CHECKED),
        "correct": _count(CORRECT),
        "help_used": _count(_and(CLOSED, USED_HELP)),
        "checked_with_help": _count(_and(CHECKED, USED_HELP)),
        "correct_with_help": _count(_and(CORRECT, USED_HELP)),
        "inconsistent": _count(_and(CLOSED, {"$eq": ["$summary.consistent", False]})),
        "durations": _values(CORRECT, "duration_seconds"),
        "failed_attempts": _values(CHECKED, "failed_attempts"),
        "help_seconds": _values(_and(CLOSED, USED_HELP), "help_seconds"),
        "reasons": _values(CLOSED, "failures_by_reason"),
    }
    rows = list(sessions_collection().aggregate([{"$match": match}, {"$group": group}]))

    if group_field is None:
        return [(None, _block(rows[0] if rows else {}))]

    # Las sesiones sin ese dato de contexto no forman un grupo
    rows = [row for row in rows if row["_id"] is not None]
    rows.sort(key=lambda row: (-row["total"], str(row["_id"])))
    return [(row["_id"], _block(row)) for row in rows]


def _block(row):
    get = lambda key: row.get(key, 0)  # noqa: E731
    closed, checked, correct = get("closed"), get("checked"), get("correct")
    checked_with_help = get("checked_with_help")
    checked_without_help = checked - checked_with_help

    return {
        "sessions": {
            "total": get("total"),
            "active": get("active"),
            "completed": get("completed"),
            "abandoned": get("abandoned"),
            "outcomes": {
                "correct": correct,
                "incorrect": checked - correct,
                "not_checked": closed - checked,
            },
        },
        "metrics": {
            "finish_rate": _rate(checked, closed),
            "correct_rate": _rate(correct, checked),
            "duration_seconds": _quartiles(row.get("durations", [])),
            "failed_attempts": _quartiles(row.get("failed_attempts", [])),
            "failures_by_reason": _sum_reasons(row.get("reasons", [])),
            "help": {
                "usage_rate": _rate(get("help_used"), closed),
                "median_seconds": _quartiles(row.get("help_seconds", []))["median"],
                "correct_rate_with_help": _rate(get("correct_with_help"), checked_with_help),
                "correct_rate_without_help": _rate(correct - get("correct_with_help"), checked_without_help),
            },
            "inconsistent_sessions": get("inconsistent"),
        },
    }


def _rate(part, total):
    return round(part / total, 3) if total else None


def _numbers(values):
    return [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _quartiles(values):
    values = sorted(_numbers(values))
    if not values:
        return {"median": None, "p25": None, "p75": None, "sessions": 0}
    if len(values) == 1:
        p25 = median = p75 = values[0]
    else:
        # "inclusive" interpola entre los valores, como la mayoría de las planillas de cálculo
        p25, median, p75 = statistics.quantiles(values, n=4, method="inclusive")
    return {"median": round(median, 1), "p25": round(p25, 1), "p75": round(p75, 1), "sessions": len(values)}


def _sum_reasons(values):
    total = Counter()
    for reasons in values:
        if isinstance(reasons, dict):
            total.update({reason: count for reason, count in reasons.items() if isinstance(count, int)})
    return dict(total.most_common())


def simulations_overview():
    """Cantidad de sesiones y última sesión de cada simulación."""
    rows = sessions_collection().aggregate([
        {"$group": {"_id": "$simulation_id", "sessions": {"$sum": 1}, "last_session_at": {"$max": "$started_at"}}},
    ])
    return {row["_id"]: row for row in rows}
