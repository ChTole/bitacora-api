# 002 · Solo MongoDB

- **Estado:** aceptada
- **Fecha:** 2026-11-23

## Contexto

Los datos son de dos tipos:

- **Sesiones con sus eventos:** el campo `data` de cada evento tiene una estructura distinta según la simulación y el tipo de evento.
- **Datos administrativos:** simulaciones, claves de API y usuarios del admin. Son pocos registros con una estructura fija.

Al principio se evaluó usar MariaDB para los datos administrativos y MongoDB para las sesiones.

## Decisión

Usar **solo MongoDB** para todo.

## Alternativas consideradas

- **MariaDB + MongoDB.** Los datos administrativos son unos pocos registros y no justifican una segunda base. Además, casi no quedan servicios gratuitos de MySQL o MariaDB: Aiven retiró su plan gratuito de MySQL a fines de 2026.
- **PostgreSQL + MongoDB.** Hay planes gratuitos y Django lo soporta de forma nativa, pero agrega un proveedor y una conexión más sin un beneficio claro para este proyecto.

## Consecuencias

- Un solo proveedor y una sola conexión, en el plan gratuito de MongoDB Atlas.
- El modelo de documentos encaja con datos que cambian según la simulación, y permite guardar juntos los datos que se consultan juntos (ver [003](003-eventos-incrustados.md)).
- Las relaciones entre colecciones (por ejemplo, de una sesión a su simulación) se resuelven por identificador, sin claves foráneas que la base haga cumplir.
