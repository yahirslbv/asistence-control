# CLAUDE.md — Sistema de Control de Asistencia

Léelo completo antes de escribir código. Este archivo es la fuente de verdad del proyecto. Si algo del código lo contradice, pregunta antes de cambiar cualquiera de los dos.

## 1. Contexto

- Proyecto académico de Victo (UABC, FCITEC) para la materia Administración de Proyectos de Software.
- **Problema:** el pase de lista en papel produce registros duplicados, listas perdidas y correcciones que no dejan rastro.
- **Solución:** aplicación web en Django que sustituye las listas en papel. Módulos: autenticación y usuarios, grupos, sesiones, asistencia y reportes.
- **Usuarios:** docente y administrador.
- **Fecha límite de entrega: viernes 27/11/2026.** El código ya existe: las fases D, E, F y G están terminadas (ver la sección 12). La documentación previa incluye requisitos, EDT, modelo entidad-relación, prototipo de pantallas y cronograma.
- **Tablero Trello:** https://trello.com/b/1CRpoq6E/control-de-asistencia-cronograma (una tarjeta por actividad, A–J).

## 2. Stack

| Capa | Decisión |
|---|---|
| Lenguaje | Python 3.10 o superior |
| Framework | Django 5.1 o superior (5.2 LTS recomendado). Se necesita 5.1+ porque `CheckConstraint` usa el argumento `condition` |
| Base de datos | MySQL 8 con InnoDB. El diseño documentado y el disparador están escritos para MySQL |
| Interfaz | Plantillas de Django + Bootstrap 5 (responsiva) + JavaScript mínimo |
| Excel / PDF | `openpyxl` / `reportlab` (se instalan solo con pip) |
| Pruebas | Ejecutor de pruebas de Django (`python manage.py test`) |
| Configuración | Variables de entorno en `.env` (con `python-dotenv`) |

## 3. Antes de empezar: pregunta a Victo

1. ¿Qué sistema operativo usa y tiene MySQL 8 instalado o Docker? Si `mysqlclient` no se instala en Windows, usar `PyMySQL` con `pymysql.install_as_MySQLdb()`.
2. ¿Ya existe el repositorio en GitHub? ¿Cómo se llama?
3. ¿Trabaja solo o en equipo? El cronograma asigna roles (analista, base de datos, interfaz, backend, frontend, pruebas, documentador, líder), pero no hay nombres.
4. ¿Qué porcentaje mínimo de asistencia se usa? Por defecto 80 (**supuesto, sin confirmar**), configurable en `ASISTENCIA_MINIMA`.
5. ¿El administrador solo gestiona usuarios o también ve todos los grupos? Por defecto: solo gestiona usuarios.
6. ¿Dónde se va a desplegar? El hosting no está definido (actividad J).

Si no responde, usa los valores por defecto y anótalos en el README.

## 4. Estructura del repositorio

```
control_asistencia/
├── manage.py
├── config/                  # settings.py, urls.py, wsgi.py
├── asistencia/              # única app; app label = "asistencia"
│   ├── models.py            # Apéndice A (7 modelos)
│   ├── migrations/
│   │   ├── 0001_initial.py
│   │   ├── 0002_trigger_bitacora.py   # Apéndice B
│   │   ├── 0003_periodo.py            # RF-17
│   │   └── 0004_usuario_aprobado.py   # RF-19
│   ├── backends.py          # EmailBackend (login con correo)
│   ├── permissions.py       # mixins: solo grupos del docente, solo administrador
│   ├── forms.py
│   ├── admin.py             # usuarios (RF-16) y periodos (RF-17) en el admin de Django
│   ├── services/            # lógica fuera de las vistas
│   │   ├── importar_alumnos.py   # CSV (RF-04)
│   │   ├── generar_sesiones.py   # horario + periodo (RF-06)
│   │   ├── periodos.py           # activar, desactivar y congelar periodos (RF-17)
│   │   ├── registro.py           # registro de docentes y aprobación de cuentas (RF-19)
│   │   ├── resumen.py            # resúmenes de inicio: docente y panel del administrador (RF-20)
│   │   └── reportes.py           # porcentajes, PDF, Excel (RF-13/14/15)
│   ├── views/               # auth.py (acceso y registro), panel.py (administrador), grupos.py, sesiones.py, asistencia.py, reportes.py
│   ├── templates/asistencia/
│   ├── templatetags/diseno.py   # filtro `iniciales` para los avatares
│   ├── static/              # asistencia/estilo.css (aplicación), admin.css (tema del admin) y pase_de_lista.js (reglas de las casillas, RF-18)
│   ├── management/commands/seed_demo.py
│   └── tests/
├── docs/
│   ├── informe_pruebas.md      # informe de la fase H
│   ├── seguimiento_semanal.md  # avance contra el cronograma y el tablero de Trello
│   ├── DESPLIEGUE.md           # plan técnico de la fase J (Docker, respaldo, producción)
│   ├── gestion_configuracion.md # elementos de configuración, versionado, ramas y control de cambios (RNF-09)
│   └── cambios/                # solicitudes de cambio (CR-NNN) y su plantilla
├── CHANGELOG.md             # historial de versiones (Keep a Changelog)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md                # instalación (RNF-09)
```

## 5. Reglas de trabajo

- Identificadores en español, como en el modelo documentado (`Alumno`, `Grupo`, `Sesion`, `Asistencia`). La interfaz va en español (`es-mx`).
- El esquema del Apéndice A es el diseño ya entregado en las Actividades 5 y en el documento de avance. **No renombres tablas ni campos, ni cambies restricciones, sin avisar a Victo.**
- `AUTH_USER_MODEL = 'asistencia.Usuario'` debe estar definido **antes del primer `migrate`**. Cambiarlo después obliga a rehacer la base de datos.
- Toda lógica de negocio va en `services/`, no en las vistas ni en las plantillas.
- Cada requisito de prioridad Alta lleva al menos una prueba.
- Commits pequeños y en español. Desde la v0.9.0 siguen Conventional Commits con el requisito como ámbito: `fix(rf-09): impedir registro duplicado`. Ramas, versionado y cambios: `docs/gestion_configuracion.md`.
- Agrega cada dependencia a `requirements.txt` al instalarla.
- Nunca subas `.env`, la base de datos ni `media/`.
- Implementa solo lo que pide un RF o RNF. No agregues funciones extra.
- Al terminar una fase, actualiza la sección 12 (Estado) de este archivo.

