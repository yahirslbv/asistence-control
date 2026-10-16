# DESPLIEGUE.md — Despliegue con Docker (parte técnica de la fase J)

Léelo junto con `CLAUDE.md`, que sigue siendo la fuente de verdad. Aquí se describe lo que falta para que el sistema corra fuera de `runserver`: servidor de aplicación, archivos estáticos, configuración de producción, justificantes (`media/`), respaldo diario (RNF-08) y red. Si algo de este archivo contradice a `CLAUDE.md`, pregunta antes de cambiar cualquiera de los dos.

Fecha límite de entrega del proyecto: viernes 27/11/2026. La fase J es la única pendiente de la ruta crítica.

**Revisión del 15/10/2026.** Este documento se contrastó con el código y con pruebas desechables (sección 9). Las correcciones están en el historial de Git de este archivo: el primer commit es el texto original.

## 1. Alcance

**Dentro:**
1. Configuración de producción en `settings.py`, controlada por variables de entorno.
2. Archivos estáticos con `DEBUG=0` (WhiteNoise).
3. `Dockerfile`, entrypoint y `gunicorn`.
4. `docker-compose.prod.yml`: base de datos, aplicación y proxy.
5. `media/` persistente y nunca expuesta por una URL pública.
6. Respaldo diario de la base de datos y de `media/`, con restauración probada (RNF-08).
7. Página 500 propia (hallazgo H-02).
8. Protección de la contraseña de demostración de `seed_demo`.
9. Sección "Despliegue" en el README.

**Fuera (no lo hagas):** elegir proveedor de hosting, contratar o configurar un servidor, crear dominios, cambiar `models.py` o migraciones, nuevas funciones de la aplicación, manuales de usuario y de administrador (fase I), los hallazgos H-01 y H-03.

## 2. Estado de partida

Esto sale del README y del seguimiento. **Verifícalo leyendo el código antes de empezar; no lo des por cierto.**

- Django 5.2, Python 3.11, `mysqlclient`, MySQL 8.0 en Docker. MariaDB no sirve: el disparador de la bitácora (migración 0002) y las restricciones `CHECK` son de MySQL 8.
- `docker-compose.yml` (desarrollo): contenedor `control_asistencia_db`, volumen `control_asistencia_mysql_data`, puerto configurable con `DB_PORT`, arranca con `--log-bin-trust-function-creators=1`. El contenedor usa UTC y Django abre cada conexión con `time_zone='+00:00'`. **Conserva ambas cosas en producción.**
- Variables del `.env`: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` (por defecto `localhost,127.0.0.1`), `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `ASISTENCIA_MINIMA`. En desarrollo el usuario de la base es `root`.
- `config/settings.py` hoy: `DJANGO_DEBUG` **ya está apagado por defecto** y `DJANGO_ALLOWED_HOSTS` **ya se lee del entorno**. Lo que falta: rechazar una clave débil (el valor por defecto es `cambia-esto`), `CSRF_TRUSTED_ORIGINS`, las opciones de HTTPS, `STATIC_ROOT` y WhiteNoise. La conexión a MySQL ya fija `sql_mode` y `time_zone='+00:00'` en `init_command`: no pierdas ninguna de las dos.
- Bootstrap 5.3.3 se carga por CDN, con el atributo `integrity` (SRI) en las dos etiquetas (`<link>` y `<script>`) de `base.html`. La plantilla hace `{% load static %}` pero **no usa ninguna etiqueta `{% static %}`** y no existe `asistencia/static/`: hoy lo único que Django sirve como estático es el admin.
- Los justificantes se guardan en `media/justificantes/` con nombre aleatorio y se descargan solo por una vista del docente dueño del grupo (RNF-04). No tienen URL pública. `config/urls.py` **no sirve `media/` en ningún caso**, ni con `DEBUG`: hay que mantenerlo así, no hay nada que quitar.
- `.gitignore`: **ya corregido el 15/10/2026** (commit `a094f13`). Antes solo cubría `.env` exacto, y un `.env.prod` se habría subido a un repositorio público. Ahora cubre `.env.*` (menos `.env.example` y `.env.prod.example`) y `*.sql.gz`. Compruébalo con `git check-ignore -v .env.prod` antes de crear el archivo.
- Las pruebas del admin (`test_usuarios.py` y `test_bitacora_admin.py`) renderizan páginas que usan `{% static %}`: cualquier cambio del almacenamiento estático las afecta (ver B3).
- Hoy no hay página 500 propia (solo `403.html` y `404.html`), y la contraseña de `seed_demo` está en el código (`PASSWORD_DEMO`) de un repositorio público.
- 406 pruebas en verde (`python manage.py test --noinput`, unos 7 minutos, necesita MySQL arriba).

