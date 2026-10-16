# DESPLIEGUE.md — Despliegue con Docker (parte técnica de la fase J)

Léelo junto con `CLAUDE.md`, que sigue siendo la fuente de verdad. Aquí se describe lo que falta para que el sistema corra fuera de `runserver`: servidor de aplicación, archivos estáticos, configuración de producción, justificantes (`media/`), respaldo diario (RNF-08) y red. Si algo de este archivo contradice a `CLAUDE.md`, pregunta antes de cambiar cualquiera de los dos.

Fecha límite de entrega del proyecto: viernes 27/11/2026. La fase J es la única pendiente de la ruta crítica.

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
- Variables del `.env`: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `ASISTENCIA_MINIMA`. En desarrollo el usuario de la base es `root`.
- Bootstrap 5.3.3 se carga por CDN.
- Los justificantes se guardan en `media/justificantes/` con nombre aleatorio y se descargan solo por una vista del docente dueño del grupo (RNF-04). No tienen URL pública.
- Hoy no hay página 500 propia, y la contraseña de `seed_demo` está en el código (`PASSWORD_DEMO`) de un repositorio público.
- 406 pruebas en verde (`python manage.py test --noinput`, unos 7 minutos, necesita MySQL arriba).

Qué revisar primero: `config/settings.py` (¿lee `DEBUG`, `SECRET_KEY` y hosts del entorno?, ¿hay `STATIC_ROOT`?), `config/urls.py` (¿sirve `media/` solo con `DEBUG`?), la vista que entrega los justificantes, `docker-compose.yml`, `.env.example`, `.gitignore` y la plantilla base.

## 3. Antes de escribir código: pregunta a Victo

No elijas por él. Si no responde, usa el valor por defecto y anótalo en el README.

| # | Pregunta | Por defecto |
|---|---|---|
| 1 | ¿El sistema debe estar en internet, o basta una demo con `docker compose up` en una laptop o servidor de la facultad? | El mismo stack sirve para ambos casos |
| 2 | Si va a internet: ¿tiene un servidor donde correr Docker y un dominio apuntando a él? | Con dominio: HTTPS automático. Solo IP: HTTP y se advierte (las contraseñas viajarían sin cifrar; aceptable solo para una demo) |
| 3 | ¿La capacitación o la demo puede ser sin internet? | Si es posible, copiar Bootstrap a `static/` en vez de usar el CDN |
| 4 | ¿Dónde se guardan las copias de respaldo fuera de la misma máquina? | Solo local en `respaldos/`, con aviso en el README de que eso no protege contra la pérdida del servidor |
| 5 | ¿El servidor es Linux o Windows? | Linux. Si es Windows, el respaldo se programa con el Programador de tareas |

## 4. Reglas de trabajo

- Se aplican las de `CLAUDE.md` sección 5: commits pequeños en español, sin `Co-Authored-By`, sin tocar `models.py` ni migraciones sin avisar.
- Prefijos de commit: `RNF-08: ...` para el respaldo, `H-02: ...` para la página 500 y `Despliegue: ...` para el resto.
- **Pide aprobación a Victo, una sola vez, antes de agregar `gunicorn` y `whitenoise` a `requirements.txt`.** Ninguna otra dependencia sin preguntar. `gunicorn` no corre en Windows: solo se usa dentro del contenedor y el desarrollo local sigue con `runserver`.
- **Nunca uses `docker compose down -v`.** Protege el volumen de desarrollo `control_asistencia_mysql_data`. El stack de producción usa un nombre de proyecto propio (`name: control_asistencia_prod`) y volúmenes propios, para no chocar con el de desarrollo.
- No subas a Git: `.env`, `.env.prod`, `respaldos/`, ni datos de MySQL.
- Cada cambio de código lleva su prueba cuando se pueda probar sin Docker. Corre la suite completa al final de cada bloque que toque código Python.
- Si una prueba falla, dime la causa antes de corregir. No las marques como `skip` ni cambies una aserción para que pasen.

## 5. Bloques de trabajo

Haz commits entre bloques. No pases al siguiente si el anterior no cumple su criterio.

### B1. Inspección y preguntas
Lee lo indicado en la sección 2, haz las preguntas de la sección 3 y resume en pocas líneas qué encontraste (qué ya existe y qué falta). **No escribas código en este bloque.**

