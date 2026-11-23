from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import ApiKeyAuthentication, HasSimulationKey


class ContractView(APIView):
    """Base de los endpoints del contrato: todos requieren la clave de una simulación."""

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasSimulationKey]


class HealthView(ContractView):
    """GET /v1/health"""

    def get(self, request):
        return Response({"status": "ok"})