Qué confirmar antes de empezar, por si algo cambió desde el 15/10/2026: `config/settings.py`, `config/urls.py`, `docker-compose.yml`, `.env.example`, `.gitignore` y la plantilla base.

## 3. Antes de escribir código: pregunta a Victo

No elijas por él. Si no responde, usa el valor por defecto y anótalo en el README.

| # | Pregunta | Por defecto |
|---|---|---|
| 1 | ¿El sistema debe estar en internet, o basta una demo con `docker compose up` en una laptop o servidor de la facultad? | El mismo stack sirve para ambos casos |
| 2 | Si va a internet: ¿tiene un servidor donde correr Docker y un dominio apuntando a él? | Con dominio: HTTPS automático. Solo IP: HTTP y se advierte (las contraseñas viajarían sin cifrar; aceptable solo para una demo) |
| 3 | ¿La capacitación o la demo puede ser sin internet? | Si es posible, copiar Bootstrap a `static/` en vez de usar el CDN, con las precauciones de B3 (archivos `.map` y atributo `integrity`) |
| 4 | ¿Dónde se guardan las copias de respaldo fuera de la misma máquina? | Solo local en `respaldos/`, con aviso en el README de que eso no protege contra la pérdida del servidor |
| 5 | ¿El servidor es Linux o Windows? | Linux. Si es Windows, el respaldo se programa con el Programador de tareas |

## 4. Reglas de trabajo

- **Normas de Victo, siempre:** 1) **Planificar antes de actuar**: muestra el plan del bloque antes de escribir código. 2) **Ejecutar e iterar en Git**: un commit por paso verificable y `git push` al cerrar cada bloque. 3) **Validar con pruebas**: cada cambio se comprueba (con una prueba automática si se puede probar sin Docker; si no, con una comprobación reproducible) y el resultado se anota en el commit o en el resumen.
- Se aplican las de `CLAUDE.md` sección 5: commits pequeños en español, sin `Co-Authored-By`, sin tocar `models.py` ni migraciones sin avisar.
- Prefijos de commit: `RNF-08: ...` para el respaldo, `H-02: ...` para la página 500 y `Despliegue: ...` para el resto.
- **Pide aprobación a Victo, una sola vez, antes de agregar `gunicorn` y `whitenoise` a `requirements.txt`.** Ninguna otra dependencia sin preguntar. `gunicorn` no corre en Windows: solo se usa dentro del contenedor y el desarrollo local sigue con `runserver`. Puedes escribirlo con el marcador `gunicorn; sys_platform != "win32"` para no instalarlo en el equipo de desarrollo.
- **Nunca uses `docker compose down -v`.** Protege el volumen de desarrollo `control_asistencia_mysql_data`. El stack de producción usa un nombre de proyecto propio (`name: control_asistencia_prod`) y volúmenes propios, para no chocar con el de desarrollo.
- No subas a Git: `.env`, `.env.prod`, `respaldos/`, ni datos de MySQL. El `.gitignore` ya lo impide: no lo debilites, y antes de cada commit revisa `git status` en busca de archivos `.env*` o `respaldos/`.
- Cada cambio de código lleva su prueba cuando se pueda probar sin Docker. Corre la suite completa al final de cada bloque que toque código Python.
- Si una prueba falla, dime la causa antes de corregir. No las marques como `skip` ni cambies una aserción para que pasen.

## 5. Bloques de trabajo

Haz commits entre bloques. No pases al siguiente si el anterior no cumple su criterio.

