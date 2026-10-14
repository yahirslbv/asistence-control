# Sistema de Control de Asistencia

Aplicación web en Django que sustituye el pase de lista en papel. Proyecto de la
materia Administración de Proyectos de Software (UABC, FCITEC).

Módulos: autenticación y usuarios, grupos, sesiones, asistencia y reportes.
El detalle de requisitos, reglas de negocio y plan por fases está en
[CLAUDE.md](CLAUDE.md), que es la fuente de verdad del proyecto.

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
| `DJANGO_SECRET_KEY` | Clave secreta de Django. Cámbiala en cualquier entorno compartido |
| `DJANGO_DEBUG` | `1` en desarrollo, `0` en producción |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Conexión a MySQL. Con Docker, `DB_PASSWORD` es también la contraseña de `root` del contenedor |
| `ASISTENCIA_MINIMA` | Porcentaje mínimo de asistencia (por defecto 80) |

## Usuarios

`seed_demo` crea tres cuentas, que entran con su **correo**:

| Correo | Rol |
|---|---|
| `admin@asistencia.test` | Administrador |
| `docente1@asistencia.test` | Docente |
| `docente2@asistencia.test` | Docente |

La contraseña de demostración está en `PASSWORD_DEMO`, dentro de
`asistencia/management/commands/seed_demo.py`. Se cambia con la variable de
entorno `SEED_PASSWORD` antes de ejecutar el comando.

`createsuperuser` crea el usuario con rol **docente**. Si lo usas para tener un
administrador, cambia su rol a Administrador desde el admin de Django.

## Pruebas

```powershell
python manage.py test
```

El usuario de MySQL necesita permiso para crear la base `test_control_asistencia`
(`root` en el contenedor ya lo tiene).

## Supuestos sin confirmar

Se usan estos valores por defecto hasta que se confirmen:

- **Asistencia mínima:** 80 %, configurable con `ASISTENCIA_MINIMA`.
- **Administrador:** solo gestiona usuarios; no ve los grupos de los docentes.
- **Hosting:** sin definir. Se resuelve en la actividad J (despliegue).
- **Trabajo:** una sola persona, sin flujo de pull requests.

## Estructura

```
config/        configuración de Django (settings, urls, wsgi)
asistencia/    única app del proyecto
  models.py        siete modelos y sus restricciones
  migrations/      0001 (esquema) y 0002 (disparador de la bitácora)
  backends.py      inicio de sesión con correo
  permissions.py   mixins: cada docente ve solo sus grupos (404 ante uno ajeno)
  forms.py         formularios
  services/        lógica de negocio: importar CSV, inscripciones, sesiones
  views/           vistas por módulo
  templates/       plantillas con Bootstrap 5
  management/      comando seed_demo
  tests/           pruebas
```
