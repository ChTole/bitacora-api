# Bitácora API

Servidor de [Bitácora](https://github.com/ChTole/bitacora): recibe las sesiones y los eventos de telemetría que envían las simulaciones, y expone las métricas de aprendizaje que muestra el tablero.

Implementa la **versión 1.1** del [contrato de Bitácora con el servidor](https://github.com/ChTole/bitacora/blob/main/Packages/com.christiantoledo.bitacora/Documentation~/API.md). El contrato vive en el repositorio del package: este repositorio lo implementa, pero no lo copia.

La primera simulación que lo usa es el [Taller de Ensamblado](https://github.com/ChTole/taller-ensamblado).

## Estado

🚧 En diseño.

- [x] Decisiones de arquitectura y modelo de datos.
- [ ] Endpoints del contrato (`/v1`).
- [ ] Admin: simulaciones y claves de API.
- [ ] Analizador del Taller de Ensamblado: contexto y resumen de cada sesión.
- [ ] Endpoints de métricas para el tablero.
- [ ] Tests del contrato.
- [ ] Despliegue en Render y MongoDB Atlas.

## Stack

- **Python** con **Django** y **Django REST Framework**.
- **Django MongoDB Backend** para los modelos y el admin, y **PyMongo** para el registro de eventos y las agregaciones de métricas.
- **MongoDB Atlas** como única base de datos.

## Arquitectura

```
Simulación (Unity + Bitácora) ──► /v1/...        Contrato de Bitácora (clave de API)
Tablero (Angular, Netlify)    ──► /stats/v1/...  Métricas, solo lectura
Equipo                        ──► /admin/        Simulaciones y claves
```

- **API REST, sin vistas propias.** Django no genera páginas: la única interfaz que se usa es el admin, como herramienta interna.
- **Núcleo genérico y analizadores por simulación.** El registro de sesiones y eventos es igual para cualquier simulación. Lo que depende de cada una, como el resumen de métricas, lo calcula un analizador propio de esa simulación.

## Documentación

| Documento | Contenido |
|---|---|
| [Modelo de datos](docs/modelo-de-datos.md) | Colecciones, documentos, índices, validación y registro de eventos |
| [001 · Stack](docs/decisiones/001-stack.md) | Django, DRF y Django MongoDB Backend |
| [002 · Solo MongoDB](docs/decisiones/002-solo-mongodb.md) | Una única base de datos, sin parte relacional |
| [003 · Eventos incrustados](docs/decisiones/003-eventos-incrustados.md) | Los eventos se guardan dentro de su sesión |
| [004 · Hosting](docs/decisiones/004-hosting.md) | Render, MongoDB Atlas y Netlify, con costo cero |
| [005 · Tablero separado](docs/decisiones/005-tablero-separado.md) | El tablero es un proyecto propio |

## Puesta en marcha

Pendiente: se completa con el primer código.

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

## Proyectos relacionados

- [Bitácora](https://github.com/ChTole/bitacora): package de Unity que registra y envía la telemetría.
- [Taller de Ensamblado](https://github.com/ChTole/taller-ensamblado): simulación de carpintería en el navegador.
- [Portfolio](https://christiantoledo-dev.netlify.app): autor y otros proyectos.

## Licencia

[MIT](LICENSE)
