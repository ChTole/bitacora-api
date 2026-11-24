# Modelo de datos

Base de datos MongoDB con dos colecciones: `simulations` y `sessions`. Las decisiones que llevaron a este modelo están en [002](decisiones/002-solo-mongodb.md) y [003](decisiones/003-eventos-incrustados.md).

Los usuarios del admin los gestiona Django en sus propias colecciones.

## `simulations`

Una simulación registrada, con su clave de API.

```json
{
  "_id": ObjectId("..."),
  "simulation_id": "taller-ensamblado",
  "name": "Taller de Ensamblado",
  "api_key_prefix": "bk_7f3a",
  "api_key_hash": "9b1c...e04d",
  "allowed_origins": ["https://taller-de-ensamblado.netlify.app"],
  "is_active": true,
  "created_at": ISODate("2026-11-23T15:00:00Z")
}
```

| Campo | Descripción |
|---|---|
| `simulation_id` | Identificador que envía Bitácora al crear la sesión. Único. |
| `name` | Nombre legible, para el admin y el tablero. |
| `api_key_prefix` | Primeros caracteres de la clave, para reconocerla en el admin sin mostrarla completa. |
| `api_key_hash` | Hash SHA-256 de la clave. La clave completa se muestra una sola vez, al generarla. |
| `allowed_origins` | Dominios permitidos por CORS para esta simulación. |
| `is_active` | Si es `false`, la clave se rechaza con `401`. |

**Validación de la clave.** El servidor calcula el hash de la clave recibida y lo busca en la colección. Además, comprueba que el `simulation_id` del cuerpo, o el de la sesión en las demás rutas, sea el de la simulación de la clave. Como las claves son aleatorias y largas, alcanza con SHA-256: no hace falta un algoritmo lento como los de las contraseñas.

**Índices**
- `simulation_id`, único.
- `api_key_hash`, único.

## `sessions`

Una sesión, con sus eventos y su resumen.

```json
{
  "_id": ObjectId("..."),
  "session_id": "27a02397-c169-4165-ba40-7402227e9d7e",
  "simulation_id": "taller-ensamblado",
  "alias": "Carpincho Turquesa",
  "participant": null,
  "status": "completed",
  "started_at": ISODate("2026-11-23T15:05:00.000Z"),
  "finished_at": ISODate("2026-11-23T15:12:40.000Z"),
  "closed_by": "client",
  "last_activity_at": ISODate("2026-11-23T15:12:40.000Z"),
  "event_count": 42,
  "discarded_count": 0,
  "context": { "furniture_id": "taburete" },
  "summary": { "...": "..." },
  "summary_version": 1,
  "events": [
    {
      "sequence": 1,
      "timestamp": ISODate("2026-11-23T15:05:12.345Z"),
      "received_at": ISODate("2026-11-23T15:05:14.020Z"),
      "type": "assembly_started",
      "data": { "furniture_id": "taburete" }
    }
  ]
}
```