### B1. Inspección y preguntas
Lee lo indicado en la sección 2, haz las preguntas de la sección 3 y resume en pocas líneas qué encontraste (qué ya existe y qué falta). **No escribas código en este bloque.**

### B2. Configuración de producción y página 500 (H-02)
En `settings.py`, todo por variables de entorno, sin romper el desarrollo:
- `DJANGO_DEBUG` **ya está apagado por defecto**: no lo cambies. Con `DEBUG=0`, si falta `DJANGO_SECRET_KEY`, está vacía o tiene el valor del ejemplo (`cambia-esto`), la aplicación debe negarse a arrancar (`ImproperlyConfigured`), no seguir con una clave débil. **Ojo con B4:** `collectstatic` durante la construcción de la imagen importa `settings.py` sin variables de entorno, así que esta regla lo aborta si no se le pasa una clave desechable en esa línea. Prueba la regla en un proceso aparte (`subprocess` con `DJANGO_DEBUG=0` y sin clave), no recargando `settings` dentro del proceso de pruebas.
- `DJANGO_ALLOWED_HOSTS` **ya existe**; agrega `DJANGO_CSRF_TRUSTED_ORIGINS` (con esquema, por ejemplo `https://midominio.com`). Las dos son listas separadas por comas.
- Variable `DJANGO_HTTPS` (`1` en un servidor con HTTPS, `0` en demo local por HTTP). Con `1`: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` porque detrás del proxy Django ve HTTP. HSTS empieza con un valor bajo (`SECURE_HSTS_SECONDS` de 3600) y se sube después; uno largo en un dominio de prueba es difícil de revertir.
- Conserva `time_zone='+00:00'` y `sql_mode` del `init_command` de la conexión.
- Página 500: `templates/500.html` **independiente**, sin `{% extends %}` ni `{% url %}` ni `request.user`, porque Django la renderiza sin contexto y el error puede venir de la propia base de datos. En español, con un enlace simple al inicio (ruta fija).
- Prueba de la página 500 con `DEBUG=False`: una vista que lance una excepción y `Client(raise_request_exception=False)`; comprueba el código 500 y el contenido de la plantilla.

Criterio: `python manage.py check --deploy` con las variables de producción no muestra advertencias, o las que queden están anotadas y justificadas en el README. **Línea base medida el 15/10/2026** con `DEBUG=0` y una clave larga, antes de cualquier cambio: 4 advertencias (`W004` HSTS, `W008` redirección SSL, `W012` cookie de sesión, `W016` cookie CSRF). Con `DJANGO_HTTPS=1` deberían desaparecer `W004`, `W012` y `W016`. `W008` (`SECURE_SSL_REDIRECT`) se queda porque la redirección a HTTPS la hace Caddy: anótala y justifícala en el README. Suite completa en verde.

### B3. Archivos estáticos
- `STATIC_ROOT`, `whitenoise` en `MIDDLEWARE` justo después de `SecurityMiddleware`, y almacenamiento comprimido con manifiesto en `STORAGES['staticfiles']`.
- **El manifiesto se activa solo por una variable de entorno (`DJANGO_STATIC_MANIFEST=1`), nunca por defecto.** Comprobado el 15/10/2026: con el manifiesto activo y sin `collectstatic` previo, 7 de 11 pruebas del admin fallan con `Missing staticfiles manifest entry for 'admin/css/base.css'`, porque el ejecutor de pruebas fuerza `DEBUG=False`. Fija la variable con `ENV DJANGO_STATIC_MANIFEST=1` en el `Dockerfile` para que `collectstatic` (al construir) y `gunicorn` (al correr) usen el mismo almacenamiento. En desarrollo y en las pruebas la variable no existe y todo queda como hoy: sin ella, las 11 pruebas pasan; con ella y el manifiesto ya generado, también.
- **WhiteNoise sirve solo `static/`. `media/` no debe pasar por WhiteNoise ni por ninguna URL pública.** `config/urls.py` hoy **no sirve `media/` ni con `DEBUG`**, así que no hay nada que quitar: no agregues nunca `static(settings.MEDIA_URL, ...)`. La prueba `test_no_hay_url_publica_del_archivo`, de `test_justificantes.py`, ya lo protege; confirma que sigue pasando después de instalar WhiteNoise.
- Si Victo respondió que la demo puede ser sin internet (pregunta 3), copia Bootstrap 5.3.3 (CSS y JS) a `static/` y ajusta la plantilla base para usarlo en lugar del CDN, con tres precauciones comprobadas el 15/10/2026:
  1. Copia también los archivos `.map`. Con el manifiesto, si el CSS apunta a un mapa ausente, `collectstatic` falla con `ValueError: The file 'css/bootstrap.min.css.map' could not be found`.
  2. **Quita el atributo `integrity` de las dos etiquetas** (`<link>` y `<script>`). El manifiesto reescribe dentro del CSS la referencia al `.map`, así que el archivo servido ya no coincide con el hash del CDN y el navegador lo bloquearía.
  3. Usa `{% static 'vendor/bootstrap/...' %}`; la plantilla ya hace `{% load static %}`.

Criterio: con `DEBUG=0` y `DJANGO_STATIC_MANIFEST=1`, `collectstatic` termina sin errores y el CSS del admin y de la base cargan; y la suite completa sigue en verde **sin** esa variable.

### B4. Imagen de la aplicación
- `Dockerfile` basado en Python 3.11 slim. `mysqlclient` se compila en Linux: instala las dependencias de compilación necesarias y no las dejes en la imagen final (por ejemplo, en dos etapas).
- Usuario sin privilegios (no `root`) con permiso de escritura sobre `media/`.
- `.dockerignore` (`.env*`, `.venv`, `.git`, `media/`, `respaldos/`, `__pycache__`).
- `ENV DJANGO_STATIC_MANIFEST=1` (ver B3) y luego `collectstatic` durante la construcción, **con una clave desechable solo en esa línea**: `RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY=solo-para-construir-la-imagen python manage.py collectstatic --noinput`. Comprobado el 15/10/2026: sin ella, la regla de B2 aborta la construcción con `ImproperlyConfigured`; con ella termina bien. No es un secreto (el contenedor real usa la clave de `.env.prod`) y nunca debe ser el valor del ejemplo.
- Entrypoint: espera a que la base responda, ejecuta `python manage.py migrate --noinput` y luego `gunicorn config.wsgi` (a `0.0.0.0:8000`, 3 workers, `--timeout 30`, registro de accesos a la salida estándar).

### B5. `docker-compose.prod.yml` y `.env.prod.example`
Tres servicios:
- **`db`** (`mysql:8.0`): copia del compose de desarrollo las opciones que importan (`--log-bin-trust-function-creators=1`, UTC, utf8mb4). Crea una base y **un usuario propio de la aplicación con permisos solo sobre esa base** (`MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`); la aplicación no usa `root` en producción. `healthcheck` con `mysqladmin ping`. Volumen propio. **Sin `ports:`**: el 3306 no se publica; solo es visible dentro de la red de Docker. **`MYSQL_USER`, `MYSQL_PASSWORD` y `MYSQL_DATABASE` solo se aplican al primer arranque del volumen.** Comprobado el 15/10/2026: tras cambiar `MYSQL_PASSWORD` y reiniciar con el mismo volumen, la contraseña nueva no entra y la original sigue entrando. Para cambiarla después, usa `ALTER USER` dentro de MySQL y luego actualiza `.env.prod`; documéntalo en el README.
- **`web`**: construida con el `Dockerfile`, `depends_on` con `condition: service_healthy`, `env_file: .env.prod`, `DB_HOST=db`, volumen nombrado para `media/`, `restart: unless-stopped`. Sin `ports:` hacia el host. Con `healthcheck` propio que pida `/login/` al contenedor **mandando un `Host` válido** (el primero de `DJANGO_ALLOWED_HOSTS`): comprobado que con `ALLOWED_HOSTS=['midominio.com']` una petición con `Host: 127.0.0.1` o `Host: localhost` recibe 400, así que un healthcheck ingenuo marcaría el servicio como no sano aunque funcione. El `proxy` depende de que `web` esté sano.
- **`proxy`** (`caddy:2`): publica 80 y 443 y reenvía a `web:8000`. El dominio sale de la variable `DOMINIO`: un dominio real activa HTTPS automático; `http://localhost` sirve para la demo local sin HTTPS. Agrega una regla defensiva que responda 404 a cualquier ruta `/media/*`. Volúmenes para los datos y la configuración de Caddy.

