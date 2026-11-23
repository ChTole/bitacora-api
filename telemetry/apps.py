from django.apps import AppConfig


class TelemetryConfig(AppConfig):
    default_auto_field = "django_mongodb_backend.fields.ObjectIdAutoField"
    name = "telemetry"
    verbose_name = "Telemetría"
