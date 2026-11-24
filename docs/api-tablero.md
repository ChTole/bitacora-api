# API del tablero

Endpoints de solo lectura que consume el tablero de métricas (ver [005](decisiones/005-tablero-separado.md)). Las métricas se calculan a partir del `summary` y el `context` de cada sesión, según [metricas.md](metricas.md).

**Versión:** 1 (borrador)

## Convenciones

- Todas las rutas comienzan con `/stats/v1`.
- Las respuestas usan JSON y los nombres de los campos usan `snake_case`, igual que el contrato de Bitácora.
- Las fechas usan ISO 8601 en UTC, por ejemplo `2026-11-24T14:05:12.345Z`.
- Las proporciones van de 0 a 1, con tres decimales, por ejemplo `0.742`. Si no hay sesiones para calcularlas, valen `null`.
- Los errores tienen el mismo formato que el contrato de Bitácora: `{ "error": { "code", "message" } }`.

## Acceso

- **Sin clave.** El tablero es público y los datos son anónimos o agregados. Una clave en el tablero sería visible para cualquiera, igual que en una build WebGL, así que no protegería nada.
- **Solo lectura.** Todos los endpoints son `GET`.
- **CORS** limitado al dominio del tablero.
- **Límite de solicitudes por IP.** Si se supera, la respuesta es `429 rate_limited`.
- **Datos personales.** El campo `participant` nunca se incluye en las respuestas, aunque la sesión sea identificada.
- **Identificador público.** Las sesiones se identifican con un `id` propio del tablero, no con el `session_id` del contrato. Con el `session_id` y la clave de la simulación, que es pública, alguien podría enviar eventos a una sesión ajena. Además, los endpoints de sesiones solo muestran sesiones cerradas.

## Antes de cada consulta

