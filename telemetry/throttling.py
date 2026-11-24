"""Límite de solicitudes por IP, con la IP real del cliente detrás del proxy de Render."""

import logging

from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle

logger = logging.getLogger(__name__)
_missing_header_logged = False


class ClientIpRateThrottle(ScopedRateThrottle):
    """
    ScopedRateThrottle que identifica al cliente por settings.CLIENT_IP_HEADER.

    DRF usa por defecto X-Forwarded-For, pero el proxy de Render no lo limpia: solo le agrega
    entradas, así que un cliente podría enviar uno falso y esquivar el límite.
    """

    def get_ident(self, request):
        global _missing_header_logged
        header = settings.CLIENT_IP_HEADER
        if header:
            value = request.META.get(header, "").split(",")[0].strip()
            if value:
                return value
            # Sin el encabezado, todos los clientes compartirían el límite: se avisa una vez en los logs
            if not _missing_header_logged:
                _missing_header_logged = True
                logger.warning("No llegó el encabezado %s: el límite de solicitudes usa REMOTE_ADDR.", header)
        return request.META.get("REMOTE_ADDR")
