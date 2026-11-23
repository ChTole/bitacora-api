from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission

from .exceptions import InvalidApiKey
from .models import Simulation, hash_api_key


class ApiKeyAuthentication(BaseAuthentication):
    """
    Autenticación por el encabezado X-Api-Key del contrato.
    La clave identifica a una simulación: queda disponible en request.auth.
    """

    def authenticate(self, request):
        raw_key = request.META.get("HTTP_X_API_KEY")
        if not raw_key:
            raise InvalidApiKey()

        simulation = Simulation.objects.filter(api_key_hash=hash_api_key(raw_key), is_active=True).first()
        if simulation is None:
            raise InvalidApiKey()

        # No hay usuario: quien llama es una simulación
        return (None, simulation)

    def authenticate_header(self, request):
        # Hace que DRF responda 401 (y no 403) cuando falta la clave
        return "X-Api-Key"


class HasSimulationKey(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, Simulation)
