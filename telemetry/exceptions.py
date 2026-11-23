"""
Errores con el formato del contrato de Bitácora:

    { "error": { "code": "session_finished", "message": "La sesión ya fue cerrada." } }
"""

import logging

from django.conf import settings
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ContractError(exceptions.APIException):
    """Error del contrato: default_code es el 'code' de la respuesta."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid_request"
    default_detail = "Datos con formato incorrecto."


class InvalidRequest(ContractError):
    pass


class InvalidApiKey(ContractError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "invalid_api_key"
    default_detail = "Clave ausente o incorrecta."


class SessionNotFound(ContractError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "session_not_found"
    default_detail = "La sesión no existe."


class SessionFinished(ContractError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "session_finished"
    default_detail = "La sesión ya fue cerrada."


class SessionFull(ContractError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "session_full"
    default_detail = "La sesión alcanzó el límite de eventos."


class BatchTooLarge(ContractError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_code = "batch_too_large"
    default_detail = "El lote supera el máximo de eventos."


# Errores propios de DRF, traducidos a códigos del contrato
_DRF_CODES = [
    ((exceptions.AuthenticationFailed, exceptions.NotAuthenticated), "invalid_api_key", "Clave ausente o incorrecta."),
    ((exceptions.ValidationError, exceptions.ParseError, exceptions.UnsupportedMediaType), "invalid_request", None),
    ((exceptions.Throttled,), "rate_limited", "Demasiadas solicitudes."),
    ((exceptions.NotFound,), "not_found", "La ruta no existe."),
    ((exceptions.MethodNotAllowed,), "method_not_allowed", "Método no permitido en esta ruta."),
]


def contract_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        # Error no previsto. En desarrollo se deja a Django, que muestra el detalle.
        if settings.DEBUG:
            return None
        logger.exception("Error no controlado en %s", context.get("view"))
        return Response({"error": {"code": "server_error", "message": "Error del servidor."}},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if isinstance(exc, ContractError):
        code, message = exc.default_code, _first_message(exc.detail)
    else:
        code, message = "error", _first_message(response.data)
        for types, contract_code, fixed_message in _DRF_CODES:
            if isinstance(exc, types):
                code, message = contract_code, fixed_message or message
                break
        if isinstance(exc, exceptions.NotAuthenticated):
            response.status_code = status.HTTP_401_UNAUTHORIZED

    response.data = {"error": {"code": code, "message": message}}
    return response


def _first_message(detail, path=""):
    """Primer mensaje de un detalle de DRF, con la ruta del campo si la hay ('events.0.type: ...')."""
    if isinstance(detail, dict):
        for key, value in detail.items():
            if key == "detail":
                return _first_message(value, path)
            return _first_message(value, f"{path}.{key}" if path else str(key))
    if isinstance(detail, list) and detail:
        if all(not isinstance(item, (dict, list)) for item in detail):
            return _first_message(detail[0], path)
        for index, item in enumerate(detail):
            if item:
                return _first_message(item, f"{path}.{index}" if path else str(index))
    text = str(detail)
    return f"{path}: {text}" if path else text
