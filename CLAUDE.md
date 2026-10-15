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
│   │   └── 0002_trigger_bitacora.py   # Apéndice B
│   ├── backends.py          # EmailBackend (login con correo)
│   ├── permissions.py       # mixins: solo grupos del docente, solo administrador
│   ├── forms.py
│   ├── services/            # lógica fuera de las vistas
│   │   ├── importar_alumnos.py   # CSV (RF-04)
│   │   ├── generar_sesiones.py   # horario + periodo (RF-06)
│   │   └── reportes.py           # porcentajes, PDF, Excel (RF-13/14/15)
│   ├── views/               # auth.py, usuarios.py, grupos.py, sesiones.py, asistencia.py, reportes.py
│   ├── templates/asistencia/
│   ├── static/
│   ├── management/commands/seed_demo.py
│   └── tests/
├── docs/
│   └── informe_pruebas.md   # informe de la fase H
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
- Commits pequeños y en español, con el requisito al inicio: `RF-09: impedir registro duplicado`.
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

## 8. Modelo de datos

Siete tablas. La separación entre `alumno` e `inscripcion` permite que un alumno esté en varios grupos sin duplicar sus datos.

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
- **Alta de usuarios (RF-16).** Solo en el admin de Django, donde el administrador ve únicamente «Usuarios». El alta pide nombre, apellido, correo, rol, usuario y contraseña.
- **El rol manda sobre el acceso al admin.** Al guardar un usuario, `is_staff` y los permisos se ajustan al rol (`services/usuarios.py`): administrador con `is_staff` y solo ver/agregar/modificar usuario; docente sin `is_staff` y sin esos permisos. El admin no deja editar `is_staff`, superusuario, grupos ni permisos sueltos, para que nadie se dé más acceso. Quien gestiona usuarios no puede modificar a un superusuario. Un docente no entra al admin y un administrador no ve los grupos (403).
- **Bajas de usuarios.** No hay borrado de usuarios en el admin (ni la acción masiva): se desactivan con «Activo» (regla 9.5). No se puede desactivar ni quitar el rol al último administrador activo, ni desactivarse a uno mismo; la comprobación bloquea las filas de los administradores activos para que dos cambios simultáneos no la burlen.
- **`createsuperuser` y `seed_demo`.** `createsuperuser` sigue creando usuarios con rol docente; para tener un administrador de la aplicación se le cambia el rol desde el admin (README). `seed_demo` prepara el administrador de demo con las mismas reglas.

- **Pruebas de integración (fase H).** `test_flujos.py` encadena las pantallas por sus URL y formularios reales, con reloj fijo y cifras calculadas a mano. `test_matriz_de_acceso.py` toma las rutas de `urls.py`: una ruta nueva que no se clasifique rompe la primera prueba, a propósito, y obliga a decidir quién puede entrar. `test_rendimiento.py` protege contra un N+1 en las pantallas que no tenían prueba de conteo.
- **RNF-07 medido.** Con 6 grupos de 50 alumnos y 48 sesiones (14 400 registros) en MySQL, el peor caso fue 570 ms (importar un CSV de 50 alumnos) contra el límite de 3 s; las demás vistas quedaron por debajo de 280 ms en su peor repetición. Método y tabla completos en `docs/informe_pruebas.md`.
- **RNF-01 no se cronometra aquí.** Se mide el costo de interacción (5 excepciones = 5 toques y un envío; botones de 48 px; guardar siempre visible), no un tiempo humano. Verificarlo requiere probar con docentes.
- **Hallazgos de la fase H sin corregir** (ninguno crítico ni mayor, ver el informe): H-01 botones secundarios `btn-sm` de unos 31 px en el teléfono; H-02 no hay página 500 propia; H-03 la importación del CSV hace unas cinco consultas por fila (0.4 s con 50 filas, 3.8 s con las 500 que acepta como máximo; el RNF-07 solo acota grupos de 50).

### Decisiones abiertas

- **Mínimo de asistencia de 80 %.** Sigue siendo un supuesto sin confirmar (`ASISTENCIA_MINIMA`). Se ve en pantalla y en las exportaciones.
- **Hallazgos H-01 a H-03.** Decidir si se corrigen antes de la entrega (el informe propone cómo) o se dejan como mejoras.
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
# DATABASES: engine 'django.db.backends.mysql', datos tomados de las variables DB_*.
```
