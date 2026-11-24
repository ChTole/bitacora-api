from django.urls import path

from . import views

app_name = "stats"

SIMULATION = "simulations/<slug:simulation_id>"

# Rutas sin barra final, como en el contrato de Bitácora
urlpatterns = [
    path("simulations", views.SimulationListView.as_view(), name="simulations"),
    path("simulations/<slug:simulation_id>/summary", views.SummaryView.as_view(), name="summary"),
    path(f"{SIMULATION}/timeline", views.TimelineView.as_view(), name="timeline"),
    path(f"{SIMULATION}/failures", views.FailuresView.as_view(), name="failures"),
    path(f"{SIMULATION}/sessions", views.SessionListView.as_view(), name="sessions"),
    path(f"{SIMULATION}/sessions/<str:session_pk>", views.SessionDetailView.as_view(), name="session-detail"),
]
