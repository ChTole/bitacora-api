from datetime import datetime, timezone


def utc_now():
    """Hora actual en UTC, truncada a milisegundos: es la precisión con la que MongoDB guarda las fechas."""
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


def to_iso(value):
    """Fecha en el formato del contrato: ISO 8601 en UTC con milisegundos, por ejemplo 2026-10-23T14:05:12.345Z."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
