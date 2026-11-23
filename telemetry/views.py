from dataclasses import asdict

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import store
from .authentication import ApiKeyAuthentication, HasSimulationKey
from .contract import MAX_BATCH_EVENTS
from .exceptions import BatchTooLarge, InvalidApiKey, InvalidRequest
from .serializers import EventBatchSerializer, FinishSerializer, SessionCreateSerializer
from .utils import to_iso


class ContractView(APIView):
    """Base de los endpoints del contrato: todos requieren la clave de una simulación."""

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasSimulationKey]

    @property
    def simulation_id(self):
        return self.request.auth.simulation_id


class HealthView(ContractView):
    """GET /v1/health"""

    def get(self, request):
        return Response({"status": "ok"})


class SessionCreateView(ContractView):
    """POST /v1/sessions"""

    def post(self, request):
        serializer = SessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # La clave solo permite crear sesiones de su propia simulación
        if data["simulation_id"] != self.simulation_id:
            raise InvalidApiKey("La clave no corresponde a esta simulación.")

        session = store.create_session(self.simulation_id, data["participant"])
        return Response(
            {
                "session_id": session["session_id"],
                "alias": session["alias"],
                "started_at": to_iso(session["started_at"]),
            },
            status=status.HTTP_201_CREATED,
        )


class SessionEventsView(ContractView):
    """POST /v1/sessions/{session_id}/events"""

    def post(self, request, session_id):
        events = request.data.get("events") if isinstance(request.data, dict) else None
        if not isinstance(events, list):
            raise InvalidRequest("El cuerpo debe tener una lista events.")
        if len(events) > MAX_BATCH_EVENTS:
            raise BatchTooLarge(f"Un lote admite hasta {MAX_BATCH_EVENTS} eventos.")

        serializer = EventBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = store.add_events(self.simulation_id, session_id, serializer.validated_data["events"])
        return Response(asdict(result))


class SessionFinishView(ContractView):
    """POST /v1/sessions/{session_id}/finish"""

    def post(self, request, session_id):
        serializer = FinishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = store.finish_session(self.simulation_id, session_id, serializer.validated_data["status"])
        return Response(
            {
                "session_id": session["session_id"],
                "status": session["status"],
                "finished_at": to_iso(session["finished_at"]),
            }
        )