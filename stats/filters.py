"""Filtros de los endpoints de métricas. Ver docs/api-tablero.md (Filtros)."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from rest_framework import serializers

GROUP_BY_FIELDS = ("furniture_id", "mobile", "app_version")


class BoundField(serializers.Field):
    """Fecha (AAAA-MM-DD, en UTC) o fecha y hora ISO 8601. Devuelve (texto original, datetime en UTC)."""

    default_error_messages = {"invalid": "Debe ser una fecha AAAA-MM-DD o una fecha y hora ISO 8601."}

    def __init__(self, *, end_of_day=False, **kwargs):
        self.end_of_day = end_of_day
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        text = str(data).strip()
        try:
            if len(text) == 10:
                day = date.fromisoformat(text)
                if self.end_of_day:
                    # "hasta" es inclusive: se toma hasta el comienzo del día siguiente
                    day += timedelta(days=1)
                return text, datetime.combine(day, time.min, tzinfo=timezone.utc)
            value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            self.fail("invalid")
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return text, value.astimezone(timezone.utc)

    def to_representation(self, value):
        return value


class FiltersSerializer(serializers.Serializer):
    furniture_id = serializers.CharField(required=False, max_length=64)
    mobile = serializers.BooleanField(required=False, default=None, allow_null=True)
    app_version = serializers.CharField(required=False, max_length=32)
    # "from" es palabra reservada en Python: se declara en __init__
    to = BoundField(required=False, end_of_day=True)
    group_by = serializers.ChoiceField(required=False, choices=GROUP_BY_FIELDS)

    def __init__(self, *args, allow_group_by=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from"] = BoundField(required=False)
        if not allow_group_by:
            del self.fields["group_by"]


@dataclass
class Filters:
    furniture_id: str = None
    mobile: bool = None
    app_version: str = None
    from_: tuple = None   # (texto, datetime)
    to: tuple = None
    group_by: str = None

    def echo(self):
        """Los filtros aplicados, para incluirlos en la respuesta."""
        return {
            "furniture_id": self.furniture_id,
            "mobile": self.mobile,
            "app_version": self.app_version,
            "from": self.from_[0] if self.from_ else None,
            "to": self.to[0] if self.to else None,
        }

    def match(self, simulation_id):
        """Condición $match de MongoDB para estas sesiones."""
        query = {"simulation_id": simulation_id}
        for field in ("furniture_id", "mobile", "app_version"):
            value = getattr(self, field)
            if value is not None:
                query[f"context.{field}"] = value
        started = {}
        if self.from_:
            started["$gte"] = self.from_[1]
        if self.to:
            started["$lt"] = self.to[1]
        if started:
            query["started_at"] = started
        return query


def parse_filters(query_params, allow_group_by=False):
    # .dict(): con un QueryDict, DRF toma un booleano ausente como False, y "mobile" sin valor debe ser None
    data = query_params.dict() if hasattr(query_params, "dict") else dict(query_params)
    serializer = FiltersSerializer(data=data, allow_group_by=allow_group_by)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    data["from_"] = data.pop("from", None)
    return Filters(**data)