### B2. Configuración de producción y página 500 (H-02)
En `settings.py`, todo por variables de entorno, sin romper el desarrollo:
- `DJANGO_DEBUG` apagado por defecto en producción. Con `DEBUG=0`, si falta `DJANGO_SECRET_KEY` o tiene el valor del ejemplo, la aplicación debe negarse a arrancar (`ImproperlyConfigured`), no seguir con una clave débil.
- `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` (con esquema, por ejemplo `https://midominio.com`), como listas separadas por comas.
- Variable `DJANGO_HTTPS` (`1` en un servidor con HTTPS, `0` en demo local por HTTP). Con `1`: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` porque detrás del proxy Django ve HTTP. HSTS empieza con un valor bajo (`SECURE_HSTS_SECONDS` de 3600) y se sube después; uno largo en un dominio de prueba es difícil de revertir.
- Conserva `time_zone='+00:00'` en las opciones de conexión.
- Página 500: `templates/500.html` **independiente**, sin `{% extends %}` ni `{% url %}` ni `request.user`, porque Django la renderiza sin contexto y el error puede venir de la propia base de datos. En español, con un enlace simple al inicio (ruta fija).
- Prueba de la página 500 con `DEBUG=False`: una vista que lance una excepción y `Client(raise_request_exception=False)`; comprueba el código 500 y el contenido de la plantilla.

Criterio: `python manage.py check --deploy` con las variables de producción no muestra advertencias, o las que queden están anotadas y justificadas en el README. Suite completa en verde.

### B3. Archivos estáticos
- `STATIC_ROOT`, `whitenoise` en `MIDDLEWARE` justo después de `SecurityMiddleware`, y almacenamiento comprimido con manifiesto.
- **WhiteNoise sirve solo `static/`. `media/` no debe pasar por WhiteNoise ni por ninguna URL pública.** Comprueba que `config/urls.py` solo sirve `media/` con `DEBUG` y que los justificantes siguen saliendo únicamente por la vista.
- Si Victo respondió que la demo puede ser sin internet (pregunta 3), copia Bootstrap 5.3.3 (CSS y JS) a `static/` y ajusta la plantilla base para usarlo en lugar del CDN.

Criterio: con `DEBUG=0`, `collectstatic` termina sin errores y el CSS del admin y de la base cargan.

### B4. Imagen de la aplicación
- `Dockerfile` basado en Python 3.11 slim. `mysqlclient` se compila en Linux: instala las dependencias de compilación necesarias y no las dejes en la imagen final (por ejemplo, en dos etapas).
- Usuario sin privilegios (no `root`) con permiso de escritura sobre `media/`.
- `.dockerignore` (`.env*`, `.venv`, `.git`, `media/`, `respaldos/`, `__pycache__`).
- `collectstatic` durante la construcción de la imagen.
- Entrypoint: espera a que la base responda, ejecuta `python manage.py migrate --noinput` y luego `gunicorn config.wsgi` (a `0.0.0.0:8000`, 3 workers, `--timeout 30`, registro de accesos a la salida estándar).

### B5. `docker-compose.prod.yml` y `.env.prod.example`
Tres servicios:
- **`db`** (`mysql:8.0`): copia del compose de desarrollo las opciones que importan (`--log-bin-trust-function-creators=1`, UTC, utf8mb4). Crea una base y **un usuario propio de la aplicación con permisos solo sobre esa base** (`MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`); la aplicación no usa `root` en producción. `healthcheck` con `mysqladmin ping`. Volumen propio. **Sin `ports:`**: el 3306 no se publica; solo es visible dentro de la red de Docker.
- **`web`**: construida con el `Dockerfile`, `depends_on` con `condition: service_healthy`, `env_file: .env.prod`, `DB_HOST=db`, volumen nombrado para `media/`, `restart: unless-stopped`. Sin `ports:` hacia el host.
- **`proxy`** (`caddy:2`): publica 80 y 443 y reenvía a `web:8000`. El dominio sale de la variable `DOMINIO`: un dominio real activa HTTPS automático; `http://localhost` sirve para la demo local sin HTTPS. Agrega una regla defensiva que responda 404 a cualquier ruta `/media/*`. Volúmenes para los datos y la configuración de Caddy.

`.env.prod.example` con marcadores (`CAMBIA-ESTO`), nunca valores reales.

Criterio: desde cero, `docker compose -f docker-compose.prod.yml up -d --build` deja los tres servicios sanos; el usuario de la aplicación (sin `SUPER`) ejecuta `migrate` y **crea el disparador de la migración 0002**.