`.env.prod.example` con marcadores (`CAMBIA-ESTO`), nunca valores reales. **Antes del primer commit de este bloque**, `git check-ignore -v .env.prod` debe mostrar la regla del `.gitignore`: solo `.env.prod.example` se versiona.

Criterio: desde cero, `docker compose -f docker-compose.prod.yml up -d --build` deja los tres servicios sanos; el usuario de la aplicación (sin `SUPER`) ejecuta `migrate` y **crea el disparador de la migración 0002**. Comprobado el 15/10/2026 en un MySQL 8.0.46 desechable: con `--log-bin-trust-function-creators=1`, un usuario con permisos solo sobre su base crea el disparador y este escribe en la bitácora; sin la bandera falla con el error 1419.

### B6. Respaldo diario y restauración (RNF-08)
Script `scripts/respaldo.sh` (bash; si Victo dijo que el servidor es Windows, agrega un equivalente en PowerShell):
- Volcado de la base: `mysqldump --single-transaction --routines --triggers --no-tablespaces`, ejecutado dentro del contenedor `db` con las credenciales de su propio entorno, comprimido con `gzip` a `respaldos/db_AAAA-MM-DD_HHMM.sql.gz`. La contraseña va en la variable `MYSQL_PWD` del `exec`, no con `-p` en la línea de comandos. Sin `--no-tablespaces`, el usuario de la aplicación imprime `Access denied; you need (at least one of) the PROCESS privilege(s)`; comprobado el 15/10/2026 que aun así el volcado sale completo y con código de salida 0, pero ese mensaje llegaría cada día al correo del cron.
- Con `docker compose exec` usa `-T`, rutas absolutas y `-f`/`-p` explícitos (`-f /ruta/docker-compose.prod.yml -p control_asistencia_prod`), porque cron no hereda tu directorio. En el Compose v5.5.1 de este equipo `exec` sin `-T` también funcionó sin terminal, pero `-T` es inocuo y evita depender de la versión; pruébalo ejecutando el script con `< /dev/null`.
- Copia de `media/`: `tar` comprimido del volumen, hecho desde el contenedor `web` y escrito a `respaldos/media_AAAA-MM-DD_HHMM.tar.gz`.
- Usa `set -euo pipefail`. Si el volcado falla o el archivo queda vacío, el script sale con error y **no borra copias antiguas**.
- Retención: conserva las últimas 14 y borra solo archivos que coincidan con el patrón `db_*` y `media_*` dentro de `respaldos/`.
- `respaldos/` va en `.gitignore`, y los archivos con permisos restringidos: contienen nombres y matrículas de alumnos.
- La línea de `cron` lista para pegar (por ejemplo, diaria a las 3:00) y las instrucciones para instalarla van en el README. No puedes instalarla en el servidor de Victo.

