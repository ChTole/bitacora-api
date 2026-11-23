# 001 · Stack: Django, DRF y Django MongoDB Backend

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

El servidor tiene que implementar el contrato de Bitácora (crear sesiones, registrar eventos por lotes y cerrarlas), exponer métricas para el tablero y permitir administrar simulaciones y claves de API. Los datos se guardan en MongoDB (ver [002](002-solo-mongodb.md)).

## Decisión

- **Django + Django REST Framework** para la API. Se usa la experiencia previa con el framework, y DRF resuelve validación, serialización, manejo de errores y límites de solicitudes (*throttling*).
- **Django MongoDB Backend**, el backend oficial de MongoDB para Django, para los modelos y el admin.
- **PyMongo directo** para dos casos donde el ORM no alcanza:
  - El registro de eventos, que necesita una actualización condicional y atómica (ver [modelo de datos](../modelo-de-datos.md#registro-de-un-lote)).
  - Las métricas, que se calculan con pipelines de agregación.
- **Sin vistas propias.** Django no genera páginas: la API es REST y el tablero es un proyecto aparte (ver [005](005-tablero-separado.md)). La única interfaz de Django que se usa es el admin, como herramienta interna.

## Alternativas consideradas

- **Flask o FastAPI.** Son más livianos, pero requieren armar por separado lo que Django ya trae (admin, configuración, validación) y hay menos experiencia previa con ellos.
- **PyMongo sin ORM.** Se pierde el admin y la integración con DRF.
- **MongoEngine o Djongo.** Son bibliotecas de terceros, anteriores al backend oficial.

## Consecuencias

- Hay dos formas de acceder a los datos: el ORM y PyMongo. El criterio es usar el ORM para leer y administrar, y PyMongo solo para el registro de eventos y las agregaciones.
- Django MongoDB Backend es reciente. Su versión tiene que corresponder a la de Django, así que conviene fijar las dos versiones en las dependencias.
