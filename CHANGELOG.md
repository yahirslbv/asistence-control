# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato se basa en [Keep a Changelog 1.1.0](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico 2.0.0](https://semver.org/lang/es/); la política está en [docs/gestion_configuracion.md](docs/gestion_configuracion.md).

## [Unreleased]

## [1.0.0] - 2026-11-17

Primera versión en producción. Agrega a la 0.9.0 los manuales de usuario y de administrador (fase I) y la parte técnica de la fase J: despliegue con Docker, configuración de producción y respaldo diario con restauración probada (RNF-08). Sin migraciones nuevas: el esquema es el de la 0.9.0. Se entrega como demostración local con Docker (`http://localhost`); la misma pila sirve en un servidor con dominio y HTTPS, pero ese caso no se ha ejecutado.

### Added

- Manual del administrador, con capturas: el Panel, aprobar y rechazar cuentas, alta, baja y cambio de contraseña de usuarios, y periodos escolares (`docs/manual_administrador.md`, fase I).
- Manual de usuario del docente, con capturas de cada pantalla: cuenta y acceso, grupos, alumnos y archivo CSV, sesiones, pase de lista con sus casillas, correcciones y justificantes, reportes y solo lectura (`docs/manual_usuario.md`, fase I).
- Despliegue con Docker (fase J): imagen de la aplicación (`Dockerfile`, con gunicorn y un usuario sin privilegios) y pila de producción (`docker-compose.prod.yml`: MySQL 8 sin puertos publicados y con usuario propio de la aplicación, la aplicación, y Caddy como único servicio que publica puertos), configurada con `.env.prod` (`.env.prod.example`).
- Archivos estáticos servidos por WhiteNoise, con huella en el nombre cuando `DJANGO_STATIC_MANIFEST=1` (lo fija la imagen).
- Variables de producción `DJANGO_HTTPS` (cookies seguras, cabecera del proxy y HSTS de una hora) y `DJANGO_CSRF_TRUSTED_ORIGINS`.
- Respaldo diario de la base de datos y de `media/`, con retención de 14 copias (`scripts/respaldo.sh` para cron y `scripts/respaldo.ps1` para Windows), y prueba de restauración (`scripts/probar_restauracion.sh`) (RNF-08).
- `scripts/demo.ps1`: levanta la demostración local con un comando.
- Sección «Despliegue» en el README: demostración local, servidor, variables, actualización, respaldo y restauración.
- `.gitattributes`: los archivos que corren en Linux conservan saltos de línea LF al clonar en Windows.

### Changed

- `requirements.txt` fija la versión exacta de cada dependencia, directa e indirecta, y agrega `whitenoise` y `gunicorn` (este último solo fuera de Windows) para el despliegue (solicitud de cambio [CR-002](docs/cambios/CR-002_versiones_exactas.md)).

### Fixed

- El texto del selector de rol del admin de Django ya no se recorta: el alto fijo que Django le da a los selectores chocaba con el relleno del tema.

### Security

- Con `DJANGO_DEBUG=0` la aplicación no arranca si `DJANGO_SECRET_KEY` falta, está vacía o es la de un archivo de ejemplo.
- `seed_demo` se niega a crear cuentas con la contraseña de demostración del código cuando `DEBUG` está apagado: exige una propia en `SEED_PASSWORD`.
- En la pila de producción, `/media/` responde 404 desde el proxy, la base no publica el puerto 3306 y la aplicación entra a MySQL con un usuario sin privilegios fuera de su base.

## [0.9.0] - 2026-11-11

Primera versión etiquetada. Fija como línea base lo construido del 13/10 al 11/11/2026: las fases D, E, F, G y H, los requisitos RF-16 a RF-20 y la gestión de la configuración. Todavía no es una versión de producción: faltan los manuales (fase I) y el despliegue (fase J).

### Added

- Autenticación: inicio de sesión con correo institucional y opciones según el rol (RF-01, RF-02), alta de usuarios con rol desde el admin de Django (RF-16), registro de docentes con dominio permitido y aprobación del administrador (RF-19) y panel del administrador (RF-20).
- Grupos y alumnos: alta, edición y baja de grupos (RF-03), carga de la lista desde un CSV (RF-04) e inscripción y baja individual (RF-05).
- Sesiones: generación a partir del horario y el periodo (RF-06), edición y cancelación (RF-07) y calendario por mes.
- Periodos escolares con un solo periodo activo; uno inactivo deja sus grupos en solo lectura (RF-17).
- Asistencia: pase de lista con los estados presente, retardo, ausente y justificado (RF-08), un solo registro por alumno y sesión (RF-09), aviso de sesiones sin registrar o incompletas (RF-10), corrección con bitácora escrita por un disparador de MySQL (RF-11, RNF-06) y justificantes en PDF, JPG o PNG (RF-12).
- Pase de lista con casillas y reglas de bloqueo (RF-18) y fila compacta para el teléfono (RNF-10).
- Reportes: porcentaje de asistencia por alumno, grupo y periodo (RF-13), alumnos bajo el mínimo (RF-14) y exportación a PDF y Excel (RF-15).
- Aislamiento por docente: un grupo ajeno responde 404 (RNF-04), con páginas 403 y 404 propias.
- Diseño visual propio «pino y ámbar» y tema del admin de Django (RNF-02).
- Comando `seed_demo` con datos de demostración (solo para desarrollo).
- Pruebas automáticas de cada requisito de prioridad Alta, flujos de extremo a extremo, matriz de acceso y conteo de consultas (RNF-07); informe de pruebas y seguimiento semanal en `docs/`.
- Plan técnico de despliegue con Docker (`docs/DESPLIEGUE.md`), todavía sin ejecutar.
- Gestión de la configuración: inventario de elementos y líneas base, convención de nombres, política de versionado, estrategia de ramas, control de cambios con plantilla de solicitud y auditoría previa a cada etiqueta (`docs/gestion_configuracion.md` y `docs/cambios/`).
- Este `CHANGELOG.md`.
- Página 500 propia, en español y sin depender del menú, las rutas ni los archivos estáticos, con 5 pruebas con `DEBUG` desactivado (H-02, solicitud de cambio [CR-001](docs/cambios/CR-001_pagina_500.md)).

### Changed

- Los mensajes de commit siguen Conventional Commits desde esta versión (antes: `RF-09: descripción`); el requisito pasa a ser el ámbito.

### Security

- Contraseñas con el cifrado de Django (RNF-03); justificantes con nombre aleatorio, validados por extensión y firma del archivo, y servidos solo por una vista del docente dueño del grupo.
- `.gitignore` cubre `.env.*`, `media/`, `respaldos/` y `*.sql.gz` para que ningún secreto ni dato de alumnos llegue al repositorio.

[Unreleased]: https://github.com/yahirslbv/asistence-control/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yahirslbv/asistence-control/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/yahirslbv/asistence-control/releases/tag/v0.9.0