**Restauración probada (obligatoria):** una copia que no se ha restaurado no es una copia. Restaura el volcado en una base temporal que tú crees (por ejemplo `restauracion_prueba`), compara el número de filas de `usuario`, `grupo`, `sesion`, `asistencia` y `bitacora_cambio` con la base real, confirma con `SHOW TRIGGERS` que el disparador existe, y elimina solo esa base temporal. Comprueba también que el tar de `media/` se extrae y contiene los justificantes. Documenta los pasos de restauración en el README. Dos hechos comprobados el 15/10/2026 que cambian cómo se hace:
- **La restauración de prueba se hace como `root`** (`MYSQL_ROOT_PASSWORD` del contenedor `db`). El usuario de la aplicación solo tiene permisos sobre su base y no puede crear `restauracion_prueba` (`ERROR 1044 Access denied`).
- **El disparador se guarda con `DEFINER=` el usuario de la aplicación.** Si se restaura en un servidor donde ese usuario no existe, **todo `UPDATE` sobre `asistencia` falla** con `ERROR 1449: The user specified as a definer ... does not exist`. Se reprodujo con un `UPDATE` de `estado` y con uno que solo cambia la columna `justificante`, así que ni corregir ni adjuntar un justificante funcionarían. Para restaurar en un servidor nuevo, levanta primero el stack con el mismo `.env.prod` (el contenedor crea `MYSQL_USER`) y restaura después. Añade a la restauración de prueba un `UPDATE` de `estado` dentro de una transacción con `ROLLBACK` sobre la copia, que no debe dar el error 1449. Explícalo en el README.