## 6. Requisitos funcionales

| ID | Módulo | Prior. | Requisito |
|---|---|---|---|
| RF-01, RF-02 | Autenticación | Alta | Texto literal no recuperado. Corresponden a iniciar sesión con correo institucional y contraseña, y a mostrar las opciones según el rol (pantalla 1). Confirmar con el documento de la Actividad 5 |
| RF-03 | Grupos | Alta | El docente da de alta, edita y da de baja sus grupos |
| RF-04 | Grupos | Alta | Cargar la lista de alumnos de un grupo desde un CSV |
| RF-05 | Grupos | Media | Inscribir o dar de baja alumnos de un grupo de forma individual |
| RF-06 | Sesiones | Alta | Generar las sesiones de un grupo a partir de su horario y periodo |
| RF-07 | Sesiones | Media | Editar o cancelar una sesión programada |
| RF-08 | Asistencia | Alta | Registrar asistencia con los estados presente, retardo, ausente y justificado |
| RF-09 | Asistencia | Alta | Impedir registrar dos veces al mismo alumno en la misma sesión |
| RF-10 | Asistencia | Alta | Advertir cuando una sesión quede sin registrar o incompleta |
| RF-11 | Asistencia | Alta | Corregir un registro; se guarda quién lo modificó, la fecha y el valor anterior |
| RF-12 | Asistencia | Media | Adjuntar un justificante a un registro |
| RF-13 | Reportes | Alta | Calcular el porcentaje de asistencia por alumno, grupo y periodo |
| RF-14 | Reportes | Alta | Señalar a los alumnos por debajo del mínimo |
| RF-15 | Reportes | Media | Exportar reportes a PDF y Excel |
| RF-16 | Autenticación | Media | El administrador da de alta usuarios y les asigna un rol |
| RF-17 | Periodos | Media | El administrador crea, edita, activa y desactiva periodos escolares. Solo uno está activo; un periodo inactivo deja sus grupos en solo lectura. Agregado el 3/11/2026 a petición de Victo, fuera del documento de requisitos original |
| RF-18 | Asistencia | Media | El pase de lista usa casillas (presente, retardo, ausente, justificado) con reglas de bloqueo: presente o retardo bloquean ausente y justificado; ausente bloquea presente y retardo; justificado solo con ausente. Cada registro sigue guardando un solo estado. Agregado el 4/11/2026 por observación de los evaluadores |
| RF-19 | Autenticación | Media | Quien no tiene cuenta se registra desde la pantalla de acceso («Si no tienes cuenta, regístrate aquí»). Condiciones de Victo: correo de un dominio permitido (`uabc.edu.mx`, configurable), cuenta pendiente hasta que un administrador la apruebe, y rol docente siempre. Cambia la decisión de que solo el administrador da de alta usuarios. Agregado el 4/11/2026 por observación de los evaluadores |
| RF-20 | Autenticación | Media | El administrador tiene un panel propio, con el diseño del inicio del docente: cuentas por aprobar (aprobar y rechazar), periodo activo, cifras y accesos a Usuarios y Periodos (que siguen siendo del admin de Django). Agregado el 4/11/2026 por observación de los evaluadores |

## 7. Requisitos no funcionales y cómo cumplirlos

| ID | Requisito | Cómo |
|---|---|---|
| RNF-01 | Pase de lista de 40 alumnos en máximo 3 minutos | Todos los alumnos empiezan en "presente"; solo se marcan las excepciones y se guarda con un único envío |
| RNF-02 | Responsiva: teléfono, tableta y computadora | Bootstrap 5; botones grandes en el pase de lista |
| RNF-03 | Contraseñas cifradas | Lo resuelve `AbstractUser` de Django. No guardar contraseñas de otra forma |
| RNF-04 | Cada usuario ve y modifica solo sus grupos | Mixin que filtra por `docente=request.user`; responder 404 (no 403) ante un grupo ajeno, en toda vista que reciba un `grupo_id` o `sesion_id` |
| RNF-05 | Integridad referencial y unicidad por alumno y sesión | Constraints del Apéndice A |
| RNF-06 | Toda corrección registra autor y fecha | Disparador de la base de datos (sección 9.3) |
| RNF-07 | Consultas en menos de 3 s con grupos de hasta 50 alumnos | Agregaciones con el ORM, `select_related` e índices. En `Meta.indexes` van `asistencia(alumno)`, `inscripcion(alumno)` y `bitacora_cambio(asistencia)`: cada uno es el único índice sobre esa clave foránea (MySQL no deja quitarlo, y sin él crearía uno equivalente sin nombre), así que no duplican nada. `sesion(grupo, fecha)` **no** se declara: es prefijo de `uq_sesion_grupo_fecha_hora` y MySQL ya lo usa. Comprobado con `SHOW INDEX` en MySQL 8.0 |
| RNF-08 | Respaldo diario de la base de datos | Comando que ejecuta `mysqldump`, programado con cron. Se hace en la fase J |
| RNF-09 | Código versionado y documentación de instalación | Git + README con pasos de instalación |
| RNF-10 | Pase de lista compacto: nombre a la izquierda y controles a la derecha, para recorrer grupos grandes sin desplazarse de más. Agregado el 4/11/2026 por observación de los evaluadores | Una fila por alumno con cuatro casillas de al menos 44 px, encabezado de columnas fijo, sin desbordamiento horizontal desde 320 px, contraste de 4.5:1 en texto y 3:1 en el borde de las casillas, y estado que no depende solo del color |

## 8. Modelo de datos

Ocho tablas: las siete del diseño original y `periodo` (RF-17, migración 0003). La separación entre `alumno` e `inscripcion` permite que un alumno esté en varios grupos sin duplicar sus datos. `grupo.periodo` sigue siendo texto: guarda la clave del periodo, sin clave foránea. `usuario` ganó la columna `aprobado` (RF-19, migración 0004): una cuenta sin aprobar no puede iniciar sesión.

```
Usuario 1──N Grupo (docente)            Grupo 1──N Sesion
Grupo   1──N Inscripcion N──1 Alumno    Sesion 1──N Asistencia N──1 Alumno
Asistencia 1──N BitacoraCambio          Usuario 1──N Asistencia (registrado_por)
                                        Usuario 1──N BitacoraCambio (usuario)
```

Reglas de integridad ya definidas:

| Regla | Implementación |
|---|---|
| Un alumno no tiene dos registros en la misma sesión (RF-09) | `UniqueConstraint(sesion, alumno)` |
| Un alumno no se inscribe dos veces al mismo grupo (RF-05) | `UniqueConstraint(grupo, alumno)` |
| No se programa dos veces la misma sesión (RF-06) | `UniqueConstraint(grupo, fecha, hora_inicio)` |
| La clave de grupo es única por periodo | `UniqueConstraint(clave, periodo)` |
| Una sesión no termina antes de empezar | `CheckConstraint hora_fin > hora_inicio` |
| Solo un registro justificado admite justificante (RF-12) | `CheckConstraint` + validación en `clean()` |
| Una entrada de bitácora refleja un cambio real | `CheckConstraint valor_anterior != valor_nuevo` |
| No se borra un alumno o usuario con historial | `on_delete=PROTECT` |
| Al eliminar un grupo se eliminan sus sesiones e inscripciones | `on_delete=CASCADE` |
| Solo un periodo activo a la vez (RF-17) | `UniqueConstraint` sobre la expresión `CASE WHEN activo THEN 1 END` (índice único funcional de MySQL 8; los NULL no chocan) |
| Un periodo termina después de empezar (RF-17) | `CheckConstraint fecha_fin > fecha_inicio` |
| La clave de periodo es única y tiene el formato AAAA-N (RF-17) | `unique=True` y validador de la expresión `^\d{4}-\d$` |

## 9. Reglas de negocio que no debes romper

1. **Duplicados.** La base de datos es la defensa. Captura `IntegrityError` y muestra un mensaje claro; no confíes solo en validar antes de guardar.
2. **Porcentaje.** Cuentan como asistencia `presente`, `retardo` y `justificado`. Solo se consideran sesiones en estado `realizada`. Porcentaje = asistencias / registros de asistencia × 100. Un alumno inscrito tarde no se penaliza porque no tiene registros de sesiones anteriores.
3. **Correcciones y bitácora.** Un disparador (Apéndice B) inserta en `bitacora_cambio` cuando cambia `asistencia.estado`, y toma el autor de `NEW.id_usuario`. Por eso, **todo UPDATE del estado debe asignar `registrado_por = request.user`**. No uses señales de Django para esto. La bitácora es solo de inserción: sin vistas de edición ni borrado, y solo lectura en el admin.
4. **Sesión realizada.** Al guardar el pase de lista, la sesión pasa a `realizada`. Una sesión `cancelada` no admite registros.
5. **Bajas lógicas.** Usuarios y alumnos se desactivan (`is_active=False`), no se borran. Eliminar un grupo borra en cascada sus sesiones, asistencias y bitácora, así que la interfaz debe pedir confirmación explícita.
6. **Aislamiento por docente (RNF-04).** Ver RNF-04. Es la regla de seguridad principal; agrega una prueba que intente entrar a un grupo de otro docente.
7. **Justificante (RF-12).** Solo un registro `justificado` admite justificante, uno por registro. Se aceptan PDF, JPG y PNG de hasta 5 MB (5 MB exactos se aceptan) y se guardan en `media/justificantes/` con nombre aleatorio. Un archivo se acepta solo si su extensión **y** su contenido (firma del archivo) coinciden. Se sirve únicamente a través de la vista, nunca por una URL pública de `media/`. Detalle en «Decisiones tomadas».

## 10. Pantallas (prototipo de baja fidelidad)

1. **Inicio de sesión:** correo institucional y contraseña. Según el rol, se muestran las opciones correspondientes.
2. **Pase de lista (pantalla crítica):** alumnos de la sesión elegida, con el estado marcable con un toque, pensada para usarse en el teléfono dentro del salón. Aquí se cumple el RNF-01.
3. **Gestión de grupos:** lista de los grupos del docente, carga del CSV de alumnos y acceso a las sesiones de cada grupo.
4. **Reportes:** porcentaje por alumno, marca visual de quienes están bajo el mínimo y exportación a PDF y Excel.

Decisiones de implementación que puedes tomar sin preguntar:
- **CSV (RF-04):** columnas `matricula,nombre,correo` (correo opcional), leído con `utf-8-sig`. Crea o reutiliza el alumno por matrícula y crea la inscripción. Informa los errores por fila sin abortar todo el archivo.
- **Generar sesiones (RF-06):** `Grupo` no guarda horario. Usa un formulario con días de la semana, hora de inicio y fin, y fechas de inicio y fin del periodo, y crea las `Sesion` con `bulk_create(ignore_conflicts=True)`.
- **Aviso de sesión sin registrar (RF-10):** una sesión pasada (fecha anterior a hoy, o de hoy con la hora de fin ya transcurrida, en America/Tijuana) es pendiente si está `programada` sin registros, o `realizada` con inscritos actuales, con `fecha_alta` igual o anterior a la fecha de la sesión, sin registro en ella. Las canceladas no cuentan. Se muestran como alerta en la página de grupos y en la del grupo, con una sola consulta por página.
- **Alta de usuarios (RF-16):** se cubre con el admin de Django, sin pantallas propias. Detalle en «Decisiones tomadas».

## 11. Plan por fases (sigue el cronograma y el Trello)

Si el tiempo no alcanza, primero todo lo de prioridad Alta; lo Media (RF-05, RF-07, RF-12, RF-15, RF-16) al final.

**D · Entorno y autenticación — S3, 12–16/10 (en curso, vence el viernes 16/10, ruta crítica)**
1. Repositorio Git, `.gitignore` y README mínimo.
2. Entorno virtual, `requirements.txt`, proyecto `config` y app `asistencia`.
3. `settings.py` con el Apéndice C: MySQL por entorno, `AUTH_USER_MODEL`, idioma, zona horaria y `MEDIA_ROOT`.
4. Copiar el `models.py` del Apéndice A completo, generar `0001_initial` y agregar `0002_trigger_bitacora` (Apéndice B). El esquema completo ya está diseñado; créalo de una vez.
5. `EmailBackend` para entrar con correo, vistas de login y logout, y redirección por rol.
6. Plantilla base con Bootstrap 5 y navegación según el rol.
7. Comando `seed_demo`: 1 administrador, 2 docentes, 2 grupos y unos 40 alumnos.
8. Pruebas: login correcto e incorrecto, redirección por rol, el duplicado en `Asistencia` lanza `IntegrityError`, y cambiar el estado crea una fila en `BitacoraCambio`.

