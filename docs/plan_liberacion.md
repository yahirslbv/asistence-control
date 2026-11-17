# Plan de liberación de la versión 1.0.0

Sistema de Control de Asistencia · UABC, FCITEC · Administración de Proyectos de Software.

| | |
|---|---|
| **Versión que se libera** | `1.0.0` (primera versión en producción) |
| **Línea base de partida** | `v0.9.0` (11/11/2026), etiqueta anotada sobre `main` |
| **Fecha objetivo** | viernes 27/11/2026 (fecha límite de entrega del proyecto) |
| **Responsable de la decisión** | Líder de proyecto, como comité de control de cambios ([gestión de la configuración](gestion_configuracion.md), sección 1) |
| **Estado** | Plan del 11/11/2026. Dictamen vigente en la sección 11: **no-go para `1.0.0` hoy; go para fijar `0.9.0`**. La candidata `v1.0.0-rc.1` se verificó y se etiquetó el 16/11/2026; la `v1.0.0-rc.2` (con los manuales) se verificó y se etiquetó el 17/11/2026 (sección 10) |

Este plan aplica la política de [gestion_configuracion.md](gestion_configuracion.md): números de versión (sección 5), ramas (sección 6), control de cambios (sección 7) y auditoría previa a cada etiqueta (sección 8). El detalle técnico del despliegue está en [DESPLIEGUE.md](DESPLIEGUE.md); aquí se decide cuándo, quién, con qué criterios y cómo se da marcha atrás.

## 1. Alcance

**Entra en `1.0.0`:**

1. Todo lo de `0.9.0`: los 20 requisitos funcionales y 9 de los 10 no funcionales implementados. El RNF-08 (respaldo diario) entra con la fase J, y el RNF-01 (pase de lista de 40 alumnos en 3 minutos) está implementado y se verificó por simulación el 16/11/2026 ([aceptacion_simulada.md](aceptacion_simulada.md), R9).
2. Fase I: manual de usuario y manual de administrador (ECS-17).
3. Fase J, parte técnica ([DESPLIEGUE.md](DESPLIEGUE.md), bloques B2 a B8): configuración de producción, archivos estáticos, imagen Docker, `docker-compose.prod.yml`, respaldo diario con restauración probada (RNF-08, que incluye `media/`), contraseña de demostración protegida y sección «Despliegue» del README.
4. Capacitación a los docentes y acta de aceptación: **opcionales**. Victo decidió el 16/11/2026 que no son necesarias por ser un proyecto escolar; si la profesora las pide, se hacen.

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
| E6 | El mínimo de asistencia está confirmado | **Cumplido el 16/11/2026:** Victo confirmó el 80 %, sin consultarlo con la profesora. `ASISTENCIA_MINIMA` deja de ser un supuesto en `CLAUDE.md` |

### Salida (go para etiquetar `v1.0.0`)

Se deben cumplir **todos** (S1 a S10). Un solo «no» es no-go.

| # | Criterio | Cómo se comprueba |
|---|---|---|
| S1 | Los 12 puntos de la lista de verificación de [DESPLIEGUE.md](DESPLIEGUE.md) sección 6 pasan en la pila real | Resultado de cada punto anotado en el informe de la liberación |
| S2 | La suite completa pasa, sin la variable `DJANGO_STATIC_MANIFEST` | `Ran N tests … OK`, con N mayor o igual que 650 |
| S3 | El respaldo genera la base y `media/`, y la restauración de prueba (como `root`) coincide en filas, conserva el disparador y un `UPDATE` de `estado` con `ROLLBACK` no da el error 1449 | Pasos de B6 |
| S4 | `python manage.py check --deploy`, con `DJANGO_HTTPS=1`, sin más advertencias que `W005`, `W008` y `W021`, las tres justificadas en el README. **Ajustado el 16/11/2026 por decisión del líder:** antes admitía solo `W008`, pero al activar HSTS aparecen las otras dos | Salida del comando dentro del contenedor |
| S5 | Ninguna URL pública sirve `media/` y el 3306 no está publicado | `/media/...` responde 404; `docker compose ps` sin mapeo para `db` |
| S6 | Existen el manual de usuario y el de administrador | Archivos en el repositorio, enlazados desde el README |
| S7 | Un docente y el administrador completan los flujos principales en la pila real (periodo, grupo, CSV, sesiones, pase de lista, corrección, justificante, reporte y exportación) | Recorrido de aceptación **simulado** (decisión de Victo del 16/11/2026, en lugar de una persona que no programó el sistema): [aceptacion_simulada.md](aceptacion_simulada.md). En B8 se repiten en la pila real los pasos de los puntos 2, 4 y 5 de la lista de verificación |
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
| mar 17/11 | Decidir el hosting (E5) y confirmar el mínimo de asistencia (E6, hecho el 16/11); B2 configuración de producción | Decisiones anotadas en `CLAUDE.md`; `settings.py` de producción | Líder de proyecto y backend |
| mié 18/11 | B3 estáticos y B4 imagen, con CR-002 (versiones exactas) | Imagen que arranca | Backend y frontend |
| jue 19/11 | B5 pila de producción y B6 respaldo con restauración probada | Pila completa y respaldo verificado | Backend y base de datos |
| vie 20/11 | B7 contraseña de demostración y README; B8 verificación en la pila real; congelamiento y etiqueta `v1.0.0-rc.1` | Informe de la lista de verificación | Pruebas |
| lun 23 y mar 24/11 | Recorrido de aceptación (S7) y RNF-01: simulados el 16/11 ([aceptacion_simulada.md](aceptacion_simulada.md)); capacitación opcional | Defectos encontrados, con su solicitud de cambio si hacen falta | Pruebas y líder de proyecto |
| mié 25/11 | Correcciones y, si las hay, `v1.0.0-rc.2` | Candidata final | Backend |
| jue 26/11 | Auditoría funcional y física, y decisión go/no-go final | Dictamen actualizado (sección 11) | Líder de proyecto |
| vie 27/11 | Etiqueta `v1.0.0` (**adelantada al 17/11/2026** por decisión del líder), despliegue, acta de aceptación (opcional), publicación de la versión en GitHub con sus notas y entrega | Versión 1.0.0 en producción | Líder de proyecto |

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
| R8 | **Cerrado el 16/11/2026:** el mínimo de asistencia (80 %) lo confirmó Victo | M | M | Confirmado (E6); es una variable de entorno (`ASISTENCIA_MINIMA`), cambiarla no requiere código | Respuesta distinta al 80 % |
| R9 | El RNF-01 (pase de lista de 40 alumnos en 3 minutos) no se ha cronometrado con personas: se verificó por simulación el 16/11 (estimación, no medición, [aceptacion_simulada.md](aceptacion_simulada.md)) | M | M | Medirlo con docentes si la profesora lo pide; el costo medido es de 9 toques para 5 excepciones y un solo envío | Más de 3 minutos en la medición |
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
| Profesora de la materia | Avance contra el cronograma y decisiones pendientes (hosting) | Cada semana y el 17/11 | Tablero de Trello y [seguimiento_semanal.md](seguimiento_semanal.md) |
| Docentes que usarán el sistema (opcional) | Fecha y contenido de la capacitación; qué cuenta crear (registro con correo institucional y espera de aprobación) | 20/11 | Mensaje del líder, con enlace al manual de usuario |
| Administrador del sistema | Cómo aprobar cuentas, activar periodos y respaldar | 23/11, si hay capacitación | Manual de administrador |
| Quien revise el repositorio | Qué trae cada versión y cómo se desplegó | En cada etiqueta | `CHANGELOG.md`, notas de la etiqueta y este plan |
| Todos | Aviso de liberación y de cualquier reversión, con la causa | El mismo día | Mensaje del líder y nota en `docs/cambios/` |

