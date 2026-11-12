# Plan de liberación de la versión 1.0.0

Sistema de Control de Asistencia · UABC, FCITEC · Administración de Proyectos de Software.

| | |
|---|---|
| **Versión que se libera** | `1.0.0` (primera versión en producción) |
| **Línea base de partida** | `v0.9.0` (11/11/2026), etiqueta anotada sobre `main` |
| **Fecha objetivo** | viernes 27/11/2026 (fecha límite de entrega del proyecto) |
| **Responsable de la decisión** | Líder de proyecto, como comité de control de cambios ([gestión de la configuración](gestion_configuracion.md), sección 1) |
| **Estado** | Plan del 11/11/2026. Dictamen vigente en la sección 11: **no-go para `1.0.0` hoy; go para fijar `0.9.0`** |

Este plan aplica la política de [gestion_configuracion.md](gestion_configuracion.md): números de versión (sección 5), ramas (sección 6), control de cambios (sección 7) y auditoría previa a cada etiqueta (sección 8). El detalle técnico del despliegue está en [DESPLIEGUE.md](DESPLIEGUE.md); aquí se decide cuándo, quién, con qué criterios y cómo se da marcha atrás.

## 1. Alcance

**Entra en `1.0.0`:**

1. Todo lo de `0.9.0`: los 20 requisitos funcionales y 9 de los 10 no funcionales implementados. El RNF-08 (respaldo diario) entra con la fase J, y el RNF-01 (pase de lista de 40 alumnos en 3 minutos) está implementado pero sin cronometrar con personas (R9).
2. Fase I: manual de usuario y manual de administrador (ECS-17).
3. Fase J, parte técnica ([DESPLIEGUE.md](DESPLIEGUE.md), bloques B2 a B8): configuración de producción, archivos estáticos, imagen Docker, `docker-compose.prod.yml`, respaldo diario con restauración probada (RNF-08, que incluye `media/`), contraseña de demostración protegida y sección «Despliegue» del README.
4. Capacitación a los docentes y acta de aceptación.

**No entra** (y no cambia el número de versión): elegir y contratar el hosting, abrir el firewall y apuntar el dominio (le toca al líder de proyecto, [DESPLIEGUE.md](DESPLIEGUE.md) sección 7); el hallazgo H-03 (importación de CSV de 500 filas), que es opcional; cualquier función nueva.

**Regla de congelamiento.** Desde el 20/11/2026 solo entran correcciones de defectos que impidan una de las pruebas de salida de la sección 3, cada una con su solicitud de cambio. Ninguna migración nueva: el esquema de `0.9.0` (migraciones 0001 a 0004) es el de `1.0.0`.

## 2. Línea base y elementos de configuración

La línea base de partida es la etiqueta `v0.9.0`. Los elementos son los del inventario de [gestion_configuracion.md](gestion_configuracion.md), sección 3. Lo que `1.0.0` agrega o modifica:

| ECS | Elemento | Cambio en `1.0.0` | Línea base |
|---|---|---|---|
| ECS-08 | `config/settings.py`, `.env.example`, `requirements.txt` | Variables de producción (`DJANGO_HTTPS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_STATIC_MANIFEST`), clave obligatoria, `STATIC_ROOT`, WhiteNoise; `gunicorn` y `whitenoise` en `requirements.txt` (con aprobación del líder) y versiones exactas de todas las dependencias (solicitud de cambio CR-002, prevista: cambia un elemento que ya está en la línea base) | LB-C |
| ECS-06 | `asistencia/templates/500.html` | Hecho con [CR-001](cambios/CR-001_pagina_500.md), entra en `0.9.0` | LB-C |
| ECS-11 | `seed_demo` | Se niega a crear cuentas con la contraseña por defecto cuando `DEBUG=0` | LB-C |
| nuevo | `Dockerfile`, `.dockerignore`, entrypoint | Imagen de la aplicación (B4) | LB-L |
| nuevo | `docker-compose.prod.yml`, `.env.prod.example` | Pila de producción: `db`, `web` y `proxy` (B5) | LB-L |
| nuevo | `scripts/respaldo.sh` | Respaldo diario de la base y de `media/` con retención de 14 copias (B6) | LB-L |
| ECS-14 | `README.md` | Sección «Despliegue» y restauración | LB-L |
| ECS-17 | Manual de usuario y manual de administrador | Se crean (fase I) | LB-L |
| ECS-15 | `CHANGELOG.md` | Sección `[1.0.0]` | LB-L |