Hecho cuando: repositorio configurado e inicio de sesión funcionando.

**E · Grupos y sesiones — S4 y S5, 19–30/10 (ruta crítica)**
RF-03, RF-04, RF-05, RF-06 y RF-07, el mixin de RNF-04, y la consulta del calendario de sesiones. Hecho cuando: alta de grupos, carga de listas y programación de sesiones funcionando.

**F · Asistencia — S6 y S7, 2–13/11 (ruta crítica, la de mayor riesgo)**
RF-08 a RF-12, pantalla de pase de lista y modo de corrección con bitácora visible. Hecho cuando: pase de lista funcionando con validaciones y bitácora de correcciones.

**G · Reportes — S6, 2–6/11 (holgura hasta la S7)**
RF-13, RF-14 y RF-15, con pruebas del cálculo del porcentaje. Hecho cuando: reportes por grupo y por alumno exportables.

**I · Manuales y documentación — S6, 2–6/11 (holgura hasta la S8)**
Manual de usuario, manual de administrador y README de instalación (RNF-09).

**H · Integración y pruebas — S8, 16–20/11 (ruta crítica)**
Flujos completos de extremo a extremo, medición del RNF-07 con 50 alumnos, revisión responsiva, corrección de defectos e informe de pruebas.

**J · Despliegue y entrega — S9, 23–27/11 (ruta crítica)**
Despliegue, respaldo diario (RNF-08), capacitación y acta de aceptación.

## 12. Estado (actualizar al terminar cada fase)

- [x] D · Entorno y autenticación
- [x] E · Grupos y sesiones
- [x] F · Asistencia (RF-08 a RF-12; el justificante, RF-12, se adjunta desde la pantalla de corrección)
- [x] G · Reportes (RF-13, RF-14 y RF-15: reportes por periodo, grupo y alumno, exportables a PDF y Excel)
- [x] RF-16 · Alta de usuarios con rol, desde el admin de Django (cerrado después de la fase G)
- [x] RF-17 · Periodos escolares: el administrador los crea, edita, activa y desactiva; uno inactivo congela sus grupos (3/11/2026)
- [x] RF-18 y RNF-10 · Pase de lista con casillas y fila compacta (4/11/2026)
- [x] RF-19 y RF-20 · Registro de docentes con aprobación y panel del administrador (4/11/2026)
- [ ] I · Manuales
- [x] H · Integración y pruebas (informe en `docs/informe_pruebas.md`; RNF-01 sin cronometrar con personas)
- [ ] J · Despliegue y entrega

### Decisiones tomadas

- **Bajas y reportes (fase G).** Dar de baja a un alumno quita su inscripción y conserva sus registros (`Alumno` no tiene `is_active` en el Apéndice A). Los reportes solo incluyen a los alumnos con inscripción actual: los registros de uno dado de baja no entran al porcentaje del grupo ni salen en la tabla, y su reporte individual responde 404. Siguen visibles en las sesiones donde existen. Si vuelve a inscribirse, vuelve a contar.
- **Porcentajes.** Se calculan con enteros y `Decimal`, nunca con `float`. Se muestran con un decimal **truncado**, no redondeado (1999 de 2500 se ve 79.9 %, no 80.0 %). La marca de «bajo el mínimo» se decide con enteros: `asistencias × 100 < mínimo × registros`, estrictamente menor.
- **Sin registros.** Un alumno sin registros muestra «Sin registros», no 0 %, y no se marca como bajo el mínimo.
- **Porcentaje del grupo.** Es el ponderado: asistencias totales entre registros totales de los inscritos actuales, no el promedio de los porcentajes.
- **Reporte por periodo.** La pantalla «Reportes» muestra, para el periodo elegido (por defecto el más reciente, ordenados como texto AAAA-N), los grupos del docente con su porcentaje y cuántos alumnos están bajo el mínimo. No hay un porcentaje consolidado de un alumno entre varios grupos.
- **Pendientes.** Si el grupo tiene sesiones pendientes (RF-10), el reporte avisa que el porcentaje no las incluye por completo.
- **Exportaciones.** PDF (reportlab, fuente Helvetica) y Excel (openpyxl) salen de la misma tabla que la pantalla. En el Excel ningún texto se convierte en fórmula (los nombres vienen de un CSV). En el PDF un carácter que la fuente no dibuja (por ejemplo «ł» o el japonés) sale como «?» y el PDF lo avisa; el Excel conserva el texto completo.
- **Pase de lista en sesiones futuras.** Solo se permite si la fecha de la sesión es hoy o anterior (fecha de Tijuana). Una sesión futura muestra un mensaje y ningún formulario; un envío contra ella se rechaza sin crear registros.

- **Justificante (RF-12).** Se adjunta desde la pantalla de corrección de la sesión, después de guardar el pase de lista; el enlace aparece solo en los registros `justificado`. Es un archivo por registro: reemplazarlo borra el anterior (cuando la transacción ya se confirmó) y quitarlo pide confirmación, deja el campo en `NULL` y borra el archivo.
- **Validación del justificante.** Se exige extensión PDF, JPG, JPEG o PNG **y** que la firma del contenido (`%PDF-`, `FF D8 FF`, `89 50 4E 47 0D 0A 1A 0A`) corresponda al mismo tipo; un `.html` renombrado a `.pdf` se rechaza. Vacío o de más de 5 MB se rechaza. No se usa Pillow para validar.
- **Almacenamiento y descarga del justificante.** El archivo se guarda como `<uuid4 hex>.<ext>`; el nombre original se descarta. Solo se descarga por la vista (adjunto, `justificante_<matrícula>_<AAAA-MM-DD>.<ext>`, tipo según la firma, `Cache-Control: private, no-store`) y solo para el docente dueño del grupo; no hay URL pública de `media/`. Adjuntar o quitar solo toca el campo `justificante`: no cambia el estado, `registrado_por` ni la bitácora.
- **Justificante y corrección.** Un registro con justificante solo admite el estado `justificado`: para cambiarlo hay que quitar primero el justificante (la pantalla lo avisa), así no se choca con el `CHECK` de la base de datos.
- **Justificante y eliminación de grupo.** La confirmación de eliminar un grupo cuenta los justificantes adjuntos y avisa que los archivos también se borran; se borran una vez confirmada la eliminación.
- **Alta de usuarios (RF-16).** El administrador da de alta a cualquier usuario, con su rol, en el admin de Django, donde ve «Usuarios» y, desde el RF-17, «Periodos» y nada más (desde el RF-20 llega ahí por su panel). El alta pide nombre, apellido, correo, rol, usuario y contraseña. Desde el RF-19 los docentes también pueden registrarse solos, pero solo como docentes y con aprobación: ver más abajo.
- **El rol manda sobre el acceso al admin.** Al guardar un usuario, `is_staff` y los permisos se ajustan al rol (`services/usuarios.py`): administrador con `is_staff` y solo ver/agregar/modificar usuario; docente sin `is_staff` y sin esos permisos. El admin no deja editar `is_staff`, superusuario, grupos ni permisos sueltos, para que nadie se dé más acceso. Quien gestiona usuarios no puede modificar a un superusuario. Un docente no entra al admin y un administrador no ve los grupos (403).
- **Bajas de usuarios.** No hay borrado de usuarios en el admin (ni la acción masiva): se desactivan con «Activo» (regla 9.5). No se puede desactivar ni quitar el rol al último administrador activo, ni desactivarse a uno mismo; la comprobación bloquea las filas de los administradores activos para que dos cambios simultáneos no la burlen.
- **`createsuperuser` y `seed_demo`.** `createsuperuser` sigue creando usuarios con rol docente; para tener un administrador de la aplicación se le cambia el rol desde el admin (README). `seed_demo` prepara el administrador de demo con las mismas reglas.

