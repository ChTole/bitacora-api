# Despliegue

La API corre en un *web service* gratuito de Render, con la imagen del `Dockerfile`, y los datos están en un cluster gratuito de MongoDB Atlas. Las decisiones están en [004](decisiones/004-hosting.md).

## 1. MongoDB Atlas

1. **Cluster:** crear un cluster gratuito en AWS, en la región más cercana a la que se elija en Render. Por ejemplo, AWS N. Virginia (`us-east-1`) con Render en Virginia. La API hace varias consultas por solicitud, así que importa más la distancia entre Render y Atlas que la distancia a quien usa la simulación.
2. **Usuario de la base de datos** (*Database Access*): un usuario solo para la API, con *Specific Privileges*:
   - `readWrite` sobre la base `bitacora`.
   - `dbAdmin` sobre la base `bitacora`. Lo necesita la migración `0002`, que aplica el validador con `collMod`.

   Ninguno de los dos da acceso a otras bases del cluster. Usar una contraseña larga, solo con letras y números, así no hay que codificarla en la cadena de conexión.
3. **Acceso de red** (*Network Access*): `0.0.0.0/0`. El plan gratuito de Render no tiene una IP de salida fija. La protección queda en el usuario con permisos acotados, la contraseña y TLS, que en Atlas siempre está activo.
4. **Cadena de conexión** (*Connect → Drivers*): queda con la forma

   ```
   mongodb+srv://<usuario>:<contraseña>@<cluster>.mongodb.net/?retryWrites=true&w=majority&appName=bitacora-api
   ```

## 2. Primer usuario del admin

El plan gratuito de Render no da acceso a una terminal del servidor, así que el superusuario se crea desde el entorno local, conectado a Atlas:

```bash
docker compose -f docker-compose-dev.yml run --rm \
  -e MONGODB_URI="<cadena de conexión de Atlas>" -e MONGODB_DB_NAME=bitacora \
  api sh -c "python manage.py migrate && python manage.py createsuperuser"
```

Las migraciones también se aplican solas cada vez que arranca el servicio en Render (`scripts/start.sh`).

## 3. Render

*New → Web Service*, con el repositorio `bitacora-api`:

| Campo | Valor |
|---|---|
| Language | Docker |
| Branch | `main` |
| Region | La misma zona que el cluster de Atlas |
| Instance Type | Free |
| Health Check Path | `/healthz` |

Variables de entorno:

| Variable | Valor |
|---|---|
| `DJANGO_SECRET_KEY` | Una clave nueva, distinta de la de desarrollo |
| `DJANGO_DEBUG` | `False` |
| `MONGODB_URI` | La cadena de conexión de Atlas |
| `MONGODB_DB_NAME` | `bitacora` |
| `CORS_ALLOWED_ORIGINS` | `https://taller-de-ensamblado.netlify.app` (y, más adelante, el dominio del tablero) |
| `CLIENT_IP_HEADER` | `HTTP_CF_CONNECTING_IP` |

`DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` no hacen falta: la configuración agrega el dominio que Render define en `RENDER_EXTERNAL_HOSTNAME`. Solo se usan para sumar un dominio propio.

`CLIENT_IP_HEADER` le dice al límite de solicitudes dónde está la IP real del cliente. El proxy de Render agrega entradas a `X-Forwarded-For` sin limpiarlo, así que no es confiable. Si el encabezado no llega, la API lo avisa una vez en los logs.

## 4. Verificación

Con el servicio en marcha (el primer arranque tarda unos minutos):

```bash
curl https://<servicio>.onrender.com/healthz                    # ok
curl -i https://<servicio>.onrender.com/v1/health               # 401 invalid_api_key
```

1. Entrar a `https://<servicio>.onrender.com/admin/` y crear la simulación `taller-ensamblado`, con el origen `https://taller-de-ensamblado.netlify.app`. Copiar la clave del aviso.
2. Probar la clave:

   ```bash
   curl -H "X-Api-Key: <clave>" https://<servicio>.onrender.com/v1/health   # {"status": "ok"}
   curl https://<servicio>.onrender.com/stats/v1/simulations
   ```

3. Revisar los logs de Render: no tendría que aparecer el aviso de `CLIENT_IP_HEADER`.

## 5. Taller de Ensamblado

1. En `BitacoraConfig`: `Backend: Http`, `Api Base Url: https://<servicio>.onrender.com` y la clave de producción.
2. En el `index.html` de la plantilla WebGL, despertar el servidor apenas carga la página, para que esté activo cuando la persona presione Comenzar:

   ```html
   <script>fetch("https://<servicio>.onrender.com/healthz").catch(() => {});</script>
   ```

3. Compilar, publicar en Netlify y hacer el commit de la configuración.

## Funcionamiento en el plan gratuito

- **Apagado por inactividad:** el servicio se apaga después de 15 minutos sin solicitudes y tarda alrededor de un minuto en volver. Bitácora conserva los eventos y reintenta mientras tanto.
- **Recursos:** 512 MB de RAM y 0,1 CPU. Por eso gunicorn corre con un solo proceso y cuatro hilos.
- **Advertencias de `check --deploy`:** `SECURE_HSTS_SECONDS` y `SECURE_SSL_REDIRECT` quedan sin configurar, porque el HTTPS lo maneja Render antes de llegar a Django. Se puede revisar con `curl -I http://<servicio>.onrender.com/healthz`, que tendría que redirigir a HTTPS.
