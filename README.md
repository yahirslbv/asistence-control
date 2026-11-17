# Sistema de Control de Asistencia

Aplicación web en Django que sustituye el pase de lista en papel. Proyecto de la
materia Administración de Proyectos de Software (UABC, FCITEC).

Módulos: autenticación y usuarios, grupos, sesiones, asistencia y reportes.
El detalle de requisitos, reglas de negocio y plan por fases está en
[CLAUDE.md](CLAUDE.md), que es la fuente de verdad del proyecto.

**Si vas a usar el sistema como docente, empieza por el [manual de usuario](docs/manual_usuario.md). Si lo vas a administrar, por el [manual del administrador](docs/manual_administrador.md).**

## Requisitos

- Python 3.10 o superior (se probó con 3.11)
- Docker Desktop, o un MySQL 8 propio. MariaDB no sirve: el disparador de la
  bitácora y las restricciones `CHECK` están escritos para MySQL 8.
- Git

## Instalación

Los comandos son para Windows (PowerShell). En Linux o macOS cambia la
activación del entorno por `source .venv/bin/activate`.

```powershell
# 1. Entorno virtual y dependencias
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Configuración. Edita .env si cambias algún dato de MySQL.
copy .env.example .env

# 3. Base de datos MySQL 8 en Docker (con Docker Desktop abierto)
docker compose up -d

# 4. Tablas y disparador de la bitácora
python manage.py migrate

# 5. Datos de demostración (opcional; se puede repetir sin duplicar nada)
python manage.py seed_demo

# 6. Servidor de desarrollo
python manage.py runserver
```

Abre <http://127.0.0.1:8000/>.

Si `mysqlclient` no se instala en tu equipo, usa `PyMySQL`: instálalo y agrega
`import pymysql; pymysql.install_as_MySQLdb()` al inicio de `manage.py` y de
`config/wsgi.py`.

### Notas sobre MySQL

- **Datos:** viven en el volumen de Docker `control_asistencia_mysql_data`, fuera
  de la carpeta del proyecto. `docker compose down` los conserva y
  `docker compose down -v` los borra.
- **Puerto ocupado:** si el 3306 lo usa otro programa (por ejemplo XAMPP), pon
  `DB_PORT=3307` en `.env`. Tanto `docker-compose.yml` como Django leen ese valor.
- **Error 1419 al crear el disparador:** MySQL 8 tiene el registro binario
  activo por defecto y, con él, no deja crear disparadores a un usuario sin el
  privilegio SUPER. El contenedor ya arranca con
  `--log-bin-trust-function-creators=1` (en `docker-compose.yml`), así que con
  Docker no aparece; se corrigió ahí y no en la migración. Con un MySQL propio,
  ejecuta `SET GLOBAL log_bin_trust_function_creators = 1;` (se pierde al
  reiniciar el servidor; para fijarlo, agrégalo a su archivo de configuración).
- **Un MySQL propio** en lugar de Docker: omite el paso 3, crea la base
  `control_asistencia` con `utf8mb4` y ajusta las variables `DB_*` del `.env`.
- **Zona horaria:** el contenedor usa UTC y Django abre cada conexión con
  `time_zone='+00:00'`, para que `NOW()` del disparador y las fechas que guarda
  Django estén en la misma zona.

### Variables de entorno (`.env`)

| Variable | Para qué sirve |
|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django. Cámbiala en cualquier entorno compartido. Con `DJANGO_DEBUG=0` es obligatoria: la aplicación no arranca si falta o es la del ejemplo |
| `DJANGO_DEBUG` | `1` en desarrollo, `0` en producción |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Conexión a MySQL. Con Docker, `DB_PASSWORD` es también la contraseña de `root` del contenedor |
| `ASISTENCIA_MINIMA` | Porcentaje mínimo de asistencia (por defecto 80) |
| `REGISTRO_DOMINIOS` | Dominios de correo que pueden registrarse solos desde la pantalla de acceso (RF-19), separados por comas. Por defecto `uabc.edu.mx`. Vacía, cierra el registro |

## Usuarios

`seed_demo` crea tres cuentas, que entran con su **correo**:

| Correo | Rol |
|---|---|
| `admin@asistencia.test` | Administrador |
| `docente1@asistencia.test` | Docente |
| `docente2@asistencia.test` | Docente |