- **Registro de docentes (RF-19, 4/11/2026).** Cambia la decisión de que solo el administrador da de alta usuarios. Condiciones fijadas por Victo: (1) **dominio permitido**: el correo debe ser de un dominio de `REGISTRO_DOMINIOS` (variable de entorno, separada por comas; por defecto `uabc.edu.mx`); el dominio es exacto (no valen subdominios ni `uabc.edu.mx.otro.com`) y, con la variable vacía, el registro se cierra: la ruta responde 404 y el enlace no aparece; (2) **aprobación del administrador**: la cuenta nace con `aprobado=False` y no puede iniciar sesión, ni en la aplicación ni en el admin, hasta que un administrador la apruebe desde su panel. `Usuario` ganó el campo `aprobado` (migración 0004, autorizada por Victo; valor por defecto verdadero: las cuentas que ya existían y las que da de alta el administrador nacen aprobadas; en el admin se ve y se filtra, pero no se edita); (3) **rol docente**: el formulario no pregunta el rol y no se puede forzar ni el rol, ni `is_staff`, ni la aprobación. El nombre de usuario es el correo y la contraseña pasa por `AUTH_PASSWORD_VALIDATORS`. Una cuenta pendiente que intenta entrar con su contraseña correcta ve «Tu cuenta está pendiente de aprobación»; con cualquier otra contraseña o correo, el mensaje genérico, para no poder sondear qué correos existen. **Rechazar** una cuenta la desactiva (regla 9.5: no se borra) y su correo sigue ocupado; reactivarla con «Activo» en el admin la devuelve a pendiente. Aprobar y rechazar quedan en el registro de acciones del admin con quién lo hizo. **No hay confirmación del correo**: la aplicación no envía mensajes y agregarlo sería una dependencia nueva; el control es la aprobación del administrador. **No hay límite de intentos ni CAPTCHA** (no estaban en el requisito): ver el riesgo en `docs/DESPLIEGUE.md`. Lógica en `services/registro.py`.
- **Panel del administrador (RF-20, 4/11/2026).** Al iniciar sesión, el administrador llega a `/panel/` (antes iba directo al admin de Django), con el diseño del inicio del docente: cuentas por aprobar (Aprobar, y Rechazar con confirmación), cifras (cuentas por aprobar, docentes y administradores activos, periodo activo), el periodo activo con sus fechas y su número de grupos, y accesos a Usuarios, Agregar usuario y Periodos. **Las pantallas de Usuarios y Periodos siguen siendo las del admin de Django** (RF-16 y RF-17 no se rehicieron): el panel las enlaza y la barra superior del administrador trae Panel, Usuarios y Periodos. Un docente recibe 403 y quien no inició sesión va al acceso; el acceso es por el rol administrador (un superusuario con rol docente no entra hasta que se le cambie el rol). El panel no muestra los grupos ni los alumnos de los docentes: solo cuenta los grupos del periodo activo, igual que la lista de Periodos. Aprobar es solo por POST, y si otra persona ya atendió la cuenta el panel avisa en lugar de fallar. `test_matriz_de_acceso.py` tiene una matriz propia para las rutas del administrador y obliga a clasificar cualquier ruta nueva bajo `/panel/`.
- **Paleta vigente (rediseño del 4/11/2026).** Variables de `estilo.css` (el admin las reutiliza, con su propio tema claro y oscuro): pino `#0b2e26` (barra y fondos de marca) y `#14523f` (botones y enlaces), ámbar `#f2b33d` (único acento: relleno, nunca texto sobre blanco), lienzo `#f1f4f1`, superficie `#ffffff`, tinta `#16201c` y `#52605a`; estados presente `#1b6b43`, retardo `#8a5a00`, ausente `#a12f2f` y justificado `#1a6478`. La aplicación es solo clara; el admin tiene claro y oscuro. **Victo confirmó esta paleta como la definitiva el 9/11/2026** (tarjeta RNF-11 del tablero, cerrada). Si algún día cambia, solo hay que editar las variables de `estilo.css`; `test_estilo.py` vuelve a comprobar el contraste.
- **Pruebas de integración (fase H).** `test_flujos.py` encadena las pantallas por sus URL y formularios reales, con reloj fijo y cifras calculadas a mano. `test_matriz_de_acceso.py` toma las rutas de `urls.py`: una ruta nueva que no se clasifique rompe la primera prueba, a propósito, y obliga a decidir quién puede entrar. `test_rendimiento.py` protege contra un N+1 en las pantallas que no tenían prueba de conteo.
- **RNF-07 medido.** Con 6 grupos de 50 alumnos y 48 sesiones (14 400 registros) en MySQL, el peor caso fue 570 ms (importar un CSV de 50 alumnos) contra el límite de 3 s; las demás vistas quedaron por debajo de 280 ms en su peor repetición. Método y tabla completos en `docs/informe_pruebas.md`.
- **RNF-01 no se cronometra aquí.** Se mide el costo de interacción, no un tiempo humano. Con las casillas del RF-18, un retardo cuesta 1 toque, una falta 2 (quitar «Presente» y marcar «Ausente») y una falta justificada 3; guardar es un solo envío y su botón siempre está visible. Marcar 5 excepciones (2 ausentes, 2 retardos, 1 justificado) cuesta 9 toques más el envío. Verificarlo requiere probar con docentes.
- **Pase de lista con casillas (RF-18, 4/11/2026).** Cada alumno tiene cuatro casillas, no botones de radio. Reglas: «Presente» o «Retardo» bloquean «Ausente» y «Justificado»; «Ausente» bloquea «Presente» y «Retardo»; «Justificado» solo se puede marcar con «Ausente». El esquema no cambia: cada registro guarda un solo estado. Correspondencia: solo «Presente» → `presente`; «Retardo», con o sin «Presente» → `retardo`; solo «Ausente» → `ausente`; «Ausente» y «Justificado» → `justificado`; ninguna casilla → el alumno queda sin registrar (RF-10). Las casillas bloqueadas se ven rayadas y con borde punteado, no solo apagadas. El navegador aplica el bloqueo (`static/asistencia/pase_de_lista.js`) y el servidor lo vuelve a comprobar (`services/asistencia.py`: `estado_de_casillas` y `estados_desde_casillas`): una combinación que rompa las reglas rechaza todo el envío, sin guardar nada, y nombra a los alumnos afectados. Cada casilla marcada llega como `<casilla>_<id del alumno>`; el campo `estado_<id>` ya no existe. Sin JavaScript el formulario se envía igual, solo que sin el bloqueo en pantalla. Los servicios `registrar_pase_de_lista` y `corregir_pase_de_lista` siguen recibiendo `{alumno_id: estado}`.
- **Fila compacta (RNF-10, 4/11/2026; ajustada el 9/11/2026 a petición de Victo).** Nombre y matrícula a la izquierda, cuatro casillas a la derecha y un encabezado de columnas fijo bajo la barra superior. **El nombre de cada estado aparece una sola vez, en el encabezado** (abreviado en el teléfono: «Pres.», «Ret.», «Aus.», «Just.»; completo desde 640 px); en las filas la casilla solo muestra su marca ✓ y dice su estado al pasar el cursor (`title`). Cada casilla conserva su nombre accesible («Presente de <alumno>») fuera de la vista, para los lectores de pantalla. Las casillas miden 44×44 px en el teléfono y 56×44 px desde 640 px (columnas de 88 px, para que quepa «Justificado» en el encabezado); la lista mide como máximo 56 rem de ancho, para que el nombre no quede lejos de sus casillas. Medido en el navegador con 25 alumnos: sin desbordamiento horizontal a 320, 375, 640, 768 y 1180 px; casillas de al menos 44 px de alto; alto medio de fila de 65 px a 375 px y 57 px a 768 y 1180 px (antes de este rediseño, unos 128 y 148 px); el nombre del alumno dispone de 142 px a 375 px y de 343 px a 768 px (con la palabra dentro de cada casilla eran 223 px). Protegido por `test_casillas.py` y `test_estilo.py`.
- **Diseño visual (RNF-02, rediseño del 4/11/2026).** Bootstrap 5 se conserva (CDN con SRI); el aspecto propio vive en `asistencia/static/asistencia/estilo.css`. Lenguaje «pino y ámbar»: un verde de marca, un único acento ámbar, neutros con tinte verdoso, sombras teñidas, una escala de radios, tipografía del sistema (sin fuentes ni librerías nuevas) e iconos en línea propios (`_iconos.html`, trazo de 1.75). Las pantallas tienen estados vacíos, barras de porcentaje con `<progress>`, animaciones de entrada que respetan `prefers-reduced-motion`, enlace «saltar al contenido» y favicon; las tablas se reacomodan en el teléfono (las sesiones pasan a tarjetas). El inicio del docente muestra un resumen del día (`services/resumen.py`) y los tres accesos (RF-02). Las letras de los avatares y de las fichas de grupo se dibujan con CSS (`data-texto`) para que no entren al texto de las tablas. Los nombres de clase de los que dependen las pruebas (`btn-check`, `table-danger`, `text-bg-*`, `alert-link`) no cambian. El color solo significa algo: presente (verde), retardo (ámbar), ausente (rojo) y justificado (turquesa), y lo marcado lleva además relleno y marca de verificación, no solo color. `test_estilo.py` protege el contraste mínimo de 4.5:1 de la paleta (3:1 para el borde de las casillas), la carga de la hoja y la sección activa del menú. Esto agrega `{% static %}` a `base.html`: ver `docs/DESPLIEGUE.md` (B3), porque en producción toda pantalla depende de servir `/static/`.
- **Periodos (RF-17, 3/11/2026).** Tabla `periodo` (clave AAAA-N, primer y último día, activo); `grupo.periodo` sigue como texto y no se tocó ninguna tabla ni restricción existente. Decisiones de Victo: **solo un periodo activo a la vez** (activar uno desactiva el otro; lo garantiza la base de datos con un índice único, y `services/periodos.py` serializa los cambios) y **desactivar un periodo congela sus grupos**: quedan en solo lectura, con sus reportes y exportaciones. Congelar bloquea editar o eliminar el grupo, cargar CSV, inscribir y dar de baja, generar, editar y cancelar sesiones, guardar o corregir el pase de lista y adjuntar o quitar justificantes (lo decide `permissions.py`: el docente vuelve al grupo con un aviso y no se toca nada). Consultar sigue permitido: detalle, sesiones, listas con los botones deshabilitados, reportes, Excel, PDF y descarga del justificante. Un grupo cuyo periodo no tiene fila en `periodo` no se congela. Los avisos de sesiones pendientes (RF-10) omiten los grupos congelados, porque ya no se pueden atender, pero los reportes siguen avisando que su porcentaje no los incluye. Un grupo nuevo solo se crea en el periodo activo (lista en lugar de texto libre; sin periodo activo el formulario lo avisa y no deja guardar) y al editar se conserva el periodo que ya tiene. La migración 0003 crea una fila por cada periodo que ya usaban los grupos (fechas tomadas de sus sesiones) y deja activo solo el más reciente.
- **Periodos en el admin.** Lista con clave, fechas, estado, número de grupos y un botón **Activar** o **Desactivar** por fila (con confirmación), y **Guardar y activar** en el formulario. No se borran (sin fila, sus grupos dejarían de congelarse) y la clave no se cambia cuando ya tiene grupos. El acceso es por rol (administrador o superusuario), no por permisos sueltos, para que un administrador que ya existía no tenga que volver a guardarse. Cada cambio queda en el registro de acciones del admin. `seed_demo` crea y activa 2026-2 solo si no hay otro activo.
- **Diseño del admin (3/11/2026).** Tema propio en `asistencia/static/asistencia/admin.css` con la paleta de la aplicación (pino y ámbar desde el 4/11/2026, con la barra superior en pino), claro y oscuro (respeta el interruptor del admin), y plantilla `admin/base_site.html` con la marca. Para que esa plantilla gane a la de Django, `asistencia` va antes que `django.contrib.admin` en `INSTALLED_APPS`. Sin barra lateral ni «Ver sitio». `test_estilo.py` comprueba el contraste de las dos paletas y que la oscura automática y la forzada no se desincronicen.
- **Hallazgos de la fase H sin corregir** (ninguno crítico ni mayor, ver el informe): ~~H-01 botones secundarios de unos 31 px~~ corregido con el rediseño (44 px en el teléfono); ~~H-02 no hay página 500 propia~~ corregido el 11/11/2026 con la solicitud de cambio CR-001 (`asistencia/templates/500.html`, probada con `DEBUG=False` en `test_pagina_500.py`); H-03 la importación del CSV hace unas cinco consultas por fila (0.4 s con 50 filas, 3.8 s con las 500 que acepta como máximo; el RNF-07 solo acota grupos de 50).