**Identificación de la liberación.** Candidata `v1.0.0-rc.1` cuando el bloque B8 pase en la pila real; `v1.0.0-rc.2` y siguientes si hay correcciones; `v1.0.0` es la etiqueta anotada sobre el mismo commit de `main` que pasó la auditoría. Una etiqueta publicada no se mueve: un error se corrige con otra versión (`1.0.1`), nunca reescribiendo la etiqueta.

## 3. Criterios de entrada y de salida

### Entrada (para abrir la rama `release/v1.0.0`)

| # | Criterio | Cómo se comprueba |
|---|---|---|
| E1 | Todo requisito de prioridad Alta está implementado y tiene prueba | `CLAUDE.md` sección 12 y [informe_pruebas.md](informe_pruebas.md) |
| E2 | La suite completa pasa en MySQL 8 | `python manage.py test --noinput` termina con `OK` |
| E3 | La línea base `v0.9.0` está etiquetada y el `CHANGELOG` está al día | `git tag -l -n` y `CHANGELOG.md` |
| E4 | No hay hallazgos críticos ni mayores abiertos | [informe_pruebas.md](informe_pruebas.md), sección 11 |
| E5 | El hosting está decidido (internet con dominio, o demostración local) | Respuesta del líder a la pregunta 1 de [DESPLIEGUE.md](DESPLIEGUE.md) sección 3 |
| E6 | El mínimo de asistencia está confirmado con la profesora | `ASISTENCIA_MINIMA` deja de ser un supuesto en `CLAUDE.md` |

### Salida (go para etiquetar `v1.0.0`)

Se deben cumplir **todos** (S1 a S10). Un solo «no» es no-go.

| # | Criterio | Cómo se comprueba |
|---|---|---|
| S1 | Los 12 puntos de la lista de verificación de [DESPLIEGUE.md](DESPLIEGUE.md) sección 6 pasan en la pila real | Resultado de cada punto anotado en el informe de la liberación |
| S2 | La suite completa pasa, sin la variable `DJANGO_STATIC_MANIFEST` | `Ran N tests … OK`, con N mayor o igual que 650 |
| S3 | El respaldo genera la base y `media/`, y la restauración de prueba (como `root`) coincide en filas, conserva el disparador y un `UPDATE` de `estado` con `ROLLBACK` no da el error 1449 | Pasos de B6 |
| S4 | `python manage.py check --deploy` sin advertencias, salvo `W008`, justificada | Salida del comando |
| S5 | Ninguna URL pública sirve `media/` y el 3306 no está publicado | `/media/...` responde 404; `docker compose ps` sin mapeo para `db` |
| S6 | Existen el manual de usuario y el de administrador | Archivos en el repositorio, enlazados desde el README |
| S7 | Un docente y el administrador completan los flujos principales en la pila real (periodo, grupo, CSV, sesiones, pase de lista, corrección, justificante, reporte y exportación) | Recorrido de aceptación hecho por una persona que no programó el sistema (un docente o la profesora), con el resultado anotado |
| S8 | Auditoría funcional y física sin diferencias ([gestion_configuracion.md](gestion_configuracion.md), sección 8) | Sección 9 de este plan |
| S9 | `git status` limpio y ningún `.env*`, `media/`, `respaldos/` ni `*.sql.gz` versionado | `git check-ignore -v` |
| S10 | `requirements.txt` tiene versiones exactas y la imagen se construye con ellas (CR-002 integrada) | Cada línea con `==`; `pip check` sin conflictos dentro de la imagen |

### Condiciones de no-go inmediato

Una de estas, en cualquier momento, detiene la liberación: una prueba automática en rojo; un secreto o un dato de alumnos en el repositorio; el disparador de la bitácora no escribe con el usuario de la aplicación; `media/` accesible por una URL pública; una restauración que no se ha probado.

## 4. Calendario y responsables

