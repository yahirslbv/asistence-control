# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato se basa en [Keep a Changelog 1.1.0](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico 2.0.0](https://semver.org/lang/es/); la política está en [docs/gestion_configuracion.md](docs/gestion_configuracion.md).

## [Unreleased]

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

### Changed

- Los mensajes de commit siguen Conventional Commits desde esta versión (antes: `RF-09: descripción`); el requisito pasa a ser el ámbito.

### Security

- Contraseñas con el cifrado de Django (RNF-03); justificantes con nombre aleatorio, validados por extensión y firma del archivo, y servidos solo por una vista del docente dueño del grupo.
- `.gitignore` cubre `.env.*`, `media/`, `respaldos/` y `*.sql.gz` para que ningún secreto ni dato de alumnos llegue al repositorio.

[Unreleased]: https://github.com/yahirslbv/asistence-control/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/yahirslbv/asistence-control/releases/tag/v0.9.0