- **Plan de despliegue (fase J).** `docs/DESPLIEGUE.md` describe lo técnico de la fase J. Se revisó el 15/10/2026 contra el código y con pruebas desechables, y sus correcciones están en el historial de Git de ese archivo. `.gitignore` ya cubre `.env.*` (menos los ejemplos) y `*.sql.gz`: antes `.env.prod` se habría subido a un repositorio público. El plan aún no se ejecuta; la fase J sigue pendiente.
- **Normas de trabajo de Victo.** Planificar antes de actuar; ejecutar e iterar en Git (un commit por paso verificable y `git push` al cerrar un bloque); validar con pruebas (automáticas cuando se puede, o comprobaciones reproducibles cuyo resultado se anota).

### Decisiones abiertas

- **Mínimo de asistencia de 80 %.** Sigue siendo un supuesto sin confirmar (`ASISTENCIA_MINIMA`). Se ve en pantalla y en las exportaciones.
- **Hallazgo H-03.** Decidir si se corrige antes de la entrega (el informe propone cómo) o se deja como mejora. El H-01 y el H-02 ya se corrigieron.
- **Respaldo de `media/` (fase J).** `media/` no se versiona y los justificantes viven ahí. El respaldo diario (RNF-08) debe incluir esa carpeta además de la base de datos.
- **Hosting (actividad J).** Sin definir.

