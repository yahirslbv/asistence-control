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

## 4. Convención de nombres

| Qué | Formato | Ejemplo |
|---|---|---|
| Ramas | `<tipo>/<id>-<tema>` en minúsculas y con guiones. Tipos: `feature` (requisito o documentación), `cambio` (solicitud de cambio aprobada), `fix` (corrección) y `release` (preparación de una liberación) | `feature/rnf-09-gestion-configuracion`, `cambio/cr-001-pagina-500`, `release/v0.9.0` |
| Commits | [Conventional Commits 1.0.0](https://www.conventionalcommits.org/es/v1.0.0/): `tipo(ámbito): descripción`. Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `style`, `build`, `ci` y `chore`. El ámbito es el requisito, hallazgo o solicitud de cambio en minúsculas, o `release`. La descripción va en español, en infinitivo, sin punto final y con el encabezado de 72 caracteres o menos. Un cambio incompatible lleva `!` antes de los dos puntos y una nota `BREAKING CHANGE:` | `feat(h-02): página 500 propia e independiente del contexto` |
| Etiquetas | `vMAJOR.MINOR.PATCH`, o `vMAJOR.MINOR.PATCH-rc.N` para una candidata. Siempre anotadas (`git tag -a`) | `v0.9.0`, `v1.0.0-rc.1` |
| Solicitudes de cambio | `CR-NNN`, en el archivo `docs/cambios/CR-NNN_tema.md` | `CR-001_pagina_500.md` |
| Documentos | `docs/<tema>.md` en minúsculas, con guiones bajos y sin acentos. Los que ya existían conservan su nombre | `docs/plan_liberacion.md` |
| Código y pruebas | Los de `CLAUDE.md` sección 5: identificadores en español, módulos en `snake_case` y pruebas en `test_<tema>.py` | `test_pagina_500.py` |
| Migraciones | Las numera Django: `000N_descripcion.py` | `0004_usuario_aprobado.py` |

La regla de `CLAUDE.md` sección 5 pide el requisito al inicio del commit (`RF-09: impedir registro duplicado`). Desde la versión 0.9.0 el requisito va como ámbito del tipo, para cumplir las dos cosas: `fix(rf-09): impedir registro duplicado`. Los commits anteriores conservan el formato antiguo y no se reescriben.

## 5. Política de versionado semántico

El sistema usa [Versionado Semántico 2.0.0](https://semver.org/lang/es/): `MAJOR.MINOR.PATCH`. La etiqueta anotada de Git es la fuente de verdad de la versión y `CHANGELOG.md` describe qué trae cada una.

**API pública del sistema.** El versionado semántico exige declararla. Este sistema no ofrece una API a otros programas, así que se declara como tal lo que quien lo opera o lo integra espera que no cambie sin aviso:

1. El esquema de la base de datos y sus migraciones.
2. Las URL de la aplicación.
3. El formato de las exportaciones a PDF y Excel.
4. Las variables de entorno (`.env`) y los comandos de administración (`seed_demo`, `migrate`).

| Incremento | Cuándo | Commit asociado | Ejemplo |
|---|---|---|---|
| MAJOR | Cambio incompatible en alguno de los cuatro puntos, que obliga a quien opera el sistema a intervenir: una migración que borra datos, renombrar una variable de entorno, cambiar una URL | `!` o `BREAKING CHANGE:` | Pasar de MySQL a otra base de datos |
| MINOR | Funcionalidad nueva compatible: un requisito nuevo, una pantalla nueva, una migración que solo agrega | `feat` | RF-17, periodos escolares |
| PATCH | Corrección que no cambia lo anterior | `fix` | Un cálculo de porcentaje mal redondeado |

Reglas:

- **Mientras el sistema no esté en producción es `0.y.z`** (desarrollo inicial: cualquier cosa puede cambiar). Se sube MINOR por cada hito funcional y PATCH por cada corrección. La línea base actual es `0.9.0`: funcionalmente completa, pero sin despliegue ni manuales.
- **`1.0.0` se asigna cuando el sistema esté desplegado y aceptado** (acta de aceptación de la fase J). El FAQ de SemVer indica que un software que ya se usa en producción debería ser 1.0.0.
- **Candidatas.** Antes de `1.0.0` puede haber `1.0.0-rc.1`, `1.0.0-rc.2`... Una versión con sufijo de pre-liberación tiene menor precedencia que la normal y avisa que es inestable.
- **Una versión etiquetada no se modifica.** Cualquier corrección se libera como una versión nueva (SemVer, punto 3). Una corrección urgente sale de una rama `fix/...` creada desde la etiqueta que está en producción y se libera como PATCH.
- **Relación con los commits:** `feat` sube MINOR, `fix` sube PATCH y un cambio incompatible sube MAJOR. Los demás tipos no cambian el número por sí solos.

## 6. Estrategia de ramas

Se usa **desarrollo basado en tronco con ramas cortas y pull request** (a veces llamado GitHub Flow):

- `main` es la única rama permanente. Siempre está en un estado que se puede desplegar.
- Cada cambio se hace en una rama corta (de unas horas a pocos días) creada desde `main`, con el nombre de la sección 4.
- Una rama entra a `main` solo por **pull request**, con la revisión de la lista de la sección 7 y la suite de pruebas en verde. La fusión se hace con commit de fusión (`--no-ff`), para que cada pull request quede visible en el historial.
- Una liberación se prepara en una rama `release/vX.Y.Z` que solo ajusta el `CHANGELOG`, la documentación de la liberación y el estado en `CLAUDE.md`. La etiqueta se pone sobre `main`, **después** de fusionarla y de pasar la auditoría de la sección 8.
- Una corrección urgente de producción sale de `fix/<tema>` creada desde la etiqueta en producción, y se libera como PATCH sin llevarse nada que esté a medias.

**Por qué se ajusta a este proyecto.** El proyecto lo desarrolla una persona, tiene un solo entorno de producción, una sola versión en producción a la vez y una fecha límite (27/11/2026) a 16 días. GitFlow (con una rama `develop` permanente, ramas de liberación y de corrección de larga vida) existe para coordinar equipos y varias versiones en paralelo; aquí agregaría sincronizaciones entre ramas sin dar ningún beneficio. Con `main` siempre estable, además, no puede ocurrir que la rama de desarrollo acumule funciones sin probar justo antes de liberar: lo que no pasó la revisión y las pruebas no está en `main`. Si algún día hubiera varias versiones soportadas a la vez, se revisaría la decisión.

## 7. Control de cambios

Todo cambio a un elemento que ya pertenece a una línea base (ECS-01 a ECS-03 siempre; los demás cuando cambian el comportamiento del sistema) pasa por una **solicitud de cambio**:

1. **Solicitud.** Se redacta con `docs/cambios/CR-000_plantilla.md` como `docs/cambios/CR-NNN_tema.md`: quién la pide, qué cambia, por qué y qué elementos toca.
2. **Evaluación de impacto.** Alcance, base de datos, pruebas, documentación, riesgo y esfuerzo, y las alternativas que se descartan.
3. **Decisión del CCB.** Aceptar, modificar, rechazar o diferir, con la fecha y la razón. Se anota en el registro de decisiones de esta sección.
4. **Implementación** en una rama `cambio/cr-nnn-tema`, con commits cuyo ámbito es `cr-nnn` (o el requisito afectado).
5. **Revisión y pruebas.** Pull request con la lista de revisión y la suite completa en verde.
6. **Cierre.** Fusión a `main`, línea nueva en el `CHANGELOG` y actualización de los documentos que cita la solicitud.

**Lista de revisión de un pull request:** (a) el título y los commits siguen la convención de la sección 4; (b) no hay secretos ni archivos de `.gitignore` en el cambio; (c) cada cambio de código tiene su prueba y la suite pasa; (d) no se tocó `models.py` ni una migración sin una solicitud de cambio aprobada; (e) el `CHANGELOG` y los documentos afectados están actualizados; (f) el cambio hace solo lo que dice la solicitud.

**Registro de decisiones del comité**

| Solicitud | Descripción | Fecha | Decisión | Rama | Versión |
|---|---|---|---|---|---|
| (aún no hay solicitudes registradas) | | | | | |

## 8. Auditoría de configuración

Antes de cada etiqueta se hace una auditoría ligera, en las dos formas que describe SWEBOK. Su resultado se anota en el plan de liberación.

- **Funcional** (el producto cumple su especificación): la suite completa pasa en una base MySQL 8 limpia; cada requisito de prioridad Alta tiene prueba; los hallazgos abiertos están revisados y los que quedan, anotados.
- **Física** (lo que se entrega es lo que se documentó): `git status` sin cambios; los archivos versionados (`git ls-files`) coinciden con la estructura de `CLAUDE.md` sección 4; ningún `.env*`, `media/`, `respaldos/` ni `*.sql.gz` versionado (`git check-ignore -v`); el número de la etiqueta coincide con el del `CHANGELOG`; y la etiqueta apunta al commit de `main` que se auditó (`git rev-parse vX.Y.Z^{}`).
