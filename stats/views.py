from django.utils.cache import patch_cache_control
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from telemetry import store
from telemetry.models import Simulation
from telemetry.utils import to_iso, utc_now

from . import aggregations
from .exceptions import SimulationNotFound
from .filters import parse_filters

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
