import re

from bson import ObjectId
from django.utils.cache import patch_cache_control
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from telemetry import store
from telemetry.analyzers import get_analyzer
from telemetry.analyzers.assembly_workshop import AssemblyWorkshopAnalyzer
from telemetry.exceptions import SessionNotFound
from telemetry.models import Simulation
from telemetry.utils import to_iso, utc_now

from . import aggregations
from .exceptions import NotFoundForSimulation, SimulationNotFound
from .filters import SessionListParams, TimelineParams, parse_filters, parse_params

# Segundos que el navegador y los intermediarios pueden reutilizar una respuesta
CACHE_SECONDS = 60


class StatsView(APIView):
    """
    Base de los endpoints del tablero: públicos, de solo lectura y con límite de solicitudes por IP.
    Antes de responder, cierra las sesiones inactivas para que las métricas las incluyan.
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "stats"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        store.close_inactive_sessions()

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == 200:
            patch_cache_control(response, public=True, max_age=CACHE_SECONDS)
        return response

    def get_simulation(self, simulation_id):
        simulation = Simulation.objects.filter(simulation_id=simulation_id, is_active=True).first()
        if simulation is None:
            raise SimulationNotFound()
        return simulation


class SimulationListView(StatsView):
    """GET /stats/v1/simulations"""

    def get(self, request):
        overview = aggregations.simulations_overview()
        simulations = sorted(Simulation.objects.filter(is_active=True), key=lambda s: s.simulation_id)
        return Response({
            "simulations": [
                {
                    "simulation_id": simulation.simulation_id,
                    "name": simulation.name,
                    "sessions": overview.get(simulation.simulation_id, {}).get("sessions", 0),
                    "last_session_at": to_iso(overview.get(simulation.simulation_id, {}).get("last_session_at")),
                }
                for simulation in simulations
            ]
        })


class SummaryView(StatsView):
    """GET /stats/v1/simulations/{simulation_id}/summary"""

    def get(self, request, simulation_id):
        simulation = self.get_simulation(simulation_id)
        filters = parse_filters(request.query_params, allow_group_by=True)
        match = filters.match(simulation.simulation_id)

        (_, overall), = aggregations.summarize(match)
        body = {
            "simulation_id": simulation.simulation_id,
            "filters": filters.echo(),
            "generated_at": to_iso(utc_now()),
            **overall,
        }
        if filters.group_by:
            body["groups"] = [
                {"key": key, **block}
                for key, block in aggregations.summarize(match, group_field=filters.group_by)
            ]
        return Response(body)


class TimelineView(StatsView):
    """GET /stats/v1/simulations/{simulation_id}/timeline"""

    def get(self, request, simulation_id):
        simulation = self.get_simulation(simulation_id)
        filters = parse_filters(request.query_params)
        tz = parse_params(TimelineParams, request.query_params)["tz"]
        return Response({
            "simulation_id": simulation.simulation_id,
            "tz": tz,
            "days": aggregations.timeline(filters.match(simulation.simulation_id), tz),
        })


class FailuresView(StatsView):
    """GET /stats/v1/simulations/{simulation_id}/failures (propio del Taller)"""

    def get(self, request, simulation_id):
        simulation = self.get_simulation(simulation_id)
        if not isinstance(get_analyzer(simulation.simulation_id), AssemblyWorkshopAnalyzer):
            raise NotFoundForSimulation()
        filters = parse_filters(request.query_params)
        return Response({
            "simulation_id": simulation.simulation_id,
            "mortises": aggregations.mortise_failures(filters.match(simulation.simulation_id)),
        })


# Campos de una sesión que muestra el tablero. Nunca participant ni session_id (ver api-tablero.md, Acceso).
SESSION_FIELDS = {"alias": 1, "status": 1, "closed_by": 1, "started_at": 1, "finished_at": 1,
                  "event_count": 1, "context": 1, "summary": 1}
CLOSED = {"$ne": "active"}


def session_item(document):
    return {
        "id": str(document["_id"]),
        "alias": document["alias"],
        "status": document["status"],
        "closed_by": document.get("closed_by"),
        "started_at": to_iso(document["started_at"]),
        "finished_at": to_iso(document.get("finished_at")),
        "event_count": document.get("event_count", 0),
        "context": document.get("context") or {},
        "summary": document.get("summary"),
    }


class SessionListView(StatsView):
    """GET /stats/v1/simulations/{simulation_id}/sessions"""

    def get(self, request, simulation_id):
        simulation = self.get_simulation(simulation_id)
        filters = parse_filters(request.query_params)
        params = parse_params(SessionListParams, request.query_params)

        query = {**filters.match(simulation.simulation_id), "status": CLOSED}
        if params.get("alias"):
            query["alias"] = {"$regex": f"^{re.escape(params['alias'].strip())}$", "$options": "i"}
        if params.get("before"):
            started = query.setdefault("started_at", {})
            before = params["before"][1]
            started["$lt"] = min(started["$lt"], before) if "$lt" in started else before

        limit = params["limit"]
        documents = list(
            store.sessions_collection().find(query, SESSION_FIELDS).sort("started_at", -1).limit(limit + 1)
        )
        has_more = len(documents) > limit
        documents = documents[:limit]
        return Response({
            "sessions": [session_item(document) for document in documents],
            "next": to_iso(documents[-1]["started_at"]) if has_more else None,
        })


class SessionDetailView(StatsView):
    """GET /stats/v1/simulations/{simulation_id}/sessions/{id}"""

    def get(self, request, simulation_id, session_pk):
        simulation = self.get_simulation(simulation_id)
        if not ObjectId.is_valid(session_pk):
            raise SessionNotFound()
        document = store.sessions_collection().find_one(
            {"_id": ObjectId(session_pk), "simulation_id": simulation.simulation_id, "status": CLOSED},
            {**SESSION_FIELDS, "events": 1},
        )
        if document is None:
            raise SessionNotFound()
        return Response({
            **session_item(document),
            "events": [
                {
                    "sequence": event["sequence"],
                    "timestamp": to_iso(event["timestamp"]),
                    "type": event["type"],
                    "data": event.get("data"),
                }
                for event in document.get("events", [])
            ],
        })
