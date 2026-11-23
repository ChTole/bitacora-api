from django.urls import path

from . import views

app_name = "telemetry"

# Rutas sin barra final, como en el contrato (/v1/health)
urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
]
