"""
Acceso a la colección sessions con PyMongo.

El registro de eventos y el cierre necesitan actualizaciones condicionales y atómicas,
que el ORM no permite (ver docs/modelo-de-datos.md, Registro de un lote y Cierre).
Los documentos tienen la misma forma que el modelo Session, así que el ORM y el admin los leen igual.
"""

from dataclasses import dataclass
from datetime import timedelta, timezone

from bson.codec_options import CodecOptions
from django.db import connection

from . import contract
from .aliases import pick_alias
from .analyzers import get_analyzer
from .exceptions import ConcurrencyConflict, SessionFinished, SessionFull, SessionNotFound
from .models import Session
from .utils import utc_now

# Intentos de una escritura condicional antes de responder 503 (el cliente reintenta)
MAX_WRITE_ATTEMPTS = 5

_CODEC_OPTIONS = CodecOptions(tz_aware=True, tzinfo=timezone.utc)


def sessions_collection():
    # Se pide en cada uso: en los tests, la conexión cambia a la base de prueba
    return connection.get_collection(Session._meta.db_table, codec_options=_CODEC_OPTIONS)


# ───────────── Crear ─────────────

def create_session(simulation_id, participant):
    sessions = sessions_collection()
    now = utc_now()
    document = {
        "session_id": Session._meta.get_field("session_id").get_default(),
        "simulation_id": simulation_id,
        "alias": pick_alias(sessions, simulation_id, now),
        "participant": participant,
        "status": Session.Status.ACTIVE,
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
    sessions.insert_one(document)
    return document


# ───────────── Registrar un lote ─────────────

@dataclass
class BatchResult:
    accepted: int
    duplicates: int
    discarded: int


def add_events(simulation_id, session_id, events):
    """
    Registra un lote ya validado. events: dicts con sequence, timestamp (datetime), type y data.
    Lectura, separación de duplicados, límite y escritura condicional por event_count.
    """
    sessions = sessions_collection()
    query = {"session_id": session_id, "simulation_id": simulation_id}

    for _ in range(MAX_WRITE_ATTEMPTS):
        current = sessions.find_one(query, {"status": 1, "event_count": 1, "events.sequence": 1})
        if current is None:
            raise SessionNotFound()
        if current["status"] != Session.Status.ACTIVE:
            raise SessionFinished()

        # Duplicados: sequence ya registrado en la sesión o repetido dentro del lote
        known = {event["sequence"] for event in current.get("events", [])}
        new_events, duplicates = [], 0
        for event in events:
            if event["sequence"] in known:
                duplicates += 1
                continue
            known.add(event["sequence"])
            new_events.append(event)

        if not new_events:
            return BatchResult(accepted=0, duplicates=duplicates, discarded=0)

        # Límite por sesión: se aceptan los de menor sequence hasta completar el espacio
        count = current["event_count"]
        room = max(0, contract.MAX_SESSION_EVENTS - count)
        if room == 0:
            raise SessionFull()

        new_events.sort(key=lambda event: event["sequence"])
        to_store = new_events[:room]
        discarded = len(new_events) - len(to_store)

        now = utc_now()
        documents = [
            {
                "sequence": event["sequence"],
                "timestamp": event["timestamp"],
                "received_at": now,
                "type": event["type"],
                "data": event.get("data"),
            }
            for event in to_store
        ]

        result = sessions.update_one(
            {**query, "status": Session.Status.ACTIVE, "event_count": count},
            {
                "$push": {"events": {"$each": documents, "$sort": {"sequence": 1}}},
                "$inc": {"event_count": len(documents), "discarded_count": discarded},
                "$set": {"last_activity_at": now},
            },
        )
        if result.matched_count == 1:
            return BatchResult(accepted=len(documents), duplicates=duplicates, discarded=discarded)
        # Otra solicitud modificó la sesión entre la lectura y la escritura: se vuelve a leer

    raise ConcurrencyConflict()


# ───────────── Cerrar ─────────────

def finish_session(simulation_id, session_id, status):
    """Cierre pedido por Bitácora. Si la sesión ya estaba cerrada, devuelve los datos del primer cierre."""
    sessions = sessions_collection()
    query = {"session_id": session_id, "simulation_id": simulation_id}

    for _ in range(MAX_WRITE_ATTEMPTS):
        current = sessions.find_one(query)
        if current is None:
            raise SessionNotFound()
        if current["status"] != Session.Status.ACTIVE:
            return current

        changes = _closing_changes(current, status, Session.ClosedBy.CLIENT, finished_at=utc_now())
        result = sessions.update_one(
            {**query, "status": Session.Status.ACTIVE, "event_count": current["event_count"]},
            {"$set": changes},
        )
        if result.matched_count == 1:
            return {**current, **changes}
        # Llegó un lote o se cerró en el medio: se vuelve a leer para que el resumen incluya todo

    raise ConcurrencyConflict()


# ───────────── Cerrar por inactividad ─────────────

# Una sesión activa sin solicitudes durante este tiempo se considera abandonada
INACTIVITY_TIMEOUT = timedelta(hours=2)

# Sesiones que se cierran como máximo en cada llamada, para acotar la demora de una consulta
INACTIVE_BATCH = 100


def close_inactive_sessions(timeout=INACTIVITY_TIMEOUT, now=None, limit=INACTIVE_BATCH):
    """
    Cierra como abandoned, con closed_by: server, las sesiones activas sin actividad desde hace más de
    timeout. Por ejemplo, las de una pestaña que se cerró. Devuelve la cantidad de sesiones cerradas.

    finished_at es la última actividad: es cuando la sesión terminó en realidad, no cuando se detectó.
    """
    sessions = sessions_collection()
    cutoff = (now or utc_now()) - timeout
    idle = {"status": Session.Status.ACTIVE, "last_activity_at": {"$lt": cutoff}}

    closed = 0
    for candidate in sessions.find(idle, {"_id": 1}).limit(limit):
        # Se lee completa para calcular el resumen. Si ya no está inactiva, se saltea.
        current = sessions.find_one({"_id": candidate["_id"], **idle})
        if current is None:
            continue

        changes = _closing_changes(current, Session.Status.ABANDONED, Session.ClosedBy.SERVER,
                                   finished_at=current["last_activity_at"])
        # Mismo filtro condicional que un cierre normal, más la inactividad: si llegó un lote
        # en el medio, la sesión volvió a estar activa y no se cierra.
        result = sessions.update_one(
            {"_id": current["_id"], **idle, "event_count": current["event_count"]},
            {"$set": changes},
        )
        closed += result.modified_count
    return closed


def _closing_changes(session, status, closed_by, finished_at):
    changes = {
        "status": status,
        "finished_at": finished_at,
        "closed_by": closed_by,
    }
    if closed_by == Session.ClosedBy.CLIENT:
        changes["last_activity_at"] = finished_at
    analyzer = get_analyzer(session["simulation_id"])
    if analyzer is not None:
        events = session.get("events", [])
        changes["context"] = analyzer.context(events)
        changes["summary"] = analyzer.summary(events, status)
        changes["summary_version"] = analyzer.version
    return changes