## 13. Comandos

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # y completar los datos de MySQL
python manage.py makemigrations asistencia
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
python manage.py test
```

Si MySQL rechaza el disparador con el error 1419 (privilegio SUPER con registro binario activo), en desarrollo ejecuta `SET GLOBAL log_bin_trust_function_creators = 1;`. Para correr las pruebas, el usuario de MySQL necesita permiso de crear la base `test_*`.

---

## Apéndice A. `asistencia/models.py`

```python
"""Modelos del Sistema de Control de Asistencia.

Requiere Django 5.1 o superior: CheckConstraint usa el argumento `condition`.
En versiones anteriores el argumento se llama `check=`.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Usuario(AbstractUser):
    """Docentes y administradores. Extiende AbstractUser para no reimplementar
    el hash de contrasena, el inicio de sesion ni el sistema de permisos."""

    class Rol(models.TextChoices):
        DOCENTE = 'docente', 'Docente'
        ADMINISTRADOR = 'administrador', 'Administrador'

    email = models.EmailField('correo institucional', unique=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.DOCENTE)

    class Meta:
        db_table = 'usuario'
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def __str__(self):
        return self.get_full_name() or self.username


class Alumno(models.Model):
    """Padron de alumnos, independiente del grupo en que esten inscritos."""

    id_alumno = models.AutoField(primary_key=True)
    matricula = models.CharField(max_length=15, unique=True)
    nombre = models.CharField(max_length=120)
    correo = models.EmailField(max_length=120, blank=True, null=True)

    class Meta:
        db_table = 'alumno'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.matricula} - {self.nombre}'


class Grupo(models.Model):
    """Grupo que imparte un docente en un periodo determinado."""

    id_grupo = models.AutoField(primary_key=True)
    clave = models.CharField(max_length=20)
    materia = models.CharField(max_length=120)
    periodo = models.CharField(max_length=10)
    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,      # RNF-05: no se borra un usuario con historial
        db_column='id_usuario',
        related_name='grupos',
    )

    class Meta:
        db_table = 'grupo'
        ordering = ['periodo', 'clave']
        constraints = [
            models.UniqueConstraint(
                fields=['clave', 'periodo'],
                name='uq_grupo_clave_periodo',
            ),
        ]

    def __str__(self):
        return f'{self.clave} ({self.periodo})'


class Inscripcion(models.Model):
    """Resuelve la relacion muchos a muchos entre grupo y alumno."""

    id_inscripcion = models.AutoField(primary_key=True)
    grupo = models.ForeignKey(
        Grupo, on_delete=models.CASCADE, db_column='id_grupo',
        related_name='inscripciones',
    )
    alumno = models.ForeignKey(
        Alumno, on_delete=models.PROTECT, db_column='id_alumno',
        related_name='inscripciones',
    )
    fecha_alta = models.DateField()

    class Meta:
        db_table = 'inscripcion'
        constraints = [
            # RF-05: impide inscribir dos veces al mismo alumno en el mismo grupo
            models.UniqueConstraint(
                fields=['grupo', 'alumno'],
                name='uq_inscripcion_grupo_alumno',
            ),
        ]

    def __str__(self):
        return f'{self.alumno} en {self.grupo}'


class Sesion(models.Model):
    """Cada clase programada de un grupo."""

    class Estado(models.TextChoices):
        PROGRAMADA = 'programada', 'Programada'
        REALIZADA = 'realizada', 'Realizada'
        CANCELADA = 'cancelada', 'Cancelada'

    id_sesion = models.AutoField(primary_key=True)
    grupo = models.ForeignKey(
        Grupo, on_delete=models.CASCADE, db_column='id_grupo',
        related_name='sesiones',
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PROGRAMADA,
    )

    class Meta:
        db_table = 'sesion'
        ordering = ['fecha', 'hora_inicio']
        constraints = [
            # RF-06: impide programar dos veces la misma sesion
            models.UniqueConstraint(
                fields=['grupo', 'fecha', 'hora_inicio'],
                name='uq_sesion_grupo_fecha_hora',
            ),
            models.CheckConstraint(
                condition=Q(hora_fin__gt=F('hora_inicio')),
                name='ck_sesion_horas',
            ),
        ]

    def __str__(self):
        return f'{self.grupo} - {self.fecha}'


class Asistencia(models.Model):
    """Registro de un alumno en una sesion. Tabla central del sistema."""

    class Estado(models.TextChoices):
        PRESENTE = 'presente', 'Presente'
        RETARDO = 'retardo', 'Retardo'
        AUSENTE = 'ausente', 'Ausente'
        JUSTIFICADO = 'justificado', 'Justificado'

    CUENTAN_COMO_ASISTENCIA = (Estado.PRESENTE, Estado.RETARDO, Estado.JUSTIFICADO)

    id_asistencia = models.AutoField(primary_key=True)
    sesion = models.ForeignKey(
        Sesion, on_delete=models.CASCADE, db_column='id_sesion',
        related_name='asistencias',
    )
    alumno = models.ForeignKey(
        Alumno, on_delete=models.PROTECT, db_column='id_alumno',
        related_name='asistencias',
    )
    estado = models.CharField(max_length=12, choices=Estado.choices)
    hora_registro = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='id_usuario', related_name='asistencias_registradas',
    )
    justificante = models.FileField(
        upload_to='justificantes/', blank=True, null=True,
    )

    class Meta:
        db_table = 'asistencia'
        constraints = [
            # RF-09: un alumno no puede tener dos registros en la misma sesion.
            # Es la regla que impide por diseno el error detectado en la entrevista.
            models.UniqueConstraint(
                fields=['sesion', 'alumno'],
                name='uq_asistencia_sesion_alumno',
            ),
            # RF-12: solo un registro justificado admite justificante
            models.CheckConstraint(
                condition=Q(justificante='') | Q(justificante__isnull=True)
                          | Q(estado='justificado'),
                name='ck_asistencia_justificante',
            ),
        ]

    def clean(self):
        if self.justificante and self.estado != self.Estado.JUSTIFICADO:
            raise ValidationError(
                {'justificante': 'Solo se puede adjuntar un justificante a un '
                                 'registro marcado como justificado.'}
            )

    def __str__(self):
        return f'{self.alumno} - {self.sesion} - {self.get_estado_display()}'


class BitacoraCambio(models.Model):
    """Historial de correcciones de asistencia (RF-11 y RNF-06).

    Solo admite inserciones: si se pudiera editar o borrar dejaria de servir
    como evidencia en una aclaracion de faltas. Las filas las escribe un
    disparador de la base de datos, definido en la migracion 0002.
    """

    id_bitacora = models.AutoField(primary_key=True)
    asistencia = models.ForeignKey(
        Asistencia, on_delete=models.CASCADE, db_column='id_asistencia',
        related_name='cambios',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='id_usuario', related_name='correcciones',
    )
    valor_anterior = models.CharField(max_length=12, choices=Asistencia.Estado.choices)
    valor_nuevo = models.CharField(max_length=12, choices=Asistencia.Estado.choices)
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bitacora_cambio'
        ordering = ['-fecha_cambio']
        constraints = [
            models.CheckConstraint(
                condition=~Q(valor_anterior=F('valor_nuevo')),
                name='ck_bitacora_cambio_real',
            ),
        ]

    def __str__(self):
        return f'{self.asistencia_id}: {self.valor_anterior} -> {self.valor_nuevo}'
```

Pendiente al copiarlo: agrega `indexes` en el `Meta` de `Sesion`, `Asistencia`, `Inscripcion` y `BitacoraCambio` según el RNF-07 (sección 7).

## Apéndice B. `asistencia/migrations/0002_trigger_bitacora.py`

```python
"""Crea el disparador de la bitacora de correcciones (RF-11 y RNF-06).