La contraseña de demostración está en `PASSWORD_DEMO`, dentro de
`asistencia/management/commands/seed_demo.py`. Se cambia con la variable de
entorno `SEED_PASSWORD` antes de ejecutar el comando. Con `DJANGO_DEBUG=0` esa variable es
obligatoria: `seed_demo` se niega a usar la contraseña del código, que es pública.

### Alta de usuarios y roles (RF-16)

El administrador da de alta a los usuarios desde el admin de Django
(<http://127.0.0.1:8000/admin/>, sección **Usuarios**), con nombre, apellido,
correo, rol, usuario y contraseña. Un administrador ve esa sección y la de **Periodos**, y nada más.

- **El rol manda sobre el acceso.** Al guardar, el sistema ajusta `is_staff` y los
  permisos según el rol: un administrador puede entrar al admin y gestionar
  usuarios (y nada más); un docente no entra al admin. No hace falta marcar nada
  más ni asignar permisos a mano.
- **Los usuarios no se borran, se desactivan** con la casilla «Activo». Un usuario
  desactivado ya no puede iniciar sesión.
- **No se puede desactivar** ni quitar el rol al **último administrador activo**, ni
  desactivarse a uno mismo.

`createsuperuser` crea el usuario con rol **docente** (y como superusuario sí entra
al admin). Para que sea también administrador de la aplicación, entra al admin con
ese usuario, abre su ficha y cambia el rol a Administrador.

### Panel del administrador (RF-20)

Al iniciar sesión, el administrador llega a su **Panel** (<http://127.0.0.1:8000/panel/>).
Ahí ve cuántas cuentas esperan aprobación, cuántos docentes y administradores activos
hay, el periodo activo, y tiene accesos directos a **Usuarios**, **Agregar usuario** y
**Periodos** (las pantallas del admin de Django). El panel no muestra los grupos de los
docentes. Un docente que abra esa dirección recibe un 403.

### Registro de docentes y aprobación (RF-19)

En la pantalla de acceso, «Si no tienes cuenta, regístrate aquí» lleva al registro
(<http://127.0.0.1:8000/registro/>): nombre, apellido, correo y contraseña. Condiciones:

- **Dominio permitido.** El correo debe ser de un dominio de `REGISTRO_DOMINIOS` (por
  defecto `uabc.edu.mx`; el dominio es exacto, no valen subdominios). Con la variable
  vacía el registro se cierra y el enlace desaparece.
- **Aprobación del administrador.** La cuenta queda pendiente y no puede iniciar sesión.
  Quien lo intenta con su contraseña correcta ve «Tu cuenta está pendiente de
  aprobación». El administrador la **aprueba o la rechaza** desde su Panel.
- **Siempre docente.** El formulario no pregunta el rol y no se puede forzar: un
  administrador solo lo da de alta otro administrador (RF-16).
- **Rechazar** desactiva la cuenta (no se borra). Si fue un error, se reactiva con
  «Activo» en **Usuarios** y vuelve a aparecer en el Panel para aprobarla.
- **Sin confirmación por correo:** la aplicación no envía correos; la aprobación del
  administrador es el control que verifica a la persona.

Para probarlo con los datos de demostración: regístrate con un correo `@uabc.edu.mx`,
entra como `admin@asistencia.test` y aprueba la cuenta desde el Panel.

### Periodos escolares (RF-17)

El administrador gestiona los periodos en el admin (**Periodos**): crea uno con su
clave (`AAAA-N`, por ejemplo `2027-1`) y sus fechas, y lo **activa** o **desactiva**
con el botón de su fila. Para crearlo y activarlo de una vez, usa **Guardar y activar**.

- **Solo un periodo está activo a la vez.** Activar uno desactiva el que estuviera
  activo. Un docente solo puede crear grupos nuevos en el periodo activo; sin uno,
  el formulario lo avisa y pide al administrador que active uno.
- **Un periodo inactivo congela sus grupos.** Siguen visibles, con sus reportes y
  exportaciones, pero en solo lectura: no se pasa lista, no se corrige, no se
  cambian sesiones, alumnos ni justificantes. Reactivar el periodo lo devuelve todo.
- **Los periodos no se borran.** La clave solo se corrige mientras no tenga grupos.
- Al actualizar desde una versión anterior, `python manage.py migrate` crea un periodo
  por cada uno que ya usaban los grupos y deja activo el más reciente.

## Justificantes y la carpeta `media/`

Los justificantes (RF-12) se adjuntan desde la pantalla de corrección de una
sesión, solo a registros marcados como justificado. Se aceptan PDF, JPG y PNG de
hasta 5 MB.

Se guardan en `media/justificantes/` con un nombre aleatorio y **no están en Git**
(`media/` está en `.gitignore`). Al hacer respaldos, copia esa carpeta además de la
base de datos: sin ella, los registros conservarían el vínculo pero no el archivo.
El respaldo de la pila de producción ya la incluye (ver [Respaldo y restauración](#respaldo-y-restauración-rnf-08)).
Los archivos no tienen una URL pública: solo se descargan desde la aplicación, por
el docente dueño del grupo.

## Pruebas

```powershell
python manage.py test
```

El usuario de MySQL necesita permiso para crear la base `test_control_asistencia`
(`root` en el contenedor ya lo tiene). La suite completa (683 pruebas) tarda entre nueve y quince minutos.

Los resultados de las pruebas de la fase H (flujos de extremo a extremo, matriz de
acceso, mediciones del RNF-07, revisión responsiva y hallazgos) están en
[docs/informe_pruebas.md](docs/informe_pruebas.md).

## Despliegue

La aplicación se despliega con Docker, en una pila de tres servicios
(`docker-compose.prod.yml`): `db` (MySQL 8), `web` (la aplicación con gunicorn) y
`proxy` (Caddy, el único que publica puertos). El detalle técnico y las
comprobaciones están en [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md); el plan de la
versión, en [docs/plan_liberacion.md](docs/plan_liberacion.md).

La pila es la misma para una demostración local y para un servidor con dominio:
solo cambian los valores de `.env.prod`. **El hosting decidido para la entrega es
la demostración local** (16/11/2026); el despliegue con dominio queda documentado,
pero no se ha ejecutado.

### Demostración local con un comando (Windows)

Con Docker Desktop abierto y los puertos 80 y 443 libres, desde la carpeta del proyecto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo.ps1
```

La primera vez el script crea `.env.prod` (con una clave y contraseñas al azar),
construye la imagen y levanta la pila; tarda unos minutos y necesita internet.
Las siguientes veces solo la levanta. Después abre <http://localhost>.

Para tener cuentas y datos de ejemplo, elige una contraseña y ejecuta una vez:

```powershell
docker compose -f docker-compose.prod.yml exec -e SEED_PASSWORD=la-que-elijas web python manage.py seed_demo
```

Crea las tres cuentas de la sección [Usuarios](#usuarios) con esa contraseña. Con
`DJANGO_DEBUG=0`, `seed_demo` se niega a usar la contraseña de demostración del
código, porque está publicada en el repositorio.

Para apagar la demostración, sin perder los datos:

```powershell
docker compose -f docker-compose.prod.yml down
```

**Nunca uses `down -v`:** borra la base de datos y los justificantes.

Qué tener en cuenta:

- **Entra por `http://localhost`, no por `http://127.0.0.1`.** El proxy solo
  atiende el nombre de `DOMINIO`; con otro, responde una página en blanco.
- **Va por HTTP.** Las contraseñas viajan sin cifrar: es aceptable solo en tu
  propio equipo. Con un dominio real, Caddy sirve HTTPS (ver más abajo).
- **Necesita internet.** Bootstrap se carga desde un CDN; sin conexión las
  pantallas pierden el estilo base.
- **No borres `.env.prod`.** Guarda las contraseñas de la base, que MySQL solo
  toma la primera vez. Si falta y la base ya existe, `demo.ps1` se detiene y lo avisa.
- **Para verla desde un teléfono u otro equipo de la misma red:** en `.env.prod`
  pon `DOMINIO=:80` y agrega la IP de tu equipo a `DJANGO_ALLOWED_HOSTS`
  (`localhost,192.168.1.50`); vuelve a ejecutar `demo.ps1` y entra por esa IP.
- **Puerto 80 ocupado:** define `PUERTO_HTTP` antes de levantarla
  (`$env:PUERTO_HTTP = "8080"`) y entra por <http://localhost:8080>.

### Despliegue en un servidor

Requisitos: Docker con Compose, Git y, para HTTPS, un dominio que apunte al
servidor, con los puertos 80 y 443 abiertos (nunca el 3306).

```bash
git clone https://github.com/yahirslbv/asistence-control.git
cd asistence-control
git checkout v1.0.0                  # se despliega una etiqueta, no main
cp .env.prod.example .env.prod       # y cambia todos los CAMBIA-ESTO
git check-ignore -v .env.prod        # debe mostrar la regla de .gitignore
docker compose -f docker-compose.prod.yml up -d --build
```

Al arrancar, el contenedor `web` espera a la base y ejecuta `migrate`, que crea
las tablas y el disparador de la bitácora con el usuario de la aplicación. Después:

1. **Primer administrador.** En un sistema en uso **no se ejecuta `seed_demo`**:

   ```bash
   docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
   ```

   Entra a `/admin/` con ese usuario, abre su ficha y cambia el rol a
   Administrador (ver [Alta de usuarios y roles](#alta-de-usuarios-y-roles-rf-16)).
2. **Primer periodo.** El administrador crea y activa un periodo en **Periodos**;
   sin periodo activo los docentes no pueden crear grupos.
3. **Respaldo diario.** Programa el respaldo y ejecútalo una vez a mano
   (ver [Respaldo y restauración](#respaldo-y-restauración-rnf-08)).
4. **Prueba de humo.** Inicia sesión, abre un grupo, visita una dirección que no
   exista (debe salir la página 404 propia) y confirma que `/media/` responde 404.

### Variables de `.env.prod`

| Variable | Para qué sirve |
|---|---|
| `DOMINIO` | Dirección que atiende el proxy. `http://localhost` para la demostración; `:80` para HTTP con cualquier nombre o IP; un dominio real (`asistencia.midominio.com`) activa HTTPS automático |
| `DJANGO_ALLOWED_HOSTS` | Nombres con los que se entra al sitio, separados por comas. El primero se usa para comprobar la salud del contenedor |
| `DJANGO_HTTPS` | `1` solo cuando el sitio se sirve por HTTPS. Activa las cookies «solo HTTPS», HSTS de una hora y la cabecera del proxy. Con `1` y por HTTP nadie podría iniciar sesión |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Orígenes de confianza para los formularios, con esquema (`https://midominio.com`). Normalmente vacía |
| `DJANGO_DEBUG` | Siempre `0` |
| `DJANGO_SECRET_KEY` | Clave larga y aleatoria. Con `DJANGO_DEBUG=0` la aplicación **no arranca** si falta, está vacía o es la de un archivo de ejemplo |
| `MYSQL_ROOT_PASSWORD` | Contraseña de `root` de MySQL. La aplicación no la recibe; sirve para administrar y restaurar |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Base y usuario propios de la aplicación, sin privilegios fuera de su base |
| `ASISTENCIA_MINIMA`, `REGISTRO_DOMINIOS` | Igual que en desarrollo |

Si una contraseña de la base falta o sigue en `CAMBIA-ESTO`, el servicio `db` se
niega a arrancar y lo dice en sus registros (`docker compose -f docker-compose.prod.yml logs db`).

`DJANGO_STATIC_MANIFEST=1` lo fija la imagen: hace que los archivos estáticos se
sirvan con una huella en el nombre. No se define en desarrollo ni en las pruebas.

**Las contraseñas de la base solo se aplican la primera vez.** MySQL crea la base
y el usuario cuando su volumen está vacío; cambiar después `DB_PASSWORD` en
`.env.prod` no cambia nada en la base y la aplicación deja de entrar. Para cambiarla:

```bash
docker compose -f docker-compose.prod.yml exec db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot'
```

```sql
ALTER USER 'asistencia'@'%' IDENTIFIED BY 'la-nueva-contraseña';
```

y luego actualiza `DB_PASSWORD` en `.env.prod` y vuelve a levantar la pila.

### Actualizar la aplicación

```bash
scripts/respaldo.sh                  # sin copia no se actualiza
git fetch --tags
git checkout vX.Y.Z
docker compose -f docker-compose.prod.yml up -d --build
```

Para volver atrás, repite los dos últimos pasos con la etiqueta anterior. Los
datos no se tocan mientras no haya migraciones nuevas.

### Respaldo y restauración (RNF-08)

`scripts/respaldo.sh` (Linux) y `scripts/respaldo.ps1` (Windows) generan en
`respaldos/` dos archivos por corrida y conservan los 14 más recientes de cada tipo:

- `db_AAAA-MM-DD_HHMM.sql.gz`: volcado de la base con `mysqldump`.
- `media_AAAA-MM-DD_HHMM.tar.gz`: la carpeta `media/` (los justificantes).

Si el volcado falla o queda incompleto, el script termina con error y no borra
ninguna copia anterior. `respaldos/` no se versiona: las copias traen nombres y
matrículas de alumnos.

**Las copias quedan en el mismo equipo que la base: no protegen contra la pérdida
del equipo.** Copia la carpeta `respaldos/` a otro lugar (otro disco, la nube de la
institución) con la frecuencia que puedas.

Para programarlo todos los días a las 3:00:

- **Linux (cron).** `crontab -e` y agrega, con la ruta real del proyecto:

  ```
  0 3 * * * /ruta/al/proyecto/scripts/respaldo.sh >> /ruta/al/proyecto/respaldos/respaldo.log 2>&1
  ```

- **Windows (Programador de tareas).** En PowerShell, con la ruta real del proyecto:

  ```powershell
  schtasks /Create /TN "Respaldo control de asistencia" /SC DAILY /ST 03:00 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\ruta\al\proyecto\scripts\respaldo.ps1"
  ```

  El equipo debe estar encendido y con Docker Desktop abierto a esa hora. Para
  hacer una copia en el momento: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\respaldo.ps1`.

**Probar la restauración.** Una copia que no se ha restaurado no es una copia. Justo
después de un respaldo (en Windows, desde Git Bash):

```bash
scripts/probar_restauracion.sh       # usa la copia más reciente de respaldos/
```

Restaura el volcado, como `root`, en una base temporal (`restauracion_prueba`);
compara las filas de cada tabla con la base real; comprueba que el disparador de
la bitácora y su dueño existen y que un `UPDATE` de `estado` funciona (dentro de
una transacción que se deshace); revisa la copia de `media/`; y elimina solo esa
base temporal. Se hace como `root` porque el usuario de la aplicación no puede
crear otra base.

**Restaurar de verdad** sobrescribe la base actual: haz antes una copia de lo que
hay. Con la pila levantada:

```bash
gzip -dc respaldos/db_AAAA-MM-DD_HHMM.sql.gz | docker compose -f docker-compose.prod.yml exec -T db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot "$DB_NAME"'
docker compose -f docker-compose.prod.yml exec -T web sh -c 'tar -xzf - -C /app' < respaldos/media_AAAA-MM-DD_HHMM.tar.gz
```

**En un servidor nuevo, levanta primero la pila con el mismo `.env.prod` y restaura
después.** El disparador de la bitácora se guarda con el usuario de la aplicación
como dueño (`DEFINER`). Si ese usuario no existe donde se restaura, todo cambio
sobre la asistencia falla con `ERROR 1449 (The user specified as a definer does not
exist)`: no se podría corregir un registro ni adjuntar un justificante. Levantar la
pila con el mismo `.env.prod` crea ese usuario antes de restaurar.

### HTTPS y `check --deploy`

Con un dominio real en `DOMINIO`, Caddy obtiene el certificado, sirve HTTPS y
redirige el puerto 80. Pon entonces `DJANGO_HTTPS=1`, el dominio en
`DJANGO_ALLOWED_HOSTS` y vuelve a levantar la pila.

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py check --deploy
```

Con `DJANGO_HTTPS=1` quedan tres avisos, los tres a propósito:

| Aviso | Por qué se queda |
|---|---|
| `security.W008` (`SECURE_SSL_REDIRECT`) | La redirección de HTTP a HTTPS la hace Caddy. Si también la hiciera Django, la comprobación de salud del contenedor, que le habla por HTTP, recibiría una redirección |
| `security.W005` (`SECURE_HSTS_INCLUDE_SUBDOMAINS`) | Obligaría a HTTPS a todos los subdominios del dominio, que no son de este sistema |
| `security.W021` (`SECURE_HSTS_PRELOAD`) | La precarga de HSTS en los navegadores tarda meses en revertirse; no corresponde a un sistema recién desplegado, con HSTS de una hora |

En la demostración local (`DJANGO_HTTPS=0`) salen cuatro: `W004`, `W008`, `W012` y
`W016`. Son los de un sitio sin HTTPS; por eso la demostración solo se usa en el
propio equipo.

### Problemas frecuentes

- **`db` no arranca y sus registros dicen «revisa MYSQL_ROOT_PASSWORD…».** Falta
  una variable de la base en `.env.prod` o sigue en `CAMBIA-ESTO`.
- **`web` se reinicia con `ImproperlyConfigured`.** Falta `DJANGO_SECRET_KEY` o es
  la del ejemplo.
- **`Access denied` al conectar a la base.** `DB_PASSWORD` de `.env.prod` no es la
  que se usó la primera vez (ver «Las contraseñas de la base solo se aplican la
  primera vez»).
- **Error 1419 al crear el disparador.** No aparece con esta pila: `db` arranca
  con `--log-bin-trust-function-creators=1`. Con un MySQL propio, ver
  [Notas sobre MySQL](#notas-sobre-mysql).
- **Error 400 (Bad Request) en todas las pantallas.** El nombre con el que entras
  no está en `DJANGO_ALLOWED_HOSTS`.

## Supuestos sin confirmar

Se usan estos valores por defecto hasta que se confirmen:

- **Administrador:** gestiona usuarios y periodos; no ve los grupos de los docentes.
- **Hosting:** decidido el 16/11/2026: demostración local con Docker en el equipo del proyecto
  (ver [Despliegue](#despliegue)). La misma pila sirve en un servidor con dominio, pero ese caso no se ha ejecutado.
- **Trabajo:** una sola persona. Los cambios se integran por pull request, con ramas cortas y versionado semántico (ver [docs/gestion_configuracion.md](docs/gestion_configuracion.md)).

## Estructura

```
config/        configuración de Django (settings, urls, wsgi)
asistencia/    única app del proyecto
  models.py        ocho modelos y sus restricciones
  migrations/      0001 (esquema), 0002 (disparador de la bitácora), 0003 (periodos) y 0004 (aprobación de cuentas)
  backends.py      inicio de sesión con correo (una cuenta sin aprobar no entra)
  permissions.py   mixins: cada docente ve solo sus grupos (404 ante uno ajeno); el panel es solo del administrador
  admin.py         usuarios con rol (RF-16) y periodos (RF-17)
  forms.py         formularios (acceso, registro, grupos, sesiones...)
  services/        lógica de negocio: importar CSV, inscripciones, sesiones,
                   pase de lista (con las reglas de las casillas) y correcciones,
                   justificantes, sesiones pendientes, periodos, usuarios y roles,
                   registro y aprobación de cuentas, resúmenes de inicio, reportes y
                   exportación a PDF y Excel
  views/           vistas por módulo (autenticación y registro, panel del administrador, grupos...)
  templates/       plantillas con Bootstrap 5
  templatetags/    filtro `iniciales` para los avatares
  static/          estilo.css (aplicación), admin.css (tema del admin, con la misma paleta)
                   y pase_de_lista.js (reglas de las casillas del pase de lista)
  management/      comando seed_demo
  tests/           pruebas
docs/          manuales de usuario y de administrador (con sus capturas en img/), informe de pruebas (fase H),
               seguimiento semanal,
               plan de despliegue y gestión de la configuración
docker/        arranque del contenedor (entrypoint.sh), comprobación de salud (healthcheck.py) y proxy (Caddyfile)
scripts/       demo.ps1 (demostración local), respaldo.sh y respaldo.ps1 (RNF-08) y probar_restauracion.sh
Dockerfile                imagen de la aplicación (gunicorn y WhiteNoise)
docker-compose.prod.yml   pila de producción: db, web y proxy (docker-compose.yml es el MySQL de desarrollo)
.env.prod.example         plantilla de la configuración de producción
CHANGELOG.md   historial de versiones (formato Keep a Changelog)
```
