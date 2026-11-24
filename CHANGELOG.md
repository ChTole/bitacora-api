# Historial de cambios

Todos los cambios relevantes de Bitácora API se registran en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/). La versión del servidor es independiente de la de sus contratos: el de Bitácora (`/v1`, versión 1.1) y el del tablero (`/stats/v1`, versión 1).

## [0.1.0] - 2026-11-24

Primera versión en producción, en Render y MongoDB Atlas.

### Agregado

- Contrato de Bitácora 1.1 (`/v1`): verificación de conexión, creación de sesiones con alias, registro de eventos por lotes con deduplicación y límite por sesión, y cierre.
- Autenticación por clave de API, limitada a la simulación de la clave. Las claves se guardan como hash.
- Admin para gestionar simulaciones y claves, y consultar sesiones.
- Analizador del Taller de Ensamblado: contexto y resumen de cada sesión (`summary_version` 1).
- Cierre de sesiones por inactividad, antes de cada consulta de métricas y con el comando `close_inactive_sessions`.
- Validador `$jsonSchema` de la colección de sesiones e índice parcial por mueble del Taller.
- API del tablero (`/stats/v1`): simulaciones, métricas generales con agrupación, sesiones por día, fallas por caja, y lista y detalle de sesiones.
- Límite de solicitudes por IP real del cliente, con respuesta `429 rate_limited`.
- Despliegue con Docker: gunicorn, archivos estáticos del admin con WhiteNoise, migraciones al arrancar y `/healthz` para el health check.

[0.1.0]: https://github.com/ChTole/bitacora-api/releases/tag/v0.1.0