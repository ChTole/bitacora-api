# Bitácora API

Servidor de [Bitácora](https://github.com/ChTole/bitacora): recibe las sesiones y los eventos de telemetría que envían las simulaciones, y expone las métricas de aprendizaje que muestra el tablero.

Implementa la **versión 1.1** del [contrato de Bitácora con el servidor](https://github.com/ChTole/bitacora/blob/main/Packages/com.christiantoledo.bitacora/Documentation~/API.md). El contrato vive en el repositorio del package: este repositorio lo implementa, pero no lo copia.

La primera simulación que lo usa es el [Taller de Ensamblado](https://github.com/ChTole/taller-ensamblado).

🔗 **API:** [bitacora-api-i1b6.onrender.com](https://bitacora-api-i1b6.onrender.com/stats/v1/simulations). Corre en el plan gratuito de Render: si no recibió solicitudes en los últimos minutos, la primera respuesta puede tardar alrededor de un minuto.

## Estado

🚧 En desarrollo. La versión 0.1.0 está en producción y recibe las sesiones del Taller publicado.

- [x] Decisiones de arquitectura y modelo de datos.
- [x] Endpoints del contrato (`/v1`), con sus tests.
- [x] Admin: simulaciones y claves de API.
- [x] Analizador del Taller de Ensamblado: contexto y resumen de cada sesión.
- [x] Cierre de sesiones por inactividad.
- [x] Validación del esquema de las sesiones e índice por mueble.
- [x] Endpoints de métricas para el tablero (`/stats/v1`), con sus tests.
- [x] Despliegue en Render y MongoDB Atlas.
- [ ] Tablero de métricas ([bitacora-tablero](https://github.com/ChTole/bitacora-tablero)).

## Stack

- **Python** con **Django** y **Django REST Framework**.
- **Django MongoDB Backend** para los modelos y el admin, y **PyMongo** para el registro de eventos y las agregaciones de métricas.
- **MongoDB Atlas** como única base de datos.

## Arquitectura

```
Simulación (Unity + Bitácora) ──► /v1/...        Contrato de Bitácora (clave de API)
Tablero (Angular, Netlify)    ──► /stats/v1/...  Métricas, solo lectura
Equipo                        ──► /admin/        Simulaciones y claves
Render                        ──► /healthz       Verificación sin clave
```

- **API REST, sin vistas propias.** Django no genera páginas: la única interfaz que se usa es el admin, como herramienta interna.
- **Núcleo genérico y analizadores por simulación.** El registro de sesiones y eventos es igual para cualquier simulación. Lo que depende de cada una, como el resumen de métricas, lo calcula un analizador propio de esa simulación.

## Documentación

| Documento | Contenido |
|---|---|
| [Modelo de datos](docs/modelo-de-datos.md) | Colecciones, documentos, índices, validación y registro de eventos |
| [API del tablero](docs/api-tablero.md) | Endpoints de solo lectura que consume el tablero (`/stats/v1`) |
| [Métricas del Taller](docs/metricas.md) | Contexto y resumen de cada sesión, y métricas para el tablero |
| [Despliegue](docs/despliegue.md) | Atlas, Render y la configuración de producción |
| [001 · Stack](docs/decisiones/001-stack.md) | Django, DRF y Django MongoDB Backend |
| [002 · Solo MongoDB](docs/decisiones/002-solo-mongodb.md) | Una única base de datos, sin parte relacional |
| [003 · Eventos incrustados](docs/decisiones/003-eventos-incrustados.md) | Los eventos se guardan dentro de su sesión |
| [004 · Hosting](docs/decisiones/004-hosting.md) | Render, MongoDB Atlas y Netlify, con costo cero |
| [005 · Tablero separado](docs/decisiones/005-tablero-separado.md) | El tablero es un proyecto propio |

## Puesta en marcha

Solo se necesita **Docker**. Python y MongoDB corren en contenedores: no hace falta instalarlos ni crear un entorno virtual.

```bash
cp .env.example .env
docker compose -f docker-compose-dev.yml up --build
```

En otra terminal, la primera vez:

```bash
docker compose -f docker-compose-dev.yml exec api python manage.py migrate
docker compose -f docker-compose-dev.yml exec api python manage.py createsuperuser
```

La API queda en `http://127.0.0.1:8000` y el admin en `http://127.0.0.1:8000/admin/`.

**Editor.** Para que VS Code reconozca las bibliotecas, con los contenedores en marcha: extensión **Dev Containers** → **Attach to Running Container** → `bitacora-api-api-1`, y abrir la carpeta `/app`. VS Code usa el Python del contenedor.

**Tests.** Usan una base de prueba aparte, que Django crea y borra:

```bash
docker compose -f docker-compose-dev.yml exec api python manage.py test telemetry stats
```

**Dependencias.** Para agregar una, sumarla a `requirements.txt` y reconstruir la imagen con `--build`.

**Versiones.** Los cambios de cada versión están en el [historial de cambios](CHANGELOG.md).

## Variables de entorno

Ver [`.env.example`](.env.example). En desarrollo se copian a un archivo `.env`, que no se versiona. En producción se cargan en el panel de Render.

| Variable | Descripción |
|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django |
| `DJANGO_DEBUG` | `True` solo en desarrollo |
| `DJANGO_ALLOWED_HOSTS` | Dominios desde los que se sirve la API |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Orígenes confiables para el admin |
| `MONGODB_URI` | Cadena de conexión a MongoDB |
| `MONGODB_DB_NAME` | Nombre de la base de datos |
| `CORS_ALLOWED_ORIGINS` | Dominios de las simulaciones y del tablero |
| `CLIENT_IP_HEADER` | Encabezado con la IP real del cliente, para el límite de solicitudes. En Render, `HTTP_CF_CONNECTING_IP` |
| `TELEMETRY_RATE_LIMIT` | Límite de solicitudes por IP del contrato. Por defecto, `600/min` |
| `STATS_RATE_LIMIT` | Límite de solicitudes por IP del tablero. Por defecto, `120/min` |

La configuración de producción está en [Despliegue](docs/despliegue.md).

## Proyectos relacionados

- [Bitácora](https://github.com/ChTole/bitacora): package de Unity que registra y envía la telemetría.
- [Taller de Ensamblado](https://github.com/ChTole/taller-ensamblado): simulación de carpintería en el navegador.
- [Portfolio](https://christiantoledo-dev.netlify.app): autor y otros proyectos.

## Licencia

[MIT](LICENSE)