### B6. Respaldo diario y restauración (RNF-08)
Script `scripts/respaldo.sh` (bash; si Victo dijo que el servidor es Windows, agrega un equivalente en PowerShell):
- Volcado de la base: `mysqldump --single-transaction --routines --triggers`, ejecutado dentro del contenedor `db` con las credenciales de su propio entorno, comprimido con `gzip` a `respaldos/db_AAAA-MM-DD_HHMM.sql.gz`.
- Copia de `media/`: `tar` comprimido del volumen, hecho desde el contenedor `web` y escrito a `respaldos/media_AAAA-MM-DD_HHMM.tar.gz`.
- Usa `set -euo pipefail`. Si el volcado falla o el archivo queda vacío, el script sale con error y **no borra copias antiguas**.
- Retención: conserva las últimas 14 y borra solo archivos que coincidan con el patrón `db_*` y `media_*` dentro de `respaldos/`.
- `respaldos/` va en `.gitignore`, y los archivos con permisos restringidos: contienen nombres y matrículas de alumnos.
- La línea de `cron` lista para pegar (por ejemplo, diaria a las 3:00) y las instrucciones para instalarla van en el README. No puedes instalarla en el servidor de Victo.

**Restauración probada (obligatoria):** una copia que no se ha restaurado no es una copia. Restaura el volcado en una base temporal que tú crees (por ejemplo `restauracion_prueba`), compara el número de filas de `usuario`, `grupo`, `sesion`, `asistencia` y `bitacora_cambio` con la base real, confirma con `SHOW TRIGGERS` que el disparador existe, y elimina solo esa base temporal. Comprueba también que el tar de `media/` se extrae y contiene los justificantes. Documenta los pasos de restauración en el README.

### B7. Contraseña de demostración y README de despliegue
- `seed_demo` no debe poder crear cuentas con la contraseña por defecto cuando `DEBUG=0`: si falta `SEED_PASSWORD`, el comando se niega y explica por qué. Con `DEBUG=1` se comporta como hasta ahora. Agrega la prueba.
- En producción **no se ejecuta `seed_demo`**. El primer administrador se crea con `createsuperuser` y luego se cambia su rol a Administrador desde el admin (el README ya lo explica). Documéntalo en el flujo de despliegue.
- Sección "Despliegue" en el README: requisitos, creación de `.env.prod`, comando de arranque, primer administrador, cómo actualizar la aplicación (`git pull`, `up -d --build`), respaldo y restauración, y qué hacer si falla el disparador (error 1419).

### B8. Verificación en el stack real
Con el stack de producción levantado de verdad, comprueba y reporta cada punto de la sección 6. Si no puedes abrir el navegador, dime exactamente qué probar a mano y espera mi "listo".

## 6. Lista de verificación final

1. `docker compose -f docker-compose.prod.yml up -d --build` desde cero: los tres servicios sanos.
2. Un docente y un administrador inician sesión y ven sus pantallas.
3. El CSS de Bootstrap y el del admin cargan con `DEBUG=0`.
4. Pase de lista y una corrección: aparece la fila en la bitácora (el disparador funciona con el usuario de base de datos sin privilegios).
5. Se sube un justificante, se ejecuta `docker compose ... down` (**sin `-v`**) y `up -d`, y el justificante se sigue descargando por la vista.
6. Una URL directa a `/media/...` responde 404.
7. Una excepción provocada muestra la página 500 propia con `DEBUG=0`.
8. El 3306 no está publicado en el host (`docker compose ps` no muestra mapeo de puertos para `db`).
9. El respaldo genera los dos archivos, la restauración de prueba coincide y el disparador existe tras restaurar.
10. `python manage.py check --deploy` limpio, o con excepciones justificadas.
11. La suite completa sigue pasando (406 pruebas más las nuevas).
12. `git status` limpio, sin `.env*` ni `respaldos/` y el README actualizado.

## 7. Lo que no puedes hacer tú (le toca a Victo)

- Elegir y contratar el hosting, abrir el firewall (solo 22, 80 y 443; nunca el 3306) y apuntar el dominio al servidor.
- Instalar la tarea programada del respaldo en el servidor y definir dónde se guardan las copias fuera de la máquina.
- Decidir si el repositorio sigue público. La contraseña de demostración ya está en el historial de Git: cambiarla en el código no la borra, así que ninguna cuenta de demostración debe existir nunca en un entorno real. Además, cada commit lleva el correo del autor.
- Confirmar con su profesora el mínimo de asistencia (80 % es un supuesto) y si el sistema debe estar en internet.
- La capacitación a los docentes, el acta de aceptación firmada y la prueba de tiempo del RNF-01 con una persona real.

## 8. Cierre

- Corre la suite completa y confirma que todo pasa.
- Actualiza `CLAUDE.md`: en la sección 12, la fase J **no se marca como terminada**; deja anotado qué subtareas técnicas quedaron hechas (despliegue técnico, RNF-08, H-02, contraseña de demostración) y cuáles siguen pendientes (hosting, capacitación, acta). Anota las decisiones abiertas que queden.
- Resumen corto al terminar: qué quedó, qué falló si algo falló y qué necesitas de Victo.
