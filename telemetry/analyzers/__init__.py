"""
Analizadores por simulación. Ver docs/modelo-de-datos.md (Analizadores por simulación).

Un analizador calcula, al cerrar una sesión, su contexto y su resumen a partir de los eventos.
Las simulaciones sin analizador guardan sus sesiones igual, con context vacío y summary en null.
"""

from .base import Analyzer
from .assembly_workshop import AssemblyWorkshopAnalyzer

# simulation_id → analizador
ANALYZERS = {
    "taller-ensamblado": AssemblyWorkshopAnalyzer(),
}


def get_analyzer(simulation_id):
    return ANALYZERS.get(simulation_id)


__all__ = ["Analyzer", "ANALYZERS", "get_analyzer"]
