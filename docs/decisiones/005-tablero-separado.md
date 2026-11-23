# 005 · Tablero como proyecto separado

- **Estado:** aceptada
- **Fecha:** 2026-11-23

## Contexto

El tablero muestra las métricas de aprendizaje del Taller de Ensamblado: tiempos, errores, uniones correctas e incorrectas y consultas a la ayuda. Forma parte de los MVP del portfolio, y se evaluó incluirlo como una sección del portfolio (Angular, Netlify).

## Decisión

El tablero es un **proyecto propio**, en su repositorio y con su propio sitio en Netlify. Consume los endpoints de métricas de esta API (`/stats/v1/...`), de solo lectura.

## Alternativas consideradas

- **Una ruta dentro del portfolio.** Reutiliza el despliegue, pero mezcla un producto con identidad propia dentro de otro sitio.
- **Vistas de Django.** Contradice la decisión de una API REST sin vistas propias (ver [001](001-stack.md)).

## Consecuencias

- El tablero se entiende por sí mismo, y el portfolio lo enlaza como un proyecto más.
- El portfolio no suma dependencias ni código ajeno a su propósito.
- Esta API tiene dos clientes con contratos distintos: Bitácora (`/v1`, definido en el repositorio de Bitácora) y el tablero (`/stats/v1`, que se va a documentar en este repositorio).
