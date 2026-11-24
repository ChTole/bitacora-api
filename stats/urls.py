from django.urls import path

from . import views

app_name = "stats"

# Rutas sin barra final, como en el contrato de Bitácora
urlpatterns = [
    path("simulations", views.SimulationListView.as_view(), name="simulations"),
    path("simulations/<slug:simulation_id>/summary", views.SummaryView.as_view(), name="summary"),
]
