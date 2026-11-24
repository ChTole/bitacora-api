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
