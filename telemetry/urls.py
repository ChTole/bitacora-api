from django.urls import path

from . import views

app_name = "telemetry"

# Rutas sin barra final, como en el contrato (/v1/health)
urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
    path("sessions", views.SessionCreateView.as_view(), name="session-create"),
    path("sessions/<str:session_id>/events", views.SessionEventsView.as_view(), name="session-events"),
    path("sessions/<str:session_id>/finish", views.SessionFinishView.as_view(), name="session-finish"),
]