## 9. Notas de versión (borrador de la 1.0.0)

Este borrador se completa al etiquetar (actualizado el 17/11/2026). El texto definitivo va en `CHANGELOG.md` (sección `[1.0.0]`, ya en `main` desde el 17/11/2026 con el pull request #10) y en la publicación de la versión en GitHub.

**Qué es.** Primera versión en producción del Sistema de Control de Asistencia: sustituye las listas de asistencia en papel por una aplicación web para docentes y administradores, con registro por sesión, correcciones con historial, justificantes y reportes exportables.

**Qué trae respecto a `0.9.0`.**

- Despliegue con Docker: base de datos, aplicación y proxy en una sola pila (`docker-compose.prod.yml`). En Windows, `scripts\demo.ps1` levanta la demostración local con un comando.
- Respaldo diario de la base de datos y de los justificantes (RNF-08), con restauración probada.
- Configuración de producción: clave obligatoria, HTTPS cuando hay dominio, archivos estáticos servidos por la aplicación y contraseña de demostración protegida.
- Manual de usuario (docente) y manual de administrador, con capturas de cada pantalla.
- Versiones exactas de las dependencias.

**Compatibilidad y actualización.** Sin migraciones nuevas: el esquema es el de `0.9.0` (migraciones 0001 a 0004). Las variables de entorno nuevas son solo de producción (`DJANGO_HTTPS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_STATIC_MANIFEST`, `DOMINIO`, y `PUERTO_HTTP` y `PUERTO_HTTPS` para la pila); el `.env` de desarrollo no cambia. Con `DJANGO_DEBUG=0` la aplicación exige una `DJANGO_SECRET_KEY` propia y `seed_demo` exige `SEED_PASSWORD`. Requiere MySQL 8 (MariaDB no sirve: usa disparador, restricciones `CHECK` e índice único sobre una expresión).

**Problemas conocidos.**

- El mínimo de asistencia es de 80 % (confirmado por Victo el 16/11/2026); se cambia con `ASISTENCIA_MINIMA`.
- El pase de lista de 40 alumnos en 3 minutos (RNF-01) se verificó por simulación, no con personas; se mide el costo de interacción (9 toques para 5 excepciones, y un solo envío).
- La importación de un CSV de 500 filas tarda unos 3.8 s (hallazgo H-03); con grupos de 50 alumnos tarda 0.4 s.
- El registro de docentes no tiene límite de intentos, CAPTCHA ni confirmación del correo: el control es la aprobación del administrador y el dominio permitido.
- Bootstrap se carga desde un CDN: sin internet las pantallas pierden el estilo base.
- Las copias de respaldo quedan en el mismo equipo que la base (decisión del 16/11/2026): no protegen contra la pérdida del equipo. La tarea programada del respaldo hay que instalarla a mano (el README trae la línea de `cron` y el comando de `schtasks`).
- Se entrega como demostración local por HTTP (`http://localhost`); el despliegue con dominio y HTTPS está documentado pero no se ejecutó. El proxy solo atiende el nombre de `DOMINIO`: por `http://127.0.0.1` se ve una página en blanco.
- Con `DJANGO_DEBUG=0`, un error del servidor muestra la página 500 propia, pero su causa no queda en los registros del contenedor; solo la línea de acceso con el código 500.

**Seguridad.** No se ejecuta `seed_demo` en producción: su contraseña está en el historial de un repositorio público.

**Cómo comprobar la instalación.** Iniciar sesión, abrir un grupo, ver la página 404 de un recurso inexistente y confirmar que `/media/` responde 404 (procedimiento de la sección 5).

## 10. Registro de auditoría de configuración

La auditoría la define [gestion_configuracion.md](gestion_configuracion.md), sección 8. Se anota aquí el resultado de cada etiqueta.

### Registro de `v0.9.0` (11/11/2026)

**Qué se auditó.** El commit `041705e` de la rama `cambio/cr-001-pagina-500` (árbol `e3772eba0c9472adf38aeb69532a189c232591b0`): el resultado de integrar `main`, que ya traía la liberación del PR #3, con la solicitud de cambio CR-001. Al fusionar el PR #2 con un commit de fusión, `main` queda con ese mismo árbol, más una sola diferencia: el commit siguiente agrega este registro y no toca ningún otro archivo (la evidencia de la etiqueta lo muestra con `git diff --stat`).

| # | Comprobación | Tipo | Comando | Resultado |
|---|---|---|---|---|
| 1 | La suite completa pasa en una base MySQL 8 limpia | Funcional | `python manage.py test --noinput` (MySQL 8.0 en Docker; el ejecutor crea y borra la base de pruebas) | **Pasa.** `Ran 650 tests in 575.198s` y `OK`, sobre el commit de integración `e2dbceb`. El commit auditado solo difiere de ese en `README.md`, `docs/DESPLIEGUE.md` y `docs/seguimiento_semanal.md` |
| 2 | Cada requisito de prioridad Alta tiene prueba | Funcional | `grep -lE "RF-NN" asistencia/tests/*.py` para RF-01, 02, 03, 04, 06, 08, 09, 10, 11, 13 y 14 | **Pasa, con límite.** Los 11 requisitos aparecen nombrados en al menos un archivo de pruebas. Es trazabilidad por nombre, no una medición de cobertura |
| 3 | Los hallazgos abiertos están revisados | Funcional | Sección de hallazgos de `docs/informe_pruebas.md` | **Pasa.** H-01 y H-02 están corregidos (el H-02 con CR-001). Queda abierto el H-03 (menor), que la sección 1 de este plan deja como opcional |
| 4 | `git status` sin cambios | Física | `git status --porcelain` | **Pasa.** La salida está vacía |
| 5 | Los archivos versionados coinciden con la estructura de `CLAUDE.md`, sección 4 | Física | Script que compara `git ls-files` con el bloque de estructura (`comparar_estructura.py`, fuera del repositorio) | **Pasa con observación.** Los 38 elementos que documenta la sección 4 existen. De los 133 archivos versionados, 25 no aparecen en ella: módulos de `services/`, archivos `__init__.py`, `apps.py`, `urls.py`, plantillas de error y de administración, `CLAUDE.md` y `docker-compose.yml`. La sección 4 es un resumen, no un inventario; ninguno de los 25 es un secreto ni un archivo generado |
| 6 | Ningún `.env*`, `media/`, `respaldos/` ni `*.sql.gz` está versionado | Física | `git check-ignore -v .env .env.prod respaldos/x media/x dump.sql.gz` y `git ls-files` filtrado por esos nombres | **Pasa.** Los cinco quedan ignorados (líneas 3, 4, 14, 15 y 17 de `.gitignore`) y no hay ninguno versionado |
| 7 | El número de la etiqueta coincide con el del CHANGELOG | Física | `grep -m1 -E '^## \[[0-9]' CHANGELOG.md` | **Pasa.** El primer encabezado es `## [0.9.0] - 2026-11-11` |
| 8 | La etiqueta apunta a lo que se auditó | Física | `git rev-parse v0.9.0^{tree}` contra el árbol auditado | **Pendiente.** Se comprueba al crear la etiqueta, después de fusionar el PR #2; el resultado queda en la evidencia de la etiqueta |

**Observación abierta (menor).** La sección 4 de `CLAUDE.md` no lista `docker-compose.yml` ni los módulos de `services/` que se agregaron después. No impide fijar `v0.9.0`; se corrige con una solicitud de cambio posterior y se vuelve a comprobar en la auditoría de `1.0.0`.

**Lo que esta auditoría no cubre.** El RNF-01 (pase de lista de 40 alumnos en 3 minutos) no se ha cronometrado con personas y sigue sin verificarse. Los comandos los ejecutó el asistente de IA sobre una copia del repositorio en la máquina del proyecto; la decisión de fusionar y de etiquetar la toma el responsable del repositorio.

### Registro de la candidata `v1.0.0-rc.1` (16/11/2026)

**Qué se verificó.** El commit `33c81f5` de la rama `feature/rnf-08-despliegue`, que tiene el código final de los bloques B2 a B7 (los commits posteriores de esa rama solo agregan `scripts/demo.ps1`, que no entra a la imagen, y documentación). Se verificó en la pila real `control_asistencia_prod`, levantada con `docker-compose.prod.yml` en el equipo del proyecto (Windows 11, Docker 29.8.1, Compose v5.5.1), en `http://localhost` y con `DJANGO_HTTPS=0`, que es la demostración local decidida como hosting (E5). El líder aprobó la etiqueta el mismo día (ver «Etiqueta», al final de este registro).

**Lista de verificación de [DESPLIEGUE.md](DESPLIEGUE.md), sección 6**

| # | Punto | Resultado | Evidencia |
|---|---|---|---|
| 1 | `up -d --build` desde cero deja los tres servicios sanos | **Pasa** | Una pila nueva con el código final levantó en 42 s y la pila real en 26 s: `db` y `web` sanos (`healthy`) y `proxy` arriba. `migrate` aplicó las migraciones 0001 a 0004 dentro del contenedor: `mysqlclient 2.3.0` compiló en `python:3.11-slim` (Debian 13) y se autentica contra MySQL 8.0.46 con `caching_sha2_password` (riesgo R3 cerrado) |
| 2 | Docente y administrador entran; periodo, grupo y solo lectura (RF-17) | **Pasa** | Recorrido por HTTP a través del proxy, con sesión y token CSRF reales: 29 de 29 comprobaciones. El administrador llega a su panel, crea el periodo 2027-2 y lo activa con el botón de su fila; el docente crea un grupo, importa 5 alumnos por CSV y programa 4 sesiones; con su periodo inactivo el pase de lista se rechaza y la página avisa «solo lectura»; al reactivarlo vuelve a guardarse. En el navegador integrado: el docente llega a «Inicio» y el administrador a «Panel de administración», cada uno con su menú |
| 3 | Cargan Bootstrap, `estilo.css` y `admin.css` con `DEBUG=0` | **Pasa** | En el navegador: Bootstrap 5.3.3 del CDN (1 298 reglas, con `integrity`), `estilo.fbbd6d027a0e.css` (222 reglas) y, en el admin, cinco hojas con huella, entre ellas `asistencia/admin.42609df61b19.css`; ningún recurso con error ni mensajes en la consola. `pase_de_lista.2a0fed160107.js` carga y bloquea las casillas |
| 4 | Pase de lista y corrección: fila en la bitácora | **Pasa** | Pase de 5 registros con un envío y corrección de ausente a justificado. La base tiene la fila de `bitacora_cambio` (autor `docente1@asistencia.test`, `ausente` → `justificado`), escrita por el disparador con el usuario `asistencia@%`, que solo tiene permisos sobre su base |
| 5 | Justificante, `down` (sin `-v`), `up -d` y sigue descargándose | **Pasa** | Tras `down`, 0 contenedores y los 4 volúmenes intactos; tras `up -d`, el PDF se descarga por la vista idéntico byte a byte. Sin sesión redirige al acceso y otro docente recibe 404 (RNF-04) |
| 6 | Una URL directa a `/media/...` responde 404 | **Pasa** | `/media/`, `/media/justificantes/` y un archivo: 404 con `Server: Caddy` y 0 bytes. El registro de accesos de `web` no tiene ninguna petición a `/media` |
| 7 | Una excepción muestra la página 500 propia | **Pasa** | Con `db` detenido, la pantalla de acceso abre (200) e iniciar sesión responde 500 con la página «Error del servidor · Control de asistencia», sin detalles del error |
| 8 | El 3306 no está publicado | **Pasa** | `docker port`: `db` y `web` sin puertos; solo `proxy` publica 80 y 443 |
| 9 | Respaldo, restauración como `root`, disparador y `UPDATE` con `ROLLBACK` | **Pasa** | `scripts/respaldo.sh` (sin terminal) y `scripts/respaldo.ps1` (PowerShell 5.1) generan los dos archivos. `scripts/probar_restauracion.sh`: las 8 tablas coinciden (usuario 3, periodo 3, grupo 4, alumno 50, inscripción 60, sesión 8, asistencia 20, bitácora 2), el disparador existe con su dueño y el `UPDATE` escribe 1 fila en la bitácora, deshecha con `ROLLBACK`. Además se restauró de verdad sobre la base y sobre `media/` con los comandos del README, y la aplicación siguió funcionando |
| 10 | `check --deploy` solo con `W005`, `W008` y `W021`, justificadas (texto ajustado el 16/11/2026) | **Pasa** | Dentro del contenedor, con `DJANGO_HTTPS=1`: `W005`, `W008` y `W021`, los tres justificados en el README. Como está la demostración (`DJANGO_HTTPS=0`): `W004`, `W008`, `W012` y `W016`, que son los de un sitio sin HTTPS. Ver la observación 1 |
| 11 | Suite completa sin `DJANGO_STATIC_MANIFEST` y `collectstatic` al construir | **Pasa** | `Ran 683 tests in 992.973s`, `OK`, sobre el commit `33c81f5`. Al construir: `130 static files copied, 390 post-processed`; sin la clave desechable, la construcción aborta con `ImproperlyConfigured` |
| 12 | `git status` limpio, sin `.env*` ni `respaldos/`, y README actualizado | **Pasa** | `git check-ignore -v .env.prod` muestra `.gitignore:4`; `git ls-files` solo trae `.env.example` y `.env.prod.example`; `respaldos/` y `staticfiles/` quedan ignorados. `git status --porcelain` salió vacío antes de fusionar y de etiquetar |

**Criterios de salida de la sección 3**

| # | Estado al 16/11/2026 | Nota |
|---|---|---|
| S1 | Cumplido | Los 12 puntos de arriba |
| S2 | Cumplido | `Ran 683 tests in 992.973s`, `OK`: las 651 de `main` más 32 nuevas (configuración, estáticos y `seed_demo`) |
| S3 | Cumplido | Punto 9. El error 1449 se reprodujo con un volcado cuyo dueño no existe, y la prueba de restauración lo detecta y falla |
| S4 | Cumplido | Con `DJANGO_HTTPS=1` quedan exactamente `W005`, `W008` y `W021`, los que admite el criterio ajustado (observación 1) |
| S5 | Cumplido | Puntos 6 y 8 |
| S6 | Cumplido después de `rc.1` | Los dos manuales entran a `main` con la fusión de la fase I; la etiqueta `rc.1` se puso antes y no los incluye |
| S7 | Simulado (decisión del 16/11) | Los pasos de los puntos 2, 4 y 5 se repitieron en la pila real, como pide el criterio |
| S8 | Pendiente | Auditoría del 26/11/2026 |
| S9 | Cumplido | Punto 12 |
| S10 | Cumplido | Todas las líneas de `requirements.txt` llevan `==`; dentro de la imagen, `pip check` no encuentra conflictos y `pip freeze` devuelve exactamente las 13 versiones fijadas para Linux |

**Observaciones**

1. **`check --deploy` (S4 y punto 10).** El criterio admite solo `W008`, pero se escribió sin medir. Al activar HSTS con `DJANGO_HTTPS=1` aparecen `W005` (`SECURE_HSTS_INCLUDE_SUBDOMAINS`) y `W021` (`SECURE_HSTS_PRELOAD`). Se dejaron apagados a propósito y están justificados en el README. La alternativa era activar los dos ajustes. **Resuelta el 16/11/2026:** el líder aceptó los tres avisos, y el texto de S4 y el del punto 10 de la lista de verificación se ajustaron; los dos ajustes de HSTS siguen apagados.
2. **Restauración de prueba.** Al restaurar como `root` en una base temporal, el `UPDATE` falla con el error 1142 (`TRIGGER command denied`), no con el 1449: el dueño del disparador no tiene permisos sobre esa base. `scripts/probar_restauracion.sh` se los da durante la prueba y se los quita al terminar.
3. **Errores del servidor sin registro.** Con `DEBUG=0`, Django no escribe los errores 500 en la salida del contenedor: en los registros de `web` solo queda la línea de acceso con el código 500. No impide ningún criterio; corregirlo es un cambio de código y necesita su solicitud de cambio.
4. **El proxy solo atiende el nombre de `DOMINIO`.** Entrar por `http://127.0.0.1` da una página en blanco; el README lo avisa.

**Lo que este registro no cubre.** El despliegue con un dominio real y HTTPS no se ejecutó: solo se comprobó que Caddy interpreta ese valor de `DOMINIO` como HTTPS automático y que, con `DJANGO_HTTPS=1` y la cabecera del proxy, la aplicación manda HSTS de 3600 s y cookies seguras. La tarea programada del respaldo (cron o Programador de tareas) no se instaló. `scripts/respaldo.sh` y `scripts/probar_restauracion.sh` se ejecutaron en Git Bash sobre Windows, no en un servidor Linux. Las comprobaciones en el navegador se hicieron leyendo el contenido de las páginas, sin capturas de pantalla. Los comandos los ejecutó el asistente de IA en el equipo del proyecto; la decisión de etiquetar la toma el líder.

**Etiqueta.** `v1.0.0-rc.1` es una etiqueta anotada sobre el commit `1fc9d7d` de `main`, creada y publicada el 16/11/2026 con la aprobación del líder.

| Comprobación | Comando | Resultado |
|---|---|---|
| La etiqueta apunta a la punta de `main` | `git ls-remote --tags origin` y `git ls-remote --heads origin main` | `v1.0.0-rc.1^{}` y `main` dan `1fc9d7d` |
| El árbol etiquetado es el que se verificó | `git rev-parse v1.0.0-rc.1^{tree}` contra el árbol de la punta de la rama verificada (`90786b3`) | Los dos dan `08e3333b50e7153d897fde860faf8868496b4e41` |
| Ningún archivo sensible versionado | `git ls-tree -r --name-only` filtrado por `.env`, `respaldos/`, `media/` y `*.sql` | Solo `.env.example` y `.env.prod.example` |
| Versiones exactas | Líneas de `requirements.txt` sin `==` | 0 |

**Cómo entró la rama a `main`.** La rama `feature/rnf-08-despliegue` se fusionó desde la línea de comandos, con commit de fusión (`1fc9d7d`, que avanza `main` desde `d1042f4` sin reescribir nada), a petición expresa del líder. Es una excepción a la regla de que una rama entra a `main` por pull request ([gestion_configuracion.md](gestion_configuracion.md), sección 6): no hay pull request en GitHub para esta fusión, y el mensaje del commit lo dice. La revisión de la lista de la sección 7 queda cubierta por este registro.

**Lo que la etiqueta no cambia.** Cuando se etiquetó, la observación 1 (criterio S4) seguía abierta; el líder la resolvió después, el mismo 16/11/2026, sin cambiar código. El `CHANGELOG` conserva la sección `[Unreleased]`: la sección `[1.0.0]` se escribe al liberar la versión final. El commit que agrega esta nota es posterior a la etiqueta y solo toca documentación.

### Registro de la candidata `v1.0.0-rc.2` (17/11/2026)

**Qué se verificó.** El commit `500bf6b` de `main` (árbol `4fe3e1c38ae9aacf944f0ff26ea4ccdcdfbf12f5`), que es la fusión del pull request #9 con los dos manuales. Respecto a `v1.0.0-rc.1` cambian 19 archivos, todos de documentación: los dos manuales y sus 10 capturas, el README, el `CHANGELOG`, `CLAUDE.md` y cinco documentos de `docs/` (`git diff --name-only v1.0.0-rc.1 500bf6b`). Ninguno es código, prueba ni archivo de la pila, y ninguno entra a la imagen: `.dockerignore` excluye `docs` y `*.md`. Por eso la candidata se re-verificó con una prueba de humo de los puntos 1, 2, 4 y 6 de la lista de verificación, en lugar de repetir los doce.

| Punto | Resultado | Evidencia |
|---|---|---|
| Imagen | **La misma que en `rc.1`** | Reconstruida desde `main`: Docker tomó de su caché los 8 pasos de la construcción. El contenido es idéntico archivo por archivo: 8512 archivos de `/app` y `/opt/venv` (sin `media/`) con la misma huella `d1f189ab588086a9`, en el contenedor que corre desde `rc.1` y en uno nuevo de la imagen de hoy. Docker muestra identificadores distintos para la imagen según desde qué proyecto se construyó, pero el contenido no cambia |
| 1 | **Pasa** | Una pila desechable desde cero (volúmenes nuevos, eliminados al terminar) quedó con los tres servicios sanos; `migrate` aplicó las migraciones 0001 a 0004 y creó el disparador con el usuario `asistencia@%`; `db` y `web` sin puertos publicados. La pila real se reconstruyó con `up -d --build` y siguió sana |
| 2 | **Pasa** | Recorrido por HTTP a través del proxy, igual al de `rc.1`: 29 de 29 comprobaciones. El administrador creó y activó el periodo 2028-1; con él activo, el grupo de 2026-2 quedó en solo lectura, y al reactivar 2026-2 el pase de lista volvió a guardarse |
| 4 | **Pasa** | Pase de lista de 5 alumnos con un envío y corrección de ausente a justificado: la fila nueva de `bitacora_cambio` tiene como autor a `docente1@asistencia.test` y la escribió el disparador con el usuario `asistencia@%` |
| 6 | **Pasa** | `/media/`, `/media/justificantes/` y un archivo: 404 desde Caddy; ninguna petición a `/media` llegó a Django |

**Lo que no se repitió y por qué.** Los puntos 3, 5, 7, 8, 9, 10, 11 y 12 dependen del código, de la imagen o de la configuración de la pila, y ninguno de los tres cambió: su resultado del registro de `rc.1` sigue valiendo. **La suite completa no se corrió**: ningún archivo de `asistencia/`, `config/` ni `requirements.txt` cambió desde `rc.1`, donde pasó (`Ran 683 tests`, `OK`). El punto 12 (`git status` limpio y ningún archivo sensible versionado) se vuelve a comprobar al poner la etiqueta.

**Criterios de salida al 17/11/2026**

| # | Estado | Cambio respecto a `rc.1` |
|---|---|---|
| S1 a S5, S9 y S10 | Cumplidos | Ninguno: el código y la imagen son los mismos |
| S6 | **Cumplido** | `docs/manual_usuario.md` y `docs/manual_administrador.md` existen y el README los enlaza (línea 10) |
| S7 | Simulado (decisión del 16/11) | Los pasos de los puntos 2, 4 y 5 se repitieron otra vez en la pila real |
| S8 | Pendiente | Auditoría del 26/11/2026 (plantilla al final de esta sección) |

**Criterios de entrada.** Con S6, los seis criterios de entrada (E1 a E6) están cumplidos: E5 y E6 desde el 16/11/2026. Por eso se abre la rama `release/v1.0.0`, que según [gestion_configuracion.md](gestion_configuracion.md), sección 6, solo ajusta el `CHANGELOG`, la documentación de la liberación y el estado en `CLAUDE.md`. El proceso la fusiona después de la auditoría; **el líder la fusionó el mismo 17/11/2026** (pull request #10), así que desde ese día el `CHANGELOG` de `main` muestra `## [1.0.0] - 2026-11-27` antes de que exista la etiqueta: su enlace del pie no abre hasta que se publique `v1.0.0`, y si la versión sale otro día hay que corregir la fecha con otro pull request.

**Etiqueta.** `v1.0.0-rc.2` es una etiqueta anotada sobre el commit `500bf6b` de `main`, creada y publicada el 17/11/2026 con el visto bueno del líder.

| Comprobación | Comando | Resultado |
|---|---|---|
| La etiqueta apunta al commit verificado, que era la punta de `main` al crearla | `git ls-remote --tags origin` | `v1.0.0-rc.2^{}` da `500bf6b`. Minutos después entraron a `main` los pull requests #10 y #11 (`f244c9a`), solo de documentación |
| El árbol etiquetado es el que se verificó | `git rev-parse v1.0.0-rc.2^{tree}` | `4fe3e1c38ae9aacf944f0ff26ea4ccdcdfbf12f5`, el mismo de la verificación |
| Ningún archivo sensible versionado | `git ls-tree -r --name-only 500bf6b` filtrado por `.env`, `respaldos/`, `media/` y `*.sql` | Solo `.env.example` y `.env.prod.example` |
| Versiones exactas | Líneas de `requirements.txt` sin `==` | 0 |

`main` entró por pull request (#9), sin excepciones al proceso. El commit que agrega esta nota es posterior a la etiqueta y solo toca documentación.

### Registro de la auditoría de `v1.0.0` (17/11/2026)

**Qué se audita.** La punta de `main` el día de la auditoría (`release/v1.0.0` ya se fusionó el 17/11/2026, pull request #10). **Se adelantó al 17/11/2026** (estaba prevista para el 26/11) y se hizo sobre el commit `5548a56` (árbol `891680c52b2d3027fad8dbfe7da76fc45ddc4297`). Si antes de poner la etiqueta `main` cambia en algo que no sea documentación, se repite. Si entre `rc.2` y ese commit cambió algún archivo que no sea documentación, la auditoría no sigue: hace falta una candidata nueva (`rc.3`) con su verificación.

Comandos, en una terminal de Git Bash en la carpeta del proyecto, con `main` al día (`git fetch origin` y `git switch main` y `git pull`), MySQL de desarrollo arriba y la pila de producción levantada:

```bash
# 0. Qué cambió desde la última candidata (solo debe salir documentación)
git diff --name-only v1.0.0-rc.2 HEAD | grep -vE '\.md$|^docs/' || echo "solo documentación"

# 1. Suite completa en una base MySQL 8 limpia (tarda de 9 a 17 minutos)
python manage.py test --noinput

# 2. Cada requisito de prioridad Alta tiene al menos un archivo de pruebas
for rf in 01 02 03 04 06 08 09 10 11 13 14; do printf 'RF-%s: ' "$rf"; grep -lE "RF-$rf" asistencia/tests/*.py | wc -l; done

# 4. Sin cambios en la copia de trabajo
git status --porcelain

# 5. Lo que documenta CLAUDE.md, sección 4, está versionado
for f in manage.py config asistencia/models.py asistencia/migrations/0001_initial.py asistencia/migrations/0002_trigger_bitacora.py asistencia/migrations/0003_periodo.py asistencia/migrations/0004_usuario_aprobado.py asistencia/backends.py asistencia/permissions.py asistencia/forms.py asistencia/admin.py asistencia/services asistencia/views asistencia/templates/asistencia asistencia/templatetags/diseno.py asistencia/static asistencia/management/commands/seed_demo.py asistencia/tests docker scripts docs/manual_usuario.md docs/manual_administrador.md docs/informe_pruebas.md docs/seguimiento_semanal.md docs/DESPLIEGUE.md docs/gestion_configuracion.md docs/plan_liberacion.md docs/cambios CHANGELOG.md Dockerfile docker-compose.prod.yml docker-compose.yml requirements.txt .env.example .env.prod.example .dockerignore .gitattributes .gitignore README.md; do [ -n "$(git ls-files -- "$f")" ] || echo "falta: $f"; done; echo "fin"

# 6. Ningún archivo sensible versionado
git check-ignore -v .env .env.prod respaldos/x media/x dump.sql.gz
git ls-files | grep -iE '(^|/)\.env|respaldos/|^media/|\.sql(\.gz)?$'

# 7. El número de la versión coincide con el del CHANGELOG
grep -m1 -E '^## \[[0-9]' CHANGELOG.md

# 10. Versiones exactas (debe dar 0)
tr -d '\r' < requirements.txt | grep -v '^#' | grep -v '^$' | grep -vc '=='

# 11. La imagen lleva el mismo código que la última candidata (sin contar los saltos de línea)
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec -T web sh -c 'cd /app && find asistencia config docker manage.py requirements.txt -type f | sort | while read f; do printf "%s %s\n" "$(tr -d "\r" < "$f" | sha256sum | cut -c1-64)" "$f"; done' > /tmp/imagen.txt
while read h f; do [ "$h" = "$(git show "v1.0.0-rc.2:$f" 2>/dev/null | tr -d '\r' | sha256sum | cut -c1-64)" ] || echo "difiere: $f"; done < /tmp/imagen.txt; echo "fin"

# 8 y 9. Después de crear la etiqueta: apunta al commit auditado y a su árbol
git rev-parse 'v1.0.0^{commit}' 'v1.0.0^{tree}' HEAD 'HEAD^{tree}'
```

| # | Comprobación | Tipo | Resultado esperado | Resultado |
|---|---|---|---|---|
| 0 | Solo documentación desde `rc.2` | Física | `solo documentación` | **Pasa.** `solo documentación` |
| 1 | La suite completa pasa en una base MySQL 8 limpia | Funcional | `Ran N tests … OK`, con N mayor o igual que 683 | **Pasa.** `Ran 683 tests in 1681.307s`, `OK` |
| 2 | Cada requisito de prioridad Alta tiene prueba | Funcional | Ningún requisito con 0 archivos | **Pasa.** RF-09, 10, 11 y 14 con 2 archivos; RF-01, 02, 03, 04, 06, 08 y 13 con 1. Es trazabilidad por nombre, no cobertura |
| 3 | Los hallazgos abiertos están revisados | Funcional | Solo el H-03 abierto, opcional por la sección 1 de este plan | **Pasa.** H-01 y H-02 corregidos; el H-03 (importar un CSV de 500 filas tarda unos 3.8 s) sigue abierto y es opcional |
| 4 | `git status` sin cambios | Física | Salida vacía | **Pasa.** 0 líneas |
| 5 | Lo documentado en `CLAUDE.md`, sección 4, está versionado | Física | Solo `fin`, sin ninguna línea `falta:` | **Pasa.** Solo `fin` |
| 6 | Ningún `.env*`, `media/`, `respaldos/` ni `*.sql.gz` versionado | Física | Las cinco rutas ignoradas; versionados solo `.env.example` y `.env.prod.example` | **Pasa.** Las cinco ignoradas (líneas 3, 4, 14, 15 y 17 de `.gitignore`) y solo los dos ejemplos versionados |
| 7 | El número de la etiqueta coincide con el del `CHANGELOG` | Física | `## [1.0.0] - 2026-11-27` (o la fecha real de la etiqueta) | **Pasa.** La auditoría encontró `2026-11-27`; el líder adelantó la liberación al 17/11/2026 y el encabezado se corrigió a `## [1.0.0] - 2026-11-17` en el mismo pull request que este registro. Se vuelve a comprobar antes de etiquetar |
| 8 | La etiqueta apunta al commit auditado | Física | `v1.0.0^{commit}` igual a `HEAD` | *Se comprueba al crear la etiqueta* |
| 9 | El árbol etiquetado es el auditado | Física | `v1.0.0^{tree}` igual a `HEAD^{tree}` | *Se comprueba al crear la etiqueta* |
| 10 | Versiones exactas | Física | `0` | **Pasa.** `0` |
| 11 | La imagen lleva el código verificado | Física | Solo `fin`, sin líneas `difiere:` | **Pasa, con observación.** Los 126 archivos del repositorio que lleva la imagen son iguales a los de `v1.0.0-rc.2`; las dependencias salen de la misma capa en caché; los estáticos conservan los nombres con huella de `rc.1` (`estilo.fbbd6d027a0e.css`, `admin.42609df61b19.css`, `pase_de_lista.2a0fed160107.js`). Ver la observación de abajo |
| S1 a S10 | Criterios de salida de la sección 3 | Ambos | Todos cumplidos (S7 simulado por decisión del líder) | **Cumplidos.** S1 a S5, S9 y S10 en `rc.1`, S6 en `rc.2`, S7 simulado y S8 es esta auditoría |

**Observación sobre la comprobación 11.** La plantilla original comparaba la imagen con una huella fija (`d1f189ab588086a9`) y hoy dio otra (`efdc81a48a501f8b`), con 2 de los 8 pasos de la construcción rehechos. La causa no es el código, sino los saltos de línea de la copia de trabajo: con `core.autocrlf` (Windows), Git escribe los archivos con CRLF, y la imagen copia los archivos tal como están en disco. Varios archivos que se crearon el 16/11 con LF (`config/settings.py`, `seed_demo.py`, tres archivos de pruebas, `docker/healthcheck.py`) volvieron a escribirse con CRLF al poner esta copia en `main`. Los 126 archivos del repositorio coinciden con `rc.2` en cuanto se ignoran los retornos de carro. Por eso la comprobación 11 ahora compara archivo por archivo contra la última candidata, sin contar los saltos de línea, en lugar de una huella fija. Python, pip y Django tratan igual LF y CRLF, y `entrypoint.sh` y el `Caddyfile` ya tienen LF fijo en `.gitattributes`, así que el comportamiento no cambia. Lo que sí deja ver es que una imagen construida en otro equipo no es idéntica byte a byte (saltos de línea y archivos que genera la instalación de dependencias), aunque lleve el mismo código y las mismas versiones. Fijar LF para todos los archivos en `.gitattributes` lo resolvería; es un cambio de configuración y necesitaría su solicitud de cambio y una candidata nueva.

**Lo que esta auditoría no cubre.** La auditoría la ejecutó el asistente de IA en el equipo del proyecto, sobre `main` y la pila de producción local; la decisión de etiquetar la toma el líder. El despliegue con dominio y HTTPS sigue sin ejecutarse y la tarea programada del respaldo sigue sin instalarse, como en los registros de las candidatas.

**Pasos para liberar, en orden:** (1) fusionar `release/v1.0.0` a `main` (**hecho el 17/11/2026**, pull request #10; si la fecha de la versión cambia, corregir el encabezado del `CHANGELOG` con un pull request); (2) correr los comandos de arriba sobre `main` y llenar la columna «Resultado»; (3) dictamen go/no-go del líder (sección 11); (4) con go, `git tag -a v1.0.0 <commit auditado> -m "Versión 1.0.0"` y `git push origin v1.0.0`; (5) correr las comprobaciones 8 y 9; (6) publicar la versión en GitHub con las notas de la sección 9; (7) marcar la fase J en `CLAUDE.md` (sección 12) y mover la tarjeta J de Trello a «Hecho». Una etiqueta publicada no se mueve: un error se corrige con `1.0.1`.


## 11. Dictamen go/no-go

**Fecha del dictamen:** 11/11/2026, actualizado el 17/11/2026 con la candidata `rc.2`. **Decide:** líder de proyecto (CCB).

| Decisión | Dictamen | Razón |
|---|---|---|
| Fijar la línea base `v0.9.0` | **Go** | La suite completa pasa; todos los requisitos de prioridad Alta tienen prueba y no hay hallazgos críticos ni mayores. No es una versión de producción y se declara así en el `CHANGELOG` |
| Etiquetar la candidata `v1.0.0-rc.1` (16/11/2026) | **Go** | Los puntos técnicos pasaron en la pila real (sección 10) y el líder aprobó la etiqueta. La observación sobre `check --deploy` (S4) quedó resuelta ese mismo día: se aceptan `W005`, `W008` y `W021` |
| Etiquetar la candidata `v1.0.0-rc.2` (17/11/2026) | **Go** (visto bueno del líder el mismo día) | Mismo código e imagen que `rc.1` más los dos manuales; la prueba de humo de los puntos 1, 2, 4 y 6 pasó en la pila real y S6 queda cumplido (sección 10) |
| Liberar `v1.0.0` | **Go** (17/11/2026, decisión del líder) | Al 11/11/2026 no se cumplían E5 ni E6 y no existían la fase J ni los manuales. Al 17/11/2026 la auditoría (S8) pasó sobre `5548a56` y todos los criterios de salida están cumplidos (S7 simulado). El líder adelantó la liberación del 27/11 al 17/11/2026 «para ya terminar»; la entrega a la profesora sigue siendo el 27/11 |

**Condiciones para pasar a go** (previsto para el 26/11/2026; la auditoría se adelantó al 17/11): los diez criterios de salida (S1 a S10) cumplidos y ninguna condición de no-go inmediato. Mientras tanto, el dictamen se actualiza en cada candidata (`rc.N`).

**Limitación.** El proyecto es individual: quien lo programa también ejerce el comité de control de cambios y decide el go. No se puede crear un comité de varias personas; se compensaba con dos condiciones: que el criterio S7 lo ejecutara otra persona y que la profesora firmara el acta de aceptación antes del go final. El 16/11/2026 Victo decidió, por ser un proyecto escolar, que el S7 se simule ([aceptacion_simulada.md](aceptacion_simulada.md)) y que el acta sea opcional; el go lo sigue decidiendo una sola persona.