La fecha de hoy es el miércoles 11/11/2026. El lunes 16/11 es descanso obligatorio (tercer lunes de noviembre, artículo 74 de la Ley Federal del Trabajo), así que quedan 11 días hábiles hasta el viernes 27/11. Los roles son los del cronograma; una sola persona puede cubrir varios ([gestion_configuracion.md](gestion_configuracion.md), sección 1).

| Fecha | Actividad | Resultado | Rol responsable |
|---|---|---|---|
| mié 11/11 | Fusionar los PR, auditar y etiquetar `v0.9.0` | Línea base `0.9.0` | Líder de proyecto |
| jue 12 y vie 13/11 | Fase I: manual de usuario y manual de administrador | ECS-17 | Documentador |
| lun 16/11 | **Descanso obligatorio**: sin actividad | | |
| mar 17/11 | Decidir el hosting (E5) y confirmar el mínimo de asistencia (E6); B2 configuración de producción | Decisiones anotadas en `CLAUDE.md`; `settings.py` de producción | Líder de proyecto y backend |
| mié 18/11 | B3 estáticos y B4 imagen, con CR-002 (versiones exactas) | Imagen que arranca | Backend y frontend |
| jue 19/11 | B5 pila de producción y B6 respaldo con restauración probada | Pila completa y respaldo verificado | Backend y base de datos |
| vie 20/11 | B7 contraseña de demostración y README; B8 verificación en la pila real; congelamiento y etiqueta `v1.0.0-rc.1` | Informe de la lista de verificación | Pruebas |
| lun 23 y mar 24/11 | Recorrido de aceptación (S7), medición del RNF-01 con personas y capacitación | Defectos encontrados, con su solicitud de cambio si hacen falta | Pruebas y líder de proyecto |
| mié 25/11 | Correcciones y, si las hay, `v1.0.0-rc.2` | Candidata final | Backend |
| jue 26/11 | Auditoría funcional y física, y decisión go/no-go final | Dictamen actualizado (sección 11) | Líder de proyecto |
| vie 27/11 | Etiqueta `v1.0.0`, despliegue, acta de aceptación, publicación de la versión en GitHub con sus notas y entrega | Versión 1.0.0 en producción | Líder de proyecto |

La ruta crítica es la de [CLAUDE.md](../CLAUDE.md) sección 11: la fase J no tiene holgura. Con el feriado, los bloques B2 a B8 quedan en cuatro días (17 al 20/11). Si B8 no termina el 20/11, pasa al 23/11 y el recorrido de aceptación se reduce a un solo día; el congelamiento y la fecha de entrega no se mueven.

## 5. Ambientes y procedimiento de despliegue

### Ambientes

| Ambiente | Para qué | Cómo está montado |
|---|---|---|
| Desarrollo | Escribir y probar a mano | Equipo de desarrollo, `runserver`, MySQL 8 de `docker-compose.yml`, archivo `.env` |
| Pruebas automáticas | Suite completa | Base `test_*` de MySQL 8 que crea el ejecutor de Django; con `DEBUG` forzado en falso y reloj fijo en las pruebas que lo necesitan |
| Ensayo (preproducción) | B8: la pila de producción, sin datos reales | `docker-compose.prod.yml` con proyecto propio `control_asistencia_prod` y `DOMINIO=http://localhost`; es el ensayo previo a producción, porque no hay un ambiente de pruebas separado |
| Producción | El sistema en uso | Servidor por definir (E5) con la misma pila del ensayo; con dominio, HTTPS automático de Caddy; sin dominio, HTTP y aviso en el README |

No hay integración continua configurada: la suite se corre a mano y su resultado se anota. Agregarla no es un requisito del proyecto y queda fuera de este plan.

### Procedimiento (primer despliegue)

1. En el servidor: Docker y Compose instalados; firewall con solo los puertos 22, 80 y 443.
2. `git clone` del repositorio y `git checkout v1.0.0` (nunca `main`: se despliega una etiqueta).
3. `cp .env.prod.example .env.prod` y completar los marcadores `CAMBIA-ESTO` con valores propios: clave de Django larga, contraseñas de la base, dominio y `DJANGO_ALLOWED_HOSTS`. El archivo no se versiona (`git check-ignore -v .env.prod`).
4. `docker compose -f docker-compose.prod.yml up -d --build`. El entrypoint espera a la base y ejecuta `migrate`, que crea el disparador de la bitácora con el usuario de la aplicación.
5. Crear el primer administrador con `createsuperuser` y cambiarle el rol desde el admin (README). **No se ejecuta `seed_demo` en producción.**
6. El administrador crea y activa el primer periodo en «Periodos»: sin periodo activo no se pueden crear grupos.
7. Instalar la línea de `cron` del respaldo diario (la da el README) y ejecutar el respaldo una vez a mano.
8. Prueba de humo: iniciar sesión, abrir un grupo, ver una página 404 y confirmar que `/media/` responde 404.

