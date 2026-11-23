"""
Alias de las sesiones: un animal y un adjetivo o color, por ejemplo "Carpincho Turquesa".
Ver la sección Alias de API.md y de docs/modelo-de-datos.md.
"""

import random
from datetime import timedelta

ANIMALS = [
    "Carpincho", "Hornero", "Yaguareté", "Ñandú", "Guanaco", "Tatú", "Pingüino", "Puma",
    "Zorro", "Cóndor", "Vicuña", "Mara", "Coatí", "Tero", "Benteveo", "Lechuza",
]

# Adjetivos y colores que no cambian con el género del animal
QUALITIES = [
    "Turquesa", "Violeta", "Celeste", "Naranja", "Verde", "Azul", "Gris", "Rosa",
    "Veloz", "Valiente", "Audaz", "Amable", "Feliz", "Paciente", "Alegre", "Sutil",
]

COMBINATIONS = [f"{animal} {quality}" for animal in ANIMALS for quality in QUALITIES]

# Período en el que no se repite un alias dentro de una simulación
RECENT_DAYS = 30


def pick_alias(sessions, simulation_id, now, rng=random):
    """Elige un alias que no se haya usado en las sesiones recientes de la simulación."""
    since = now - timedelta(days=RECENT_DAYS)
    used = set(sessions.distinct("alias", {"simulation_id": simulation_id, "started_at": {"$gte": since}}))

    free = [alias for alias in COMBINATIONS if alias not in used]
    if free:
        return rng.choice(free)

    # Combinaciones agotadas: se agrega un número, como indica el contrato
    for _ in range(100):
        candidate = f"{rng.choice(COMBINATIONS)} {rng.randint(2, 99)}"
        if candidate not in used:
            return candidate
    return f"{rng.choice(COMBINATIONS)} {rng.randint(100, 9999)}"