| Campo | Descripción |
|---|---|
| `session_id` | UUID generado por el servidor. Es el identificador del contrato. |
| `simulation_id` | Simulación a la que pertenece. |
| `alias` | Alias asignado al crear la sesión (ver [Alias](#alias)). |
| `participant` | `null` o `{ type, value }`, como en el contrato. |
| `status` | `active`, `completed` o `abandoned`. |
| `started_at`, `finished_at` | Creación y cierre, según el reloj del servidor. `finished_at` es `null` mientras la sesión está activa. |
| `closed_by` | `client` si la cerró Bitácora, `server` si se cerró por inactividad. `null` mientras está activa. |
| `last_activity_at` | Última solicitud recibida para la sesión: creación, lote de eventos o cierre. |
| `event_count` | Cantidad de eventos guardados. Se usa para el control de concurrencia y para el límite. |
| `discarded_count` | Eventos descartados por haber alcanzado el límite. |
| `context` | Datos de la sesión que el tablero usa para filtrar y agrupar. Los define el analizador de cada simulación. |
| `summary` | Métricas de la sesión. Se calcula al cerrarla; `null` mientras está activa. Lo define el analizador de cada simulación. |
| `summary_version` | Versión del cálculo del resumen. Si el cálculo cambia, permite identificar y recalcular las sesiones con una versión anterior. |
| `events` | Eventos ordenados por `sequence`. Hasta 2000. |

Cada evento guarda los cuatro campos del contrato más `received_at`, el momento en que llegó al servidor. La diferencia con `timestamp` muestra la demora de entrega.

Las fechas se guardan como `Date` de BSON, no como texto, para poder ordenarlas, filtrarlas y operar con ellas en las agregaciones. Se convierten a ISO 8601 al responder.

### Analizadores por simulación

El núcleo del servidor es igual para todas las simulaciones. Cada simulación puede tener un analizador que define:

- **`context`:** qué datos de los eventos se copian a la sesión. En el Taller, `furniture_id`, que llega en `assembly_started`.
- **`summary`:** cómo se calculan las métricas a partir de los eventos. El cálculo del Taller se va a documentar en `docs/metricas.md`.

Si una simulación no tiene analizador, sus sesiones se guardan igual, con `context` vacío y `summary` en `null`.

### Índices

| Índice | Uso |
|---|---|
| `session_id`, único | Todas las rutas del contrato |
| `simulation_id`, `started_at` (descendente) | Listados y métricas por período |
| `simulation_id`, `status`, `started_at` (descendente) | Tasa de finalización, sesiones activas |
| `simulation_id`, `alias`, `started_at` (descendente) | Búsqueda de resultados por alias; alias recientes |
| `context.furniture_id`, `started_at` (descendente), parcial: solo `simulation_id: "taller-ensamblado"` | Métricas por mueble del Taller |
| `status`, `last_activity_at` | Búsqueda de sesiones inactivas para cerrarlas |

Los índices sobre `context` se agregan por simulación, según lo que use su tablero. Son parciales: solo incluyen las sesiones de esa simulación, que son las que tienen esos campos.

Todos, menos el del Taller, se definen en el modelo `Session`. El del Taller se crea en la migración `0002`, con PyMongo, porque Django no puede indexar un campo dentro de un `JSONField`.

### Validación

La colección tiene un validador `$jsonSchema`, que se aplica en la migración `0002` y refuerza las reglas de la aplicación. Los enteros admiten `int` y `long`, los dos tipos con los que PyMongo guarda un entero de Python según su tamaño.

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "required": [
      "session_id",
      "simulation_id",
      "alias",
      "status",
      "started_at",
      "last_activity_at",
      "event_count",
      "discarded_count",
      "events"
    ],
    "properties": {
      "session_id": {
        "bsonType": "string"
      },
      "simulation_id": {
        "bsonType": "string"
      },
      "alias": {
        "bsonType": "string"
      },
      "participant": {
        "bsonType": [
          "object",
          "null"
        ]
      },
      "status": {
        "enum": [
          "active",
          "completed",
          "abandoned"
        ]
      },
      "started_at": {
        "bsonType": "date"
      },
      "finished_at": {
        "bsonType": [
          "date",
          "null"
        ]
      },
      "closed_by": {
        "enum": [
          "client",
          "server",
          null
        ]
      },
      "last_activity_at": {
        "bsonType": "date"
      },
      "event_count": {
        "bsonType": [
          "int",
          "long"
        ],
        "minimum": 0,
        "maximum": 2000
      },
      "discarded_count": {
        "bsonType": [
          "int",
          "long"
        ],
        "minimum": 0
      },
      "context": {
        "bsonType": "object"
      },
      "summary": {
        "bsonType": [
          "object",
          "null"
        ]
      },
      "summary_version": {
        "bsonType": [
          "int",
          "long",
          "null"
        ]
      },
      "events": {
        "bsonType": "array",
        "maxItems": 2000,
        "items": {
          "bsonType": "object",
          "required": [
            "sequence",
            "timestamp",
            "received_at",
            "type"
          ],
          "properties": {
            "sequence": {
              "bsonType": [
                "int",
                "long"
              ],
              "minimum": 1
            },
            "timestamp": {
              "bsonType": "date"
            },
            "received_at": {
              "bsonType": "date"
            },
            "type": {
              "bsonType": "string",
              "maxLength": 64
            },
            "data": {
              "bsonType": [
                "object",
                "null"
              ]
            }
          }
        }
      }
    }
  }
}
```

El validador no reemplaza la validación de la API: los errores de formato se responden con `400` antes de llegar a la base.

## Registro de un lote

`POST /v1/sessions/{session_id}/events`. Después de validar el formato del lote:

1. **Leer** la sesión, solo con `status`, `event_count` y `events.sequence`.
   - Si no existe → `404 session_not_found`.
   - Si `status` no es `active` → `409 session_finished`.
2. **Separar duplicados:** los eventos cuyo `sequence` ya está en la sesión, o repetido dentro del lote, se cuentan en `duplicates`.
3. **Aplicar el límite:** si quedan eventos nuevos y la sesión no tiene espacio → `409 session_full`. Si el espacio no alcanza para todos, se aceptan los de menor `sequence` y el resto se cuenta en `discarded`.
4. **Guardar** con una actualización condicional:

```python
result = sessions.update_one(
    {"session_id": session_id, "status": "active", "event_count": count_leido},
    {
        "$push": {"events": {"$each": nuevos, "$sort": {"sequence": 1}}},
        "$inc": {"event_count": len(nuevos), "discarded_count": discarded},
        "$set": {"last_activity_at": ahora},
    },
)
```

5. **Si `result.matched_count` es 0**, otra solicitud modificó la sesión entre la lectura y la escritura: se vuelve al paso 1. Se reintenta unas pocas veces; si no se logra, se responde `5xx` y el cliente reintenta.

La actualización de un documento es atómica en MongoDB: el lote se guarda completo o no se guarda. El filtro por `event_count` es control de concurrencia optimista: solo escribe quien leyó la versión actual. Si el lote solo trae duplicados, no se escribe nada y se responde `200`.

Este paso se implementa con PyMongo y no con el ORM, porque `save()` reescribe la lista completa y no permite una actualización condicional.

## Cierre de una sesión

`POST /v1/sessions/{session_id}/finish`:

1. Leer la sesión completa.
   - Si ya está cerrada → `200` con los datos del primer cierre.
2. Calcular `summary` con el analizador de la simulación, si tiene uno.
3. Guardar `status`, `finished_at`, `closed_by: "client"`, `summary` y `summary_version` con el mismo filtro condicional por `status: "active"` y `event_count`. Si un lote llegó entre la lectura y la escritura, se vuelve al paso 1, para que el resumen incluya todos los eventos.

## Cierre por inactividad

Si se cierra la pestaña del navegador, Bitácora no llega a cerrar la sesión. El servidor cierra como `abandoned` las sesiones activas con `last_activity_at` de hace más de 2 horas, con `closed_by: "server"` y el resumen calculado con los eventos que llegaron.

- **`finished_at` es la última actividad**, no el momento en que se detectó la inactividad: es cuando la sesión terminó en realidad.
- **Se usa el mismo filtro condicional que en un cierre normal**, más la condición de inactividad. Si llega un lote entre la lectura y la escritura, la sesión vuelve a estar activa y no se cierra.
- **Si Bitácora pide el cierre después**, recibe `200` con los datos del cierre del servidor, como en cualquier sesión ya cerrada.

El plan gratuito de Render no tiene tareas programadas, así que el cierre se ejecuta antes de responder una consulta de métricas: se buscan las sesiones inactivas con el índice `status`, `last_activity_at` y se cierran hasta 100 por consulta. Si no hay ninguna, la búsqueda por índice no tiene un costo apreciable.

También se puede ejecutar a mano:

```bash
python manage.py close_inactive_sessions            # cierra las inactivas por más de 2 horas
python manage.py close_inactive_sessions --dry-run  # solo muestra cuántas hay
```

## Alias

Al crear una sesión, el servidor elige al azar una combinación de animal y adjetivo que no se haya usado en las sesiones de la misma simulación de los últimos 30 días. Si no encuentra una libre después de algunos intentos, agrega un número ("Carpincho Turquesa 27"), como indica el contrato.

El alias no es único para siempre: se puede repetir después de ese período. Por eso, la búsqueda por alias ordena por `started_at` y muestra primero la sesión más reciente.