### Procedimiento (actualizar)

1. Ejecutar `scripts/respaldo.sh` y comprobar que generó los dos archivos. **Sin copia no se actualiza.**
2. `git fetch --tags` y `git checkout vX.Y.Z`.
3. `docker compose -f docker-compose.prod.yml up -d --build` (**sin `down -v`**: borraría los volúmenes).
4. Prueba de humo del paso 8 anterior y revisión de los registros del contenedor `web`.

## 6. Riesgos

Probabilidad e impacto en tres niveles (A alta, M media, B baja).

| # | Riesgo | Prob. | Impacto | Mitigación | Disparador |
|---|---|---|---|---|---|
| R1 | El hosting sigue sin definirse | A | A | Decidirlo el 17/11 (E5); la misma pila sirve para internet y para una demostración local, así que el peor caso es entregar la demostración local y documentarlo | Sin decisión al 17/11 |
| R2 | Los manuales (fase I) no se terminan y no se puede firmar el acta | M | A | Escribirlos el 12 y 13/11, antes de que empiece el despliegue; el criterio S6 los exige | Sin manuales el 17/11 |
| R3 | `mysqlclient` no compila en la imagen o no autentica contra MySQL 8 (no está comprobado en Linux) | M | A | Comprobarlo en B4/B5 con `migrate` dentro del contenedor; plan B: `PyMySQL` ([CLAUDE.md](../CLAUDE.md) sección 3) | Falla `up --build` el 18/11 |
| R4 | Al restaurar en otro servidor, el disparador queda con un usuario `DEFINER` inexistente y todo `UPDATE` de asistencia falla (error 1449) | M | A | Levantar primero la pila con el mismo `.env.prod` y restaurar después; el criterio S3 lo prueba con un `UPDATE` y `ROLLBACK` | Error 1449 en la restauración de prueba |
| R5 | Olvidar `collectstatic` rompe todas las pantallas, no solo el admin | M | A | `collectstatic` en la construcción de la imagen (B4); el punto 3 de la lista de verificación comprueba que cargan las tres hojas de estilo | Pantallas sin estilo o error `Missing staticfiles manifest entry` |
| R6 | Registro público sin límite de intentos ni CAPTCHA: cuentas pendientes que se acumulan | M | M | `REGISTRO_DOMINIOS` solo con dominios institucionales (o vacía); revisar el Panel; limitar `/registro/` en el proxy si hace falta | Más de 20 cuentas pendientes sin atender |
| R7 | La contraseña de demostración está en el historial de un repositorio público | A | M | Ninguna cuenta de demostración existe en un entorno real; `seed_demo` se niega con `DEBUG=0` (B7); el líder decide si el repositorio sigue público | Cualquier acceso con la contraseña de `seed_demo` en producción |
| R8 | El mínimo de asistencia (80 %) es un supuesto sin confirmar | M | M | Confirmarlo con la profesora (E6) el 17/11; es una variable de entorno (`ASISTENCIA_MINIMA`), cambiarla no requiere código | Respuesta distinta al 80 % |
| R9 | El RNF-01 (pase de lista de 40 alumnos en 3 minutos) no se ha cronometrado con personas | M | M | Medirlo el 23 y 24/11 con docentes; el costo medido es de 9 toques para 5 excepciones y un solo envío | Más de 3 minutos en la medición |
| R10 | Solo cuatro días hábiles (17 al 20/11, por el feriado del 16) para los bloques B2 a B8, con un solo desarrollador y una fecha límite que no se mueve | A | A | Congelamiento el 20/11, criterios de salida cerrados desde hoy y regla de que lo Media se difiere antes de arriesgar la fecha ([CLAUDE.md](../CLAUDE.md) sección 11) | B8 sin terminar el 20/11 |
| R11 | Las copias de respaldo viven en la misma máquina que la base: se pierden con ella | M | A | Decidir dónde se copian fuera del servidor (pregunta 4 de [DESPLIEGUE.md](DESPLIEGUE.md)); mientras tanto, aviso explícito en el README | Sin destino externo al 26/11 |
| R12 | Bootstrap se carga desde un CDN: sin internet en el salón, las pantallas pierden el estilo base | B | M | Si la capacitación es sin internet, autoalojarlo con las precauciones de B3 | Capacitación sin red |
| R13 | Las dependencias no tienen versión exacta (`Django>=5.2,<5.3` y cuatro paquetes sin versión): la imagen de hoy y la de dentro de una semana pueden diferir, y una reversión reconstruiría con otras versiones | M | A | CR-002: versiones exactas en `requirements.txt` antes de B4; criterio S10 | La imagen de `rc.1` y la de `rc.2` difieren en alguna dependencia sin que nadie la haya cambiado |