### B7. Contraseña de demostración y README de despliegue
- `seed_demo` no debe poder crear cuentas con la contraseña por defecto cuando `DEBUG=0`: si falta `SEED_PASSWORD`, el comando se niega y explica por qué. Con `DEBUG=1` se comporta como hasta ahora. Agrega la prueba.
- En producción **no se ejecuta `seed_demo`**. El primer administrador se crea con `createsuperuser` y luego se cambia su rol a Administrador desde el admin (el README ya lo explica). Documéntalo en el flujo de despliegue.
- Sección "Despliegue" en el README: requisitos, creación de `.env.prod`, comando de arranque, primer administrador, cómo actualizar la aplicación (`git pull`, `up -d --build`), respaldo y restauración, y qué hacer si falla el disparador (error 1419).

### B8. Verificación en el stack real
Con el stack de producción levantado de verdad, comprueba y reporta cada punto de la sección 6. Si no puedes abrir el navegador, dime exactamente qué probar a mano y espera mi "listo".

## 6. Lista de verificación final

1. `docker compose -f docker-compose.prod.yml up -d --build` desde cero: los tres servicios sanos (el `healthcheck` de `web` en verde, con un `Host` válido). Que `migrate` corra dentro del contenedor prueba a la vez que `mysqlclient` compiló en Linux y que la autenticación contra MySQL 8 funciona (ver la sección 9, «No comprobado»).
2. Un docente y un administrador inician sesión y ven sus pantallas.
3. El CSS de Bootstrap y el del admin cargan con `DEBUG=0` (si se autoaloja Bootstrap, sin el atributo `integrity`).
4. Pase de lista y una corrección: aparece la fila en la bitácora (el disparador funciona con el usuario de base de datos sin privilegios).
5. Se sube un justificante, se ejecuta `docker compose ... down` (**sin `-v`**) y `up -d`, y el justificante se sigue descargando por la vista.
6. Una URL directa a `/media/...` responde 404.
7. Una excepción provocada muestra la página 500 propia con `DEBUG=0`.
8. El 3306 no está publicado en el host (`docker compose ps` no muestra mapeo de puertos para `db`).
9. El respaldo genera los dos archivos, la restauración de prueba (como `root`) coincide, el disparador existe tras restaurar y un `UPDATE` de `estado` con `ROLLBACK` sobre la copia no da el error 1449.
10. `python manage.py check --deploy` limpio, o solo con `W008` (la redirección a HTTPS la hace Caddy) justificada en el README. La línea base era de 4 advertencias.
11. La suite completa sigue pasando (406 pruebas más las nuevas) **sin** `DJANGO_STATIC_MANIFEST`, y `collectstatic` durante la construcción de la imagen termina bien con la clave desechable.
12. `git status` limpio, sin `.env*` ni `respaldos/` y el README actualizado; `git check-ignore -v .env.prod` muestra la regla del `.gitignore`.

## 7. Lo que no puedes hacer tú (le toca a Victo)

- Elegir y contratar el hosting, abrir el firewall (solo 22, 80 y 443; nunca el 3306) y apuntar el dominio al servidor.
- Instalar la tarea programada del respaldo en el servidor y definir dónde se guardan las copias fuera de la máquina.
- Decidir si el repositorio sigue público. La contraseña de demostración ya está en el historial de Git: cambiarla en el código no la borra, así que ninguna cuenta de demostración debe existir nunca en un entorno real. Además, cada commit lleva el correo del autor.
- Confirmar con su profesora el mínimo de asistencia (80 % es un supuesto) y si el sistema debe estar en internet.
- La capacitación a los docentes, el acta de aceptación firmada y la prueba de tiempo del RNF-01 con una persona real.
- Programar la fase I (manuales de usuario y de administrador): en el cronograma, la actividad J depende de H **e I**, y sin los manuales no se puede firmar el acta. Este documento la deja fuera a propósito.

