# Métricas del Taller de Ensamblado

Cómo calcula el analizador del Taller el `context` y el `summary` de cada sesión (ver [modelo de datos](modelo-de-datos.md#analizadores-por-simulación)), y qué métricas entre sesiones se derivan de ellos para el tablero.

**Versión del cálculo (`summary_version`):** 1

## Eventos del Taller

| `type` | Cuándo | `data` |
|---|---|---|
| `assembly_started` | Al cargar el mueble | `furniture_id`, `app_version`, `pieces`, `joints`, `mobile` |
| `joint_completed` | Al encastrar una unión | `tenon`, `mortise`, `expected`, `elapsed_seconds`, `previous_failures` |
| `joint_attempt_failed` | Al soltar una espiga cerca de una caja sin poder encastrar | `tenon`, `mortise`, `reason`, `elapsed_seconds` |
| `joint_undone` | Al deshacer una unión o sacar una pieza | `tenon`, `mortise`, `mode` (`undo` o `detach`), `piece` (solo en `detach`), `elapsed_seconds` |
| `help_viewed` | Al soltar el botón de ayuda | `duration_seconds`, `elapsed_seconds` |
| `controls_viewed` | Al cerrar los controles | `duration_seconds`, `elapsed_seconds` |
| `assembly_checked` | Al presionar Comprobar; cierra la sesión como `completed` | Resumen completo del armado |
| `assembly_abandoned` | Al volver al menú sin comprobar; cierra la sesión como `abandoned` | Resumen completo del armado |

`elapsed_seconds` es el tiempo del cronómetro de la simulación. `reason` puede ser `orientation`, `position`, `incompatible` o `blocked`. Bitácora agrega `session_paused` y `session_resumed`.

## Estrategia

El Taller ya calcula el resultado del armado para la pantalla de resumen y lo envía en el evento final (`assembly_checked` o `assembly_abandoned`). El analizador lo combina con lo que se puede derivar de los eventos:

1. **El resumen del cliente es la fuente principal.** Así, el tablero y la pantalla de resumen muestran los mismos números. Además, hay datos que solo existen ahí: las veces que se agarró y se giró una pieza no se envían como eventos.
2. **Los eventos completan** lo que el resumen del cliente no tiene: los motivos de falla, el tiempo hasta la primera unión, la cantidad total de encastres y el análisis por caja.
3. **Los eventos verifican** el resumen del cliente. Las cantidades que se pueden contar en los dos lados se comparan, y una diferencia indica eventos perdidos o un error en alguno de los dos cálculos.
4. **Sin evento final**, por ejemplo si se cerró la pestaña del navegador, el resumen se calcula solo con los eventos y queda marcado con `source: "events"`.

## `context`

Se copia del primer `assembly_started` de la sesión:

| Campo | Uso en el tablero |
|---|---|
| `furniture_id` | Agrupar por mueble, que es también la dificultad |
| `app_version` | Separar resultados de versiones distintas de la simulación |
| `mobile` | Comparar escritorio y móvil |
| `joints_total` | Total de uniones del mueble (`joints` en el evento) |

## `summary`

```json
{
  "source": "client",
  "outcome": "checked",
  "completed": true,
  "correct": true,
  "duration_seconds": 166.3,
  "time_to_first_joint_seconds": 26.0,
  "joints_total": 4,
  "joints_completed": 4,
  "incorrect_joints": 0,
  "connections": 7,
  "undos": 2,
  "detaches": 1,
  "failed_attempts": 8,
  "failures_by_reason": { "position": 6, "blocked": 2 },
  "help_requests": 2,
  "help_seconds": 3.1,
  "controls_views": 2,
  "controls_seconds": 6.1,
  "grabs": 52,
  "rotations": 23,
  "consistent": true,
  "discrepancies": []
}
```

### Campos y cálculo

| Campo | Del resumen del cliente | Desde los eventos |
|---|---|---|
| `source` | `client` | `events`, si no hay evento final |
| `outcome` | `checked` o `abandoned`, según el evento final | `none` |
| `completed` | `completed` | `joints_completed` = `joints_total` |
| `correct` | `correct` | `completed` y `incorrect_joints` = 0 |
| `duration_seconds` | `duration_seconds` | `elapsed_seconds` del último evento del armado |
| `time_to_first_joint_seconds` | — | `elapsed_seconds` del primer `joint_completed` |
| `joints_total` | `joints_total` | `joints` de `assembly_started` |
| `joints_completed` | `joints_completed` | `joint_completed` menos `joint_undone` |
| `incorrect_joints` | `incorrect_joints` | Uniones vigentes con `expected: false` |
| `connections` | — | Cantidad de `joint_completed`, incluidas las que después se deshicieron |
| `undos` | `undos` | `joint_undone` con `mode: "undo"` |
| `detaches` | `detaches` | `joint_undone` con `mode: "detach"` |
| `failed_attempts` | `failed_attempts` | Cantidad de `joint_attempt_failed` |
| `failures_by_reason` | — | `joint_attempt_failed` agrupados por `reason` |
| `help_requests` | `help_requests` | Cantidad de `help_viewed` |
| `help_seconds` | `help_seconds` | Suma de `duration_seconds` de `help_viewed` |
| `controls_views` | `controls_views` | Cantidad de `controls_viewed` |
| `controls_seconds` | `controls_seconds` | Suma de `duration_seconds` de `controls_viewed` |
| `grabs`, `rotations` | `grabs`, `rotations` | `null`: no hay eventos para calcularlos |
| `consistent`, `discrepancies` | Comparación de los campos que existen en las dos columnas | `null` |

Los tiempos se redondean a una décima de segundo, igual que en el Taller.

### Verificación con la sesión de ejemplo

Sesión "Tero Alegre" del servidor de prueba (mesa ratona, 24 eventos):

| Campo | Cliente | Eventos |
|---|---|---|
| `duration_seconds` | 166.3 | 166.3 (diferencia de `timestamp`, sin pausas) |
| `joints_completed` | 4 | 7 encastres − 3 deshechos = 4 |
| `incorrect_joints` | 0 | 0 |
| `failed_attempts` | 8 | 8 (6 `position`, 2 `blocked`) |
| `undos` / `detaches` | 2 / 1 | 2 / 1 |
| `help_requests` / `help_seconds` | 2 / 3.1 | 2 / 3.1 |
| `controls_views` / `controls_seconds` | 2 / 6.1 | 2 / 6.1 |

Todas las cantidades coinciden: `consistent: true`. La demora máxima de entrega (`received_at` − `timestamp`) fue de 4,7 segundos, dentro del intervalo de envío de Bitácora.

## Métricas entre sesiones

Propuesta para el tablero. Los endpoints se van a definir en `docs/api-tablero.md`. Todas se pueden filtrar por mueble, versión de la simulación, escritorio o móvil y período.

| Métrica | Cálculo | Fuente |
|---|---|---|
| Sesiones | Cantidad, por estado | Sesión |
| Tasa de finalización | `outcome: checked` sobre el total de sesiones cerradas | `summary` |
| Tasa de resolución correcta | `correct: true` sobre las sesiones comprobadas | `summary` |
| Tiempo de armado | Mediana y percentiles de `duration_seconds` de las sesiones correctas | `summary` |
| Intentos fallidos | Mediana por sesión, y distribución por `reason` | `summary` |
| Uso de la ayuda | Porcentaje de sesiones que la usan, y mediana de `help_seconds` | `summary` |
| Ayuda y resultado | Tasa de resolución correcta con y sin ayuda | `summary` |
| Cajas más difíciles | `joint_attempt_failed` agrupados por `mortise` y por `reason` | `events`, con `$unwind` |

Para los tiempos se usa la mediana y no el promedio: una sesión que quedó abierta mucho tiempo distorsionaría el promedio.

## Criterios del Taller

1. **Las fallas se miden por caja, no por pieza.** El Taller no fija qué espiga va en qué caja: cualquier pata puede ir en cualquier caja de la tabla. Por eso, la dificultad está en la caja y en cómo se la intenta encastrar, no en la pieza. `previous_failures` cuenta las fallas en esa caja desde el inicio de la sesión, con cualquier espiga, y las métricas por caja se calculan con el mismo criterio a partir de `joint_attempt_failed`.
2. **El motivo de la falla describe el error.** Por ejemplo, intentar encastrar del lado incorrecto de una tabla (la de la mesa, el asiento del taburete, el asiento o el respaldo de la silla), o encastrar en la parte más alta con la tabla de la mesa parada, que se registra como `position`. Por eso el tablero muestra las fallas por caja y por motivo.
3. **Sin reinicio del armado.** La versión actual del Taller no tiene la opción de reiniciar: volver al menú abandona la sesión y Comprobar la cierra. `AssemblyTelemetry` está preparado para registrar `assembly_reset`, pero ningún control lo dispara, así que este cálculo no lo contempla. Si una versión futura agrega el reinicio, el cálculo se actualiza y sube `summary_version`.
4. **Sesiones sin cierre.** Si se cierra la pestaña, la sesión queda activa sin evento final. El servidor la cierra como `abandoned` después de 2 horas sin eventos y calcula su resumen solo desde los eventos (ver [modelo de datos](modelo-de-datos.md#cierre-por-inactividad)).