Antes de responder, el servidor cierra las sesiones inactivas (ver [modelo de datos](modelo-de-datos.md#cierre-por-inactividad)). Así, las métricas incluyen las sesiones abandonadas al cerrar la pestaña, aunque nadie haya llamado antes al comando.

## Filtros

Los endpoints de métricas aceptan estos parámetros, todos opcionales:

| Parámetro | Ejemplo | Filtra por |
|---|---|---|
| `furniture_id` | `living_room_table` | Mueble (`context.furniture_id`) |
| `mobile` | `true` | Escritorio o móvil (`context.mobile`) |
| `app_version` | `1.1.1` | Versión de la simulación (`context.app_version`) |
| `from` | `2026-11-01` | Sesiones iniciadas desde esa fecha, inclusive |
| `to` | `2026-11-30` | Sesiones iniciadas hasta esa fecha, inclusive |

`from` y `to` aceptan una fecha (`AAAA-MM-DD`, que se interpreta en UTC) o una fecha y hora en ISO 8601. Un filtro con formato incorrecto responde `400 invalid_request`.

Las métricas solo consideran las **sesiones cerradas** (`completed` o `abandoned`). Las activas se informan aparte, en la cantidad de sesiones.

## Endpoints

```
GET /stats/v1/simulations                                      Simulaciones con datos
GET /stats/v1/simulations/{simulation_id}/summary              Métricas generales
GET /stats/v1/simulations/{simulation_id}/timeline             Sesiones por día
GET /stats/v1/simulations/{simulation_id}/failures             Fallas por caja (Taller)
GET /stats/v1/simulations/{simulation_id}/sessions             Sesiones cerradas, la más reciente primero
GET /stats/v1/simulations/{simulation_id}/sessions/{id}        Detalle de una sesión, con sus eventos
```

### Simulaciones

```
GET /stats/v1/simulations
```

Las simulaciones activas, para la página principal del tablero.

**Respuesta `200`**

```json
{
  "simulations": [
    {
      "simulation_id": "taller-ensamblado",
      "name": "Taller de Ensamblado",
      "sessions": 124,
      "last_session_at": "2026-11-24T13:40:02.120Z"
    }
  ]
}
```

### Métricas generales

```
GET /stats/v1/simulations/{simulation_id}/summary
```

Además de los filtros, acepta `group_by`, con `furniture_id`, `mobile` o `app_version`. Con `group_by`, la respuesta agrega las mismas métricas para cada valor.

**Respuesta `200`**

```json
{
  "simulation_id": "taller-ensamblado",
  "filters": { "furniture_id": null, "mobile": null, "app_version": null, "from": null, "to": null },
  "generated_at": "2026-11-24T14:00:00.000Z",
  "sessions": {
    "total": 124, "active": 2, "completed": 95, "abandoned": 27,
    "outcomes": { "correct": 61, "incorrect": 13, "not_checked": 48 }
  },
  "metrics": {
    "finish_rate": 0.746,
    "correct_rate": 0.821,
    "duration_seconds": { "median": 166.3, "p25": 121.0, "p75": 240.5, "sessions": 74 },
    "failed_attempts": { "median": 6, "p25": 3, "p75": 10, "sessions": 91 },
    "failures_by_reason": { "position": 412, "blocked": 133, "orientation": 58, "incompatible": 21 },
    "help": {
      "usage_rate": 0.553,
      "median_seconds": 3.1,
      "correct_rate_with_help": 0.76,
      "correct_rate_without_help": 0.89
    },
    "inconsistent_sessions": 1
  },
  "groups": [
    {
      "key": "living_room_table",
      "sessions": { "total": 60, "active": 1, "completed": 50, "abandoned": 9, "outcomes": { "...": "..." } },
      "metrics": { "...": "las mismas métricas, para este grupo" }
    }
  ]
}
```

`groups` solo aparece con `group_by`, ordenado por cantidad de sesiones.

`sessions.outcomes` reparte las sesiones cerradas según su resultado, y las tres cantidades suman `completed` + `abandoned`:

| Campo | Sesiones |
|---|---|
| `correct` | Comprobadas y correctas (`outcome: checked`, `correct: true`) |
| `incorrect` | Comprobadas, pero con errores o incompletas (`outcome: checked`, `correct: false`) |
| `not_checked` | Cerradas sin comprobar: volvieron al menú, cerraron la pestaña o no tienen resumen |


| Métrica | Cálculo | Sesiones consideradas |
|---|---|---|
| `finish_rate` | Sesiones con `outcome: checked` | Cerradas |
| `correct_rate` | Sesiones con `correct: true` | Con `outcome: checked` |
| `duration_seconds` | Mediana y cuartiles de `duration_seconds` | Con `correct: true` |
| `failed_attempts` | Mediana y cuartiles de `failed_attempts` | Con `outcome: checked` |
| `failures_by_reason` | Suma de `failures_by_reason` | Cerradas |
| `help.usage_rate` | Sesiones con `help_requests` mayor que 0 | Cerradas |
| `help.median_seconds` | Mediana de `help_seconds` | Que usaron la ayuda |
| `help.correct_rate_with_help`, `..._without_help` | `correct_rate`, separado por uso de la ayuda | Con `outcome: checked` |
| `inconsistent_sessions` | Sesiones con `consistent: false` | Cerradas |

Los tiempos usan la mediana y los cuartiles, no el promedio: una sesión que quedó abierta mucho tiempo distorsionaría el promedio. Cada bloque informa en `sessions` cuántas sesiones entraron en el cálculo, para que el tablero pueda advertir cuando son pocas.

### Sesiones por día

```
GET /stats/v1/simulations/{simulation_id}/timeline
```

Además de los filtros, acepta `tz`, una zona horaria IANA para agrupar los días, por ejemplo `America/Argentina/Buenos_Aires`. Por defecto, UTC.

**Respuesta `200`**

```json
{
  "simulation_id": "taller-ensamblado",
  "tz": "America/Argentina/Buenos_Aires",
  "days": [
    { "date": "2026-11-23", "sessions": 12, "checked": 9, "correct": 7 },
    { "date": "2026-11-24", "sessions": 5, "checked": 3, "correct": 3 }
  ]
}
```

Los días sin sesiones no aparecen: el tablero los completa con ceros.

### Fallas por caja

```
GET /stats/v1/simulations/{simulation_id}/failures
```

Las cajas donde más fallan los intentos de encastre, a partir de los eventos `joint_attempt_failed` (ver [Criterios del Taller](metricas.md#criterios-del-taller)). Es propio del Taller: para otras simulaciones responde `404 not_found`. Acepta los filtros; conviene usarlo con `furniture_id`, porque cada mueble tiene sus propias cajas.

**Respuesta `200`**

```json
{
  "simulation_id": "taller-ensamblado",
  "mortises": [
    {
      "mortise": "Table/Mortise_BR",
      "failures": 54,
      "sessions": 31,
      "by_reason": { "position": 40, "blocked": 14 }
    }
  ]
}
```

`sessions` es la cantidad de sesiones con al menos una falla en esa caja. La lista está ordenada por `failures`.

### Sesiones

```
GET /stats/v1/simulations/{simulation_id}/sessions
```

Sesiones cerradas, la más reciente primero. Además de los filtros, acepta:

| Parámetro | Descripción |
|---|---|
| `alias` | Solo las sesiones con ese alias, sin distinguir mayúsculas. Es la búsqueda de "Ver tu sesión". |
| `limit` | Cantidad por página, de 1 a 50. Por defecto, 20. |
| `before` | Cursor de la página siguiente: el valor de `next` de la respuesta anterior. |

**Respuesta `200`**

```json
{
  "sessions": [
    {
      "id": "6742f1c0a1b2c3d4e5f60718",
      "alias": "Tero Alegre",
      "status": "completed",
      "closed_by": "client",
      "started_at": "2026-11-23T18:11:48.663Z",
      "finished_at": "2026-11-23T18:14:35.611Z",
      "event_count": 24,
      "context": { "furniture_id": "living_room_table", "app_version": "1.1.1", "mobile": false, "joints_total": 4 },
      "summary": { "...": "el resumen completo de metricas.md" }
    }
  ],
  "next": "2026-11-23T18:11:48.663Z"
}
```

`next` es `null` en la última página.

### Detalle de una sesión

```
GET /stats/v1/simulations/{simulation_id}/sessions/{id}
```

Los mismos campos que en la lista, más los eventos. Una sesión activa o inexistente responde `404 session_not_found`.

**Respuesta `200`**

```json
{
  "id": "6742f1c0a1b2c3d4e5f60718",
  "alias": "Tero Alegre",
  "...": "los campos de la lista",
  "events": [
    {
      "sequence": 1,
      "timestamp": "2026-11-23T18:11:49.019Z",
      "type": "assembly_started",
      "data": { "furniture_id": "living_room_table", "app_version": "1.1.1", "pieces": 5, "joints": 4, "mobile": false }
    }
  ]
}
```

## Caché

Las respuestas de métricas incluyen `Cache-Control: public, max-age=60`. Los datos cambian con cada sesión, pero un minuto de demora no afecta al tablero y evita repetir las mismas agregaciones si varias personas lo abren a la vez.

## Errores

| Código HTTP | `code` | Causa |
|---|---|---|
| `400` | `invalid_request` | Filtro o parámetro con formato incorrecto |
| `404` | `simulation_not_found` | La simulación no existe o no está activa |
| `404` | `session_not_found` | La sesión no existe o todavía está activa |
| `404` | `not_found` | Endpoint que no existe para esa simulación |
| `429` | `rate_limited` | Demasiadas solicitudes |
| `5xx` | `server_error` | Error del servidor |

## Nombres de los muebles

La API devuelve identificadores (`living_room_table`), no nombres para mostrar. Los nombres los define el tablero, porque son parte de su interfaz y de su idioma.

## Gráficos del tablero

Referencia de qué endpoint alimenta cada gráfico. El diseño final es parte del tablero.

| Sección | Gráfico | Datos |
|---|---|---|
| Resumen | Tarjetas: sesiones, tasa de finalización, tasa de resolución correcta, tiempo mediano, uso de la ayuda | `/summary` |
| | Dona: resultado de las sesiones | `/summary`, `sessions.outcomes` |
| Evolución | Línea: sesiones, comprobadas y correctas por día | `/timeline` |
| Comparación | Barras agrupadas: finalización y resolución correcta por mueble | `/summary?group_by=furniture_id` |
| | Barras de rango: tiempo por mueble, del cuartil 25 al 75, con la mediana marcada | `/summary?group_by=furniture_id`, `duration_seconds` |
| | Barras agrupadas: resolución correcta con y sin ayuda | `/summary`, `help` |
| Dificultades | Barras horizontales: fallas por motivo | `/summary`, `failures_by_reason` |
| | Mapa de calor: cajas por motivo, para un mueble | `/failures?furniture_id=...` |
| Sesiones | Tabla con búsqueda por alias | `/sessions` |
| | Recorrido de una sesión: los eventos sobre una línea de tiempo, con un color por tipo | `/sessions/{id}`, `elapsed_seconds` de cada evento |

Criterios:

- **Cada gráfico muestra cuántas sesiones tiene detrás**, con el campo `sessions` de cada bloque. Al principio van a ser pocas, y un porcentaje sobre 2 sesiones no se lee igual que uno sobre 200.
- **Las donas, solo para partes de un total y con pocas partes.** Para comparar categorías, barras.
- **El color no es la única forma de distinguir los datos:** los valores se escriben sobre las barras y las porciones, y la paleta se elige para que se distinga también con daltonismo.