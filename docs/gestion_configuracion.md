# Gestión de la configuración del software

Sistema de Control de Asistencia · UABC, FCITEC · Administración de Proyectos de Software.

Este documento define cómo se identifica, versiona, cambia y libera cada componente del sistema. Aplica las técnicas de configuración de IEEE 828 y de la guía SWEBOK (identificación de elementos, líneas base, control de versiones, control de cambios y auditoría). [CLAUDE.md](../CLAUDE.md) sigue siendo la fuente de verdad del proyecto; este archivo solo describe cómo se controlan sus cambios.

## 1. Alcance y roles

- **Un solo repositorio** guarda el código, la base de datos (migraciones), los scripts y la documentación. Los manuales de usuario y de administrador (fase I) entrarán al mismo repositorio cuando existan.
- **Trabajo individual** (supuesto del README: una sola persona). Los roles son los del cronograma (líder de proyecto, analista, desarrollador de base de datos, backend, frontend, pruebas y documentador) y una persona puede cubrir varios.
- **Comité de control de cambios (CCB).** Lo ejerce el líder de proyecto. SWEBOK admite que, en proyectos pequeños, la autoridad para aceptar o rechazar cambios la tenga una sola persona. Para que la decisión no sea solo mental, cada solicitud de cambio se escribe en `docs/cambios/` con su evaluación y su resolución (sección 7).

## 2. Líneas base

Una línea base es una versión formalmente aprobada y fijada de un conjunto de elementos; solo cambia por el procedimiento de control de cambios. Se usan los tipos de línea base que describe SWEBOK (funcional, asignada, de desarrollo y de producto).

| ID | Línea base | Tipo SWEBOK | Qué contiene | Cuándo se establece |
|---|---|---|---|---|
| LB-F | Funcional | Funcional | Requisitos funcionales y no funcionales (`CLAUDE.md`, secciones 6 y 7) y las pantallas del prototipo | Con la aprobación del documento de requisitos (actividad A) |
| LB-D | Diseño | Asignada | Modelo de datos, restricciones de integridad y migraciones (`CLAUDE.md` sección 8 y Apéndices A y B) | Con la aprobación del diseño de la base de datos (actividad B) |
| LB-C | Construcción | De desarrollo | Código, pruebas y configuración; evoluciona con cada cambio integrado a `main` | Se fija en cada etiqueta |
| LB-L | Liberación | De producto | El conjunto etiquetado (`vMAJOR.MINOR.PATCH`) con su documentación de liberación | Al etiquetar la versión, después de la auditoría de la sección 8 |

LB-F y LB-D se aprobaron antes de que existiera el repositorio (el primer commit es del 13/10/2026); desde entonces su texto vive en `CLAUDE.md`, y cualquier cambio a ellas pasa por una solicitud de cambio.

## 3. Elementos de configuración (ECS)

Un solo número de versión identifica al producto completo (repositorio único): la **versión inicial** de un elemento es la etiqueta en la que entró a su línea base. Los responsables son roles del cronograma.

| ID | Elemento de configuración | Ubicación | Tipo | Responsable | Línea base | Versión inicial |
|---|---|---|---|---|---|---|
| ECS-01 | Especificación del proyecto: requisitos, reglas de negocio, estado y decisiones | `CLAUDE.md` | Documento | Líder de proyecto | LB-F | 0.9.0 |
| ECS-02 | Modelo de datos | `asistencia/models.py` | Código (modelo) | Desarrollador de base de datos | LB-D | 0.9.0 |
| ECS-03 | Migraciones y disparador de la bitácora | `asistencia/migrations/` (0001 a 0004) | Script de base de datos | Desarrollador de base de datos | LB-D | 0.9.0 |
| ECS-04 | Lógica de negocio | `asistencia/services/` | Código | Backend | LB-C | 0.9.0 |
| ECS-05 | Vistas, formularios, rutas, permisos y administración | `asistencia/views/`, `forms.py`, `urls.py`, `permissions.py`, `backends.py`, `admin.py`, `config/urls.py` | Código | Backend | LB-C | 0.9.0 |
| ECS-06 | Plantillas y recursos estáticos | `asistencia/templates/`, `asistencia/static/`, `asistencia/templatetags/` | Código (interfaz) | Frontend | LB-C | 0.9.0 |
| ECS-07 | Pruebas automatizadas | `asistencia/tests/` | Código (pruebas) | Pruebas | LB-C | 0.9.0 |
| ECS-08 | Configuración de la aplicación y dependencias | `config/settings.py`, `.env.example`, `requirements.txt` | Configuración | Backend | LB-C | 0.9.0 |
| ECS-09 | Reglas de exclusión del repositorio (protegen secretos y datos) | `.gitignore` | Configuración | Líder de proyecto | LB-C | 0.9.0 |
| ECS-10 | MySQL 8 de desarrollo en Docker | `docker-compose.yml` | Script de infraestructura | Backend | LB-C | 0.9.0 |
| ECS-11 | Datos de demostración | `asistencia/management/commands/seed_demo.py` | Script | Backend | LB-C | 0.9.0 |
| ECS-12 | Informe de pruebas y seguimiento semanal | `docs/informe_pruebas.md`, `docs/seguimiento_semanal.md` | Documento | Pruebas | LB-C | 0.9.0 |
| ECS-13 | Plan técnico de despliegue (fase J) | `docs/DESPLIEGUE.md` | Documento | Líder de proyecto | LB-L | 0.9.0 |
| ECS-14 | Instalación y uso | `README.md` | Documento | Documentador | LB-L | 0.9.0 |
| ECS-15 | Historial de versiones | `CHANGELOG.md` | Documento | Documentador | LB-L | 0.9.0 |
| ECS-16 | Gestión de la configuración, solicitudes de cambio y plan de liberación | `docs/gestion_configuracion.md`, `docs/cambios/`, `docs/plan_liberacion.md` | Documento | Líder de proyecto | LB-L | 0.9.0 |
| ECS-17 | Manual de usuario y manual de administrador | pendientes (fase I) | Documento | Documentador | LB-L | por definir (antes de 1.0.0) |

**Todavía no existen** y entrarán a LB-L cuando se creen: el `Dockerfile`, `docker-compose.prod.yml`, `.env.prod.example` y `scripts/respaldo.sh` del plan de despliegue, y los manuales (ECS-17). La documentación previa (EDT, modelo entidad-relación, prototipo y cronograma) está fuera del repositorio.
