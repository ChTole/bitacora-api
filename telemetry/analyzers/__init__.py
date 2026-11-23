"""
Analizadores por simulación. Ver docs/modelo-de-datos.md (Analizadores por simulación).

Un analizador calcula, al cerrar una sesión, su contexto y su resumen a partir de los eventos.
Las simulaciones sin analizador guardan sus sesiones igual, con context vacío y summary en null.
"""


class Analyzer:
    """Base de los analizadores. Cada simulación define el suyo."""

    # Versión del cálculo: se guarda en summary_version
    version = 1

    def context(self, events):
        """Datos para filtrar y agrupar en el tablero."""
        return {}

    def summary(self, events, status):
        """Métricas de la sesión. status es el estado de cierre: completed o abandoned."""
        return None


# simulation_id → analizador
ANALYZERS = {}


def get_analyzer(simulation_id):
    return ANALYZERS.get(simulation_id)
