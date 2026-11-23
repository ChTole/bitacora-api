"""Validación de las solicitudes del contrato. Ver API.md."""

import json
import re
from datetime import datetime

from rest_framework import serializers

from .contract import MAX_DATA_BYTES, MAX_TYPE_LENGTH

PARTICIPANT_TYPES = ("email", "full_name", "document_id")
MAX_PARTICIPANT_LENGTH = 200
TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ParticipantField(serializers.Field):
    """null, o { "type": ..., "value": ... } con un tipo del contrato."""

    default_error_messages = {
        "invalid": "Debe ser null o {{ type, value }}, con type entre: " + ", ".join(PARTICIPANT_TYPES) + ".",
    }

    def to_internal_value(self, data):
        if not isinstance(data, dict) or data.get("type") not in PARTICIPANT_TYPES:
            self.fail("invalid")
        value = data.get("value")
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_PARTICIPANT_LENGTH:
            self.fail("invalid")
        return {"type": data["type"], "value": value.strip()}

    def to_representation(self, value):
        return value


class SessionCreateSerializer(serializers.Serializer):
    simulation_id = serializers.CharField(max_length=64)
    participant = ParticipantField(required=False, allow_null=True, default=None)


class SequenceField(serializers.Field):
    """Entero desde 1. A diferencia de IntegerField, no acepta texto ("5") ni booleanos."""

    default_error_messages = {"invalid": "Debe ser un entero desde 1."}

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int) or data < 1:
            self.fail("invalid")
        return data

    def to_representation(self, value):
        return value


class UtcTimestampField(serializers.Field):
    """Fecha ISO 8601 en UTC, terminada en Z."""

    default_error_messages = {"invalid": "Debe ser una fecha ISO 8601 en UTC, por ejemplo 2026-10-23T14:05:12.345Z."}

    def to_internal_value(self, data):
        if not isinstance(data, str) or not data.endswith("Z"):
            self.fail("invalid")
        try:
            return datetime.fromisoformat(data[:-1] + "+00:00")
        except ValueError:
            self.fail("invalid")

    def to_representation(self, value):
        return value


class EventDataField(serializers.Field):
    """Objeto JSON o null, de hasta 4 KB."""

    default_error_messages = {
        "invalid": "Debe ser un objeto JSON o null.",
        "too_large": f"Supera los {MAX_DATA_BYTES} bytes.",
    }

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            self.fail("invalid")
        size = len(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if size > MAX_DATA_BYTES:
            self.fail("too_large")
        return data

    def to_representation(self, value):
        return value


class EventSerializer(serializers.Serializer):
    sequence = SequenceField()
    timestamp = UtcTimestampField()
    type = serializers.RegexField(
        TYPE_PATTERN,
        max_length=MAX_TYPE_LENGTH,
        error_messages={"invalid": f"Debe estar en snake_case, hasta {MAX_TYPE_LENGTH} caracteres."},
    )
    data = EventDataField(required=False, allow_null=True, default=None)


class EventBatchSerializer(serializers.Serializer):
    events = EventSerializer(many=True, allow_empty=True)


class FinishSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["completed", "abandoned"])