## 7. Plan de reversión

**Qué se puede revertir y cómo.** La versión `1.0.0` no agrega migraciones, así que el esquema de la base es el mismo que el de `0.9.0`: el código se puede revertir sin tocar los datos. Lo que cambia es el punto de vuelta: en el primer despliegue no hay versión anterior a la que volver.

| Situación | Acción | Tiempo máximo |
|---|---|---|
| **Primer despliegue:** la prueba de humo falla | No hay versión anterior en producción ni compose de producción en `0.9.0`. Se baja la pila con `docker compose -f docker-compose.prod.yml down` (**sin `-v`**), se deja el sistema fuera de servicio y se corrige en una rama; los volúmenes no se tocan | 15 minutos |
| **Actualización desde `1.0.0`:** la prueba de humo falla | Volver a la etiqueta anterior: `git checkout vX.Y.Z` y `docker compose -f docker-compose.prod.yml up -d --build`. Los datos no se tocan porque el esquema no cambió. Con las versiones exactas de CR-002, la imagen reconstruida es la misma que la anterior | 15 minutos |
| El código nuevo escribió datos incorrectos (por ejemplo, registros de asistencia con un error) | Restaurar la copia previa a la actualización (base y `media/`) como `root`, con los pasos de B6. Si se restaura en otro servidor, levantar antes la pila con el mismo `.env.prod` (R4) | 1 hora |
| El servidor se perdió | Servidor nuevo, misma pila y `.env.prod`, restaurar la última copia diaria. Se pierde, como máximo, lo registrado desde la última copia (hasta 24 horas) | 2 horas |

**Quién decide.** El líder de proyecto decide la reversión; si la prueba de humo no está en verde 30 minutos después del despliegue, se revierte sin más discusión.

**Reglas.**

- Una etiqueta publicada no se mueve ni se borra. Si `v1.0.0` resulta mala, se publica `v1.0.1` con la corrección, y en el `CHANGELOG` la versión mala se marca con `[YANKED]` (Keep a Changelog).
- Antes de cualquier reversión de datos se hace una copia de lo que hay, aunque esté mal: nada se sobrescribe sin copia.
- Si una futura solicitud de cambio agrega una migración, este plan cambia: la reversión de código ya no basta y hay que restaurar la copia previa a la migración.
- Tras una reversión se escribe una nota en `docs/cambios/` con la causa; ese es el insumo de la corrección.

## 8. Comunicación

| A quién | Qué | Cuándo | Por qué medio |
|---|---|---|---|
| Profesora de la materia | Avance contra el cronograma y decisiones pendientes (hosting y mínimo de asistencia) | Cada semana y el 17/11 | Tablero de Trello y [seguimiento_semanal.md](seguimiento_semanal.md) |
| Docentes que usarán el sistema | Fecha y contenido de la capacitación; qué cuenta crear (registro con correo institucional y espera de aprobación) | 20/11 | Mensaje del líder, con enlace al manual de usuario |
| Administrador del sistema | Cómo aprobar cuentas, activar periodos y respaldar | 23/11, junto con la capacitación | Manual de administrador |
| Quien revise el repositorio | Qué trae cada versión y cómo se desplegó | En cada etiqueta | `CHANGELOG.md`, notas de la etiqueta y este plan |
| Todos | Aviso de liberación y de cualquier reversión, con la causa | El mismo día | Mensaje del líder y nota en `docs/cambios/` |

