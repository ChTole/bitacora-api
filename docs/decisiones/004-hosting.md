# 004 · Hosting: Render, MongoDB Atlas y Netlify

- **Estado:** aceptada
- **Fecha:** 2026-11-23

## Contexto

El proyecto no tiene presupuesto: todo tiene que funcionar en planes gratuitos. La API recibe telemetría de simulaciones públicas y sirve métricas a un tablero público.

## Decisión

| Parte | Servicio | Plan |
|---|---|---|
| API (Django) | Render, *web service* | Gratuito |
| Base de datos | MongoDB Atlas | Cluster gratuito |
| Tablero (Angular) | Netlify | Gratuito |

En desarrollo se usa MongoDB en local, con Docker.

## Alternativas consideradas

- **Fly.io y Railway:** ya no tienen un plan gratuito permanente.
- **Koyeb:** pide una retención en la tarjeta.
- **Máquinas virtuales gratuitas (Oracle Cloud y otros):** piden tarjeta y requieren administrar el servidor.

## Consecuencias

**Render**
- El servicio se apaga después de 15 minutos sin tráfico y tarda alrededor de un minuto en volver. Para compensarlo:
  - El Taller llama a `/v1/health` apenas carga la página, para despertar al servidor mientras se descarga la simulación.
  - El tablero muestra un estado de espera mientras el servidor se activa.
  - Bitácora conserva los eventos y reintenta si no hay conexión.
- El disco no persiste entre reinicios: no se guarda nada en archivos locales, todo va a Atlas.
- Hay una sola instancia, así que los límites de solicitudes de DRF pueden usar la caché en memoria.

**MongoDB Atlas**
- El cluster gratuito tiene 512 MB y 100 operaciones por segundo. Alcanza para decenas de miles de sesiones, y un lote de eventos es una sola operación.
- Atlas puede desactivar clusters gratuitos inactivos.
- Render no tiene una IP de salida propia en el plan gratuito, así que el acceso de red a Atlas puede quedar abierto a cualquier IP. Se compensa con un usuario de base de datos con permiso `readWrite` solo sobre esta base, una contraseña larga y TLS, que en Atlas siempre está activo.

**Seguridad general**
- Las credenciales van en variables de entorno del panel de Render, nunca en el repositorio.
- La clave de API de una simulación en el navegador es pública por diseño: solo permite crear sesiones y registrar eventos de su propia simulación, y se guarda en la base como hash.
- CORS limitado a los dominios de cada simulación y del tablero.
