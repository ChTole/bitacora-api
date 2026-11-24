"""
Validador $jsonSchema de la colección sessions e índice por mueble del Taller.
Ver docs/modelo-de-datos.md (Validación e Índices).

Se aplican con PyMongo porque Django no tiene operaciones para ninguno de los dos:
el validador es propio de MongoDB y el índice es sobre un campo dentro de un JSONField.
"""

from django.db import migrations

COLLECTION = "sessions"

INT = ["int", "long"]
DATE = "date"

SESSION_SCHEMA = {
    "bsonType": "object",
    "required": ["session_id", "simulation_id", "alias", "status", "started_at", "last_activity_at",
                 "event_count", "discarded_count", "events"],
    "properties": {
        "session_id": {"bsonType": "string"},
        "simulation_id": {"bsonType": "string"},
        "alias": {"bsonType": "string"},
        "participant": {"bsonType": ["object", "null"]},
        "status": {"enum": ["active", "completed", "abandoned"]},
        "started_at": {"bsonType": DATE},
        "finished_at": {"bsonType": [DATE, "null"]},
        "closed_by": {"enum": ["client", "server", None]},
        "last_activity_at": {"bsonType": DATE},
        "event_count": {"bsonType": INT, "minimum": 0, "maximum": 2000},
        "discarded_count": {"bsonType": INT, "minimum": 0},
        "context": {"bsonType": "object"},
        "summary": {"bsonType": ["object", "null"]},
        "summary_version": {"bsonType": INT + ["null"]},
        "events": {
            "bsonType": "array",
            "maxItems": 2000,
            "items": {
                "bsonType": "object",
                "required": ["sequence", "timestamp", "received_at", "type"],
                "properties": {
                    "sequence": {"bsonType": INT, "minimum": 1},
                    "timestamp": {"bsonType": DATE},
                    "received_at": {"bsonType": DATE},
                    "type": {"bsonType": "string", "maxLength": 64},
                    "data": {"bsonType": ["object", "null"]},
                },
            },
        },
    },
}

# Índice parcial: solo incluye las sesiones del Taller, que son las que tienen context.furniture_id
WORKSHOP_INDEX = "session_workshop_furniture"
WORKSHOP_INDEX_KEYS = [("context.furniture_id", 1), ("started_at", -1)]
WORKSHOP_INDEX_FILTER = {"simulation_id": "taller-ensamblado"}


def apply(apps, schema_editor):
    database = schema_editor.connection.database
    database.command("collMod", COLLECTION, validator={"$jsonSchema": SESSION_SCHEMA},
                     validationLevel="strict", validationAction="error")
    database[COLLECTION].create_index(WORKSHOP_INDEX_KEYS, name=WORKSHOP_INDEX,
                                      partialFilterExpression=WORKSHOP_INDEX_FILTER)


def revert(apps, schema_editor):
    database = schema_editor.connection.database
    database[COLLECTION].drop_index(WORKSHOP_INDEX)
    database.command("collMod", COLLECTION, validator={}, validationLevel="off")


class Migration(migrations.Migration):
    dependencies = [
        ("telemetry", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply, revert),
    ]