## 9. Notas de versión (borrador de la 1.0.0)

Este borrador se completa al etiquetar. El texto definitivo va en `CHANGELOG.md` (sección `[1.0.0]`) y en la publicación de la versión en GitHub.

**Qué es.** Primera versión en producción del Sistema de Control de Asistencia: sustituye las listas de asistencia en papel por una aplicación web para docentes y administradores, con registro por sesión, correcciones con historial, justificantes y reportes exportables.

**Qué trae respecto a `0.9.0`.**

- Despliegue con Docker: base de datos, aplicación y proxy en una sola pila (`docker-compose.prod.yml`).
- Respaldo diario de la base de datos y de los justificantes (RNF-08), con restauración probada.
- Configuración de producción: clave obligatoria, HTTPS cuando hay dominio, archivos estáticos servidos por la aplicación y contraseña de demostración protegida.
- Manual de usuario y manual de administrador.
- Versiones exactas de las dependencias.

**Compatibilidad y actualización.** Sin migraciones nuevas: el esquema es el de `0.9.0` (migraciones 0001 a 0004). Las variables de entorno nuevas son solo de producción (`DJANGO_HTTPS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_STATIC_MANIFEST`, `DOMINIO`); el `.env` de desarrollo no cambia. Requiere MySQL 8 (MariaDB no sirve: usa disparador, restricciones `CHECK` e índice único sobre una expresión).

**Problemas conocidos.**

- El mínimo de asistencia (80 %) es un supuesto sin confirmar con la profesora; se cambia con `ASISTENCIA_MINIMA`.
- El pase de lista de 40 alumnos en 3 minutos (RNF-01) no se ha cronometrado con personas; se mide el costo de interacción (9 toques para 5 excepciones, y un solo envío).
- La importación de un CSV de 500 filas tarda unos 3.8 s (hallazgo H-03); con grupos de 50 alumnos tarda 0.4 s.
- El registro de docentes no tiene límite de intentos, CAPTCHA ni confirmación del correo: el control es la aprobación del administrador y el dominio permitido.
- Bootstrap se carga desde un CDN: sin internet las pantallas pierden el estilo base.
- Las copias de respaldo viven en el servidor salvo que se defina un destino externo.

**Seguridad.** No se ejecuta `seed_demo` en producción: su contraseña está en el historial de un repositorio público.

**Cómo comprobar la instalación.** Iniciar sesión, abrir un grupo, ver la página 404 de un recurso inexistente y confirmar que `/media/` responde 404 (procedimiento de la sección 5).

## 10. Registro de auditoría de configuración

La auditoría la define [gestion_configuracion.md](gestion_configuracion.md), sección 8. Se anota aquí el resultado de cada etiqueta.

*(El registro de `v0.9.0` se completa al etiquetar; el de `v1.0.0`, el 26/11/2026.)*

## 11. Dictamen go/no-go

**Fecha del dictamen:** 11/11/2026. **Decide:** líder de proyecto (CCB).

| Decisión | Dictamen | Razón |
|---|---|---|
| Fijar la línea base `v0.9.0` | **Go** | La suite completa pasa; todos los requisitos de prioridad Alta tienen prueba y no hay hallazgos críticos ni mayores. No es una versión de producción y se declara así en el `CHANGELOG` |
| Liberar `v1.0.0` hoy | **No-go** | No se cumplen E5 ni E6, y los criterios de salida S1 a S8 dependen de cosas que todavía no existen: la fase J no se ha ejecutado, no hay manuales y no hay un servidor |

**Condiciones para pasar a go el 26/11/2026:** los diez criterios de salida (S1 a S10) cumplidos y ninguna condición de no-go inmediato. Mientras tanto, el dictamen se actualiza en cada candidata (`rc.N`).

**Limitación.** El proyecto es individual: quien lo programa también ejerce el comité de control de cambios y decide el go. No se puede crear un comité de varias personas; se compensa con dos condiciones: el criterio S7 lo ejecuta otra persona y el acta de aceptación debe estar firmada por la profesora antes de dar el go final.