## 8. Cierre

- Corre la suite completa y confirma que todo pasa.
- Actualiza `CLAUDE.md`: la sección 4 (estructura) con los archivos nuevos (`Dockerfile`, `docker-compose.prod.yml`, `.dockerignore`, `.env.prod.example`, `scripts/` y los demás que crees), la sección 13 (comandos de despliegue) y la sección 12: la fase J **no se marca como terminada**; deja anotado qué subtareas técnicas quedaron hechas (despliegue técnico, RNF-08, H-02, contraseña de demostración) y cuáles siguen pendientes (hosting, capacitación, acta). Anota las decisiones abiertas que queden.
- Si tienes acceso al tablero de Trello, marca en la tarjeta J solo las subtareas técnicas hechas (respaldo diario, contraseña de demostración, página 500) y actualiza `docs/seguimiento_semanal.md`.
- Resumen corto al terminar: qué quedó, qué falló si algo falló y qué necesitas de Victo.

## 9. Comprobaciones del 15/10/2026

Se hicieron en un MySQL 8.0.46 desechable (eliminado al terminar), con configuraciones de prueba fuera del repositorio y sobre el código tal como estaba. Las cifras y los mensajes de error de este documento salen de aquí.

| Comprobación | Resultado |
|---|---|
| `.gitignore` con `.env.*` | 8 nombres que deben ignorarse y 7 que deben versionarse: 15 de 15 correctos; ningún archivo ya versionado quedó afectado |
| Manifiesto de estáticos y pruebas del admin | Sin la variable: 11 de 11 pruebas pasan. Con manifiesto y sin `collectstatic` previo: 7 de 11 fallan (`Missing staticfiles manifest entry`). Con `collectstatic` previo: 11 de 11 |
| Bootstrap autoalojado con manifiesto | `collectstatic` falla sin el `.map` (`ValueError`) y pasa con él; el CSS servido trae la referencia al `.map` reescrita |
| Clave obligatoria frente a `collectstatic` | Sin clave: `ImproperlyConfigured`. Con una clave desechable en esa línea: termina bien |
| `ALLOWED_HOSTS` de producción frente a un `healthcheck` | `Host: 127.0.0.1` y `localhost` dan 400; el dominio da 200 |
| `check --deploy` sobre la configuración actual | 4 advertencias: `W004`, `W008`, `W012`, `W016` |
| Disparador creado por un usuario sin `SUPER` | Funciona con `--log-bin-trust-function-creators=1` y escribe en la bitácora; sin la bandera, error 1419 |
| `mysqldump` con el usuario de la aplicación | Error de privilegio `PROCESS` en la salida de errores, código de salida 0 y archivo completo que incluye el disparador; con `--no-tablespaces` no hay error |
| Restauración | Como `root`: mismas filas y un disparador. El usuario de la aplicación no puede crear la base temporal (error 1044) |
| Usuario `DEFINER` ausente | `UPDATE` de `estado` y de `justificante`: ambos fallan con el error 1449 |
| `MYSQL_USER` y `MYSQL_PASSWORD` | Solo se aplican al primer arranque del volumen; la contraseña nueva no entra y la original sí |
| `docker compose exec` sin `-T` y sin terminal | Funcionó en Compose v5.5.1 |
| `test_no_hay_url_publica_del_archivo` | Pasa hoy |

**No comprobado** (verifícalo al llegar al bloque correspondiente y repórtalo):
- Que `mysqlclient` compile en una imagen `python:3.11-slim` de Debian y conecte a MySQL 8 con su método de autenticación por defecto (`caching_sha2_password`). El equipo de desarrollo es Windows y usa una rueda ya compilada. Se verifica en B4/B5 con `migrate` dentro del contenedor.
- La configuración concreta de Caddy, el comportamiento de `gunicorn` y el stack de producción completo: todavía no existen.
- Que `W004`, `W012` y `W016` desaparezcan con `DJANGO_HTTPS=1`: se espera por cómo se definen, pero no se midió.
