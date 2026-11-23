# 003 · Eventos incrustados en la sesión

- **Estado:** aceptada
- **Fecha:** 2026-11-23

## Contexto

Cada sesión tiene una lista de eventos. Los eventos de una sesión se consultan casi siempre juntos: para calcular su resumen, para mostrar su recorrido en el tablero o para buscar los resultados de una persona por su alias. En MongoDB, lo que se lee junto conviene guardarlo junto, siempre que la lista tenga un límite: una lista sin límite dentro de un documento es un antipatrón.

## Decisión

- Los eventos se guardan **dentro del documento de su sesión**, en el arreglo `events`.
- El contrato fija un **límite de 2000 eventos por sesión** (versión 1.1, error `409 session_full`). Lo controla la aplicación y, además, un validador `$jsonSchema` de la colección.
- El **resumen de la sesión** (`summary`) también se guarda dentro de la sesión. Se calcula una sola vez, al cerrarla (*computed pattern*).

## Alternativas consideradas

- **Colección `events` aparte**, con un índice único en `(session_id, sequence)`. Resuelve la deduplicación con el índice, pero separa datos que se leen juntos y obliga a combinarlos en cada consulta.
- **Patrón *bucket*:** los eventos se reparten en documentos de tamaño fijo vinculados a la sesión. Sirve para sesiones con muchos eventos. Queda como salida si alguna simulación lo necesita.

## Consecuencias

- **Una sola lectura por sesión:** sesión, eventos y resumen en un documento.
- **La deduplicación pasa a la aplicación.** Un índice único sobre `events.sequence` impide repetir un valor entre documentos distintos, pero no dentro del mismo documento. El registro de un lote usa una actualización condicional con control de concurrencia optimista (ver [modelo de datos](../modelo-de-datos.md#registro-de-un-lote)).
- **Tamaño acotado:** con 2000 eventos y el máximo de 4 KB por `data`, el peor caso ronda los 8 MB, debajo del límite de 16 MB por documento. Una sesión típica del Taller tiene unas decenas de eventos.
- **Los listados no traen los eventos.** Todas las consultas que no muestran el detalle de una sesión excluyen `events` de la proyección.
- **Métricas entre sesiones:** las generales salen de los resúmenes. Las que analizan eventos de muchas sesiones (por ejemplo, en qué unión se falla más) necesitan `$unwind`, que a esta escala no es un problema.