Se implementa en la base de datos y no en una senal de Django para que la
constancia quede registrada aunque alguien modifique la tabla de asistencia
desde fuera del sistema.
"""

from django.db import migrations


CREAR_DISPARADOR = """
CREATE TRIGGER trg_asistencia_bitacora
AFTER UPDATE ON asistencia
FOR EACH ROW
BEGIN
    IF NEW.estado <> OLD.estado THEN
        INSERT INTO bitacora_cambio
            (id_asistencia, id_usuario, valor_anterior, valor_nuevo, fecha_cambio)
        VALUES
            (NEW.id_asistencia, NEW.id_usuario, OLD.estado, NEW.estado, NOW());
    END IF;
END
"""

BORRAR_DISPARADOR = "DROP TRIGGER IF EXISTS trg_asistencia_bitacora"


class Migration(migrations.Migration):

    dependencies = [
        ('asistencia', '0001_initial'),
    ]

    operations = [
        # Se pasa como lista de un elemento para que Django no parta el
        # cuerpo del disparador por los ";" internos.
        migrations.RunSQL(
            sql=[CREAR_DISPARADOR],
            reverse_sql=BORRAR_DISPARADOR,
        ),
    ]
```

## Apéndice C. Configuración base

`requirements.txt`
```
Django>=5.2,<5.3
mysqlclient
python-dotenv
openpyxl
reportlab
```

`.env.example`
```
DJANGO_SECRET_KEY=cambia-esto
DJANGO_DEBUG=1
DB_NAME=control_asistencia
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306
ASISTENCIA_MINIMA=80
REGISTRO_DOMINIOS=uabc.edu.mx
```

Claves de `config/settings.py` que no pueden faltar:
```python
AUTH_USER_MODEL = 'asistencia.Usuario'
AUTHENTICATION_BACKENDS = ['asistencia.backends.EmailBackend']
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Tijuana'
LOGIN_URL = 'login'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
ASISTENCIA_MINIMA = int(os.environ.get('ASISTENCIA_MINIMA', 80))
REGISTRO_DOMINIOS = [d.strip().lower() for d in os.environ.get('REGISTRO_DOMINIOS', 'uabc.edu.mx').split(',') if d.strip()]
# DATABASES: engine 'django.db.backends.mysql', datos tomados de las variables DB_*.
```
