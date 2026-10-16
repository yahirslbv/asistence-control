# Seguimiento semanal del proyecto

Sistema de Control de Asistencia · UABC, FCITEC · Administración de Proyectos de Software.
**Corte: jueves 15/10/2026 (semana S3).** Fecha límite de entrega: viernes 27/11/2026.

| Recurso | Enlace |
|---|---|
| Repositorio | <https://github.com/yahirslbv/asistence-control> |
| Tablero Trello | <https://trello.com/b/1CRpoq6E/control-de-asistencia-cronograma> |
| Fuente de verdad del proyecto | [CLAUDE.md](../CLAUDE.md) (requisitos, reglas, estado y decisiones) |
| Informe de pruebas de la fase H | [informe_pruebas.md](informe_pruebas.md) |
| Plan técnico de despliegue (fase J) | [DESPLIEGUE.md](DESPLIEGUE.md) |
| Instalación y uso | [README.md](../README.md) |

Este documento sirve para revisar los avances contra las actividades que el cronograma asigna a cada semana. Las cifras salen del historial de Git y de las pruebas, no de estimaciones. Lo que no se verificó aparece como tal.

## 1. Resumen

- **Estado:** las actividades A a H están terminadas, la I (manuales) está en curso y la J (despliegue y entrega) está por hacer.
- **Adelanto:** el cronograma prevé terminar la H el 20/11/2026. Quedó terminada el 15/10/2026, 36 días antes.
- **Calidad:** 406 pruebas automáticas en verde. El peor caso medido de consulta con 50 alumnos fue de 570 ms contra el límite de 3 s (RNF-07).
- **Requisitos:** los 16 requisitos funcionales están implementados y probados. Quedan por hacer el respaldo diario (RNF-08) y los manuales (parte del RNF-09).
- **Pendiente de decisión:** hosting, mínimo de asistencia de 80 %, respaldo de `media/` y tres hallazgos menores de la fase H (sección 8).

### Avance contra el cronograma

| Actividad | Ventana prevista | Fin previsto | Terminada el | Adelanto |
|---|---|---|---|---|
| A · Análisis y validación de requisitos | S1 (28/09–02/10) | 02/10 | según el tablero | no verificado en el repositorio |
| B · Diseño de la base de datos | S2 (05–09/10) | 09/10 | según el tablero | no verificado en el repositorio |
| C · Diseño de interfaz y prototipo | S2 (05–09/10) | 09/10 | según el tablero | no verificado en el repositorio |
| D · Entorno y autenticación | S3 (12–16/10) | 16/10 | 13/10 | 3 días |
| E · Grupos y sesiones | S4–S5 (19–30/10) | 30/10 | 13/10 | 17 días |
| F · Asistencia | S6–S7 (02–13/11) | 13/11 | 13/10 (el justificante, el 15/10) | 31 días |
| G · Reportes | S6 (02–06/11) | 06/11 | 14/10 | 23 días |
| H · Integración y pruebas | S8 (16–20/11) | 20/11 | 15/10 | 36 días |
| I · Manuales y documentación | S6 (02–06/11), holgura hasta S8 | 20/11 | en curso | |
| J · Despliegue y entrega | S9 (23–27/11) | 27/11 | por hacer | |

El código fuente tiene 63 commits entre el 13 y el 15/10/2026. Las actividades A, B y C vienen de la documentación previa (requisitos, modelo entidad-relación, prototipo de pantallas y cronograma) y su estado es el que marca el tablero.

## 2. Cómo revisar el avance

Con el repositorio clonado y Docker abierto (los pasos completos están en el [README](../README.md)):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
python manage.py test --noinput
```

- `seed_demo` crea 1 administrador, 2 docentes, 2 grupos y 40 alumnos. La contraseña de las cuentas de demostración está en `asistencia/management/commands/seed_demo.py`.
- La suite completa debe terminar con `Ran 406 tests` y `OK`. Tardó unos siete minutos en la última corrida.
- La carpeta [docs](.) contiene este seguimiento y el informe de pruebas.

## 3. Estado por semana

### S1 · 28/09 al 02/10 · A · Análisis y validación de requisitos
- **Responsable:** analista (líder de proyecto). **Ruta crítica:** sí.
- **Resultado esperado:** documento de requisitos aprobado.
- **Estado:** hecha, según el tablero.
- **Evidencia en el repositorio:** la sección 6 de [CLAUDE.md](../CLAUDE.md) recoge los 16 requisitos funcionales con su prioridad y la sección 7 los requisitos no funcionales. El texto literal de RF-01 y RF-02 no se recuperó y se confirmará con el documento de la Actividad 5.

### S2 · 05/10 al 09/10 · B · Diseño de la base de datos · C · Diseño de interfaz y prototipo
- **B.** Responsable: desarrollador de base de datos. Ruta crítica: sí. Resultado esperado: modelo entidad-relación y script de la base de datos. **Estado:** hecha, según el tablero. **Evidencia:** el diseño de 7 tablas del Apéndice A de CLAUDE.md, implementado en `asistencia/models.py` y en la migración `0001_initial`.
- **C.** Responsable: diseñador de interfaz. Ruta crítica: no (holgura de 1 semana). Resultado esperado: prototipo navegable validado con los docentes. **Estado:** hecha, según el tablero. **Evidencia:** las 4 pantallas de baja fidelidad de la sección 10 de CLAUDE.md, que son las que se implementaron.

### S3 · 12/10 al 16/10 · D · Configuración del entorno y módulo de autenticación
- **Responsable:** desarrollador backend. **Ruta crítica:** sí, sin holgura.
- **Resultado esperado:** repositorio configurado e inicio de sesión funcionando.
- **Estado:** **terminada el 13/10**, tres días antes del cierre.

| Subtarea | Commit |
|---|---|
| Repositorio Git con `.gitignore` y README | `c0000bd` |
| Proyecto Django y MySQL 8 en Docker, con configuración por `.env` | `afe4296` |
| Modelos del Apéndice A y migración 0001, con solo los índices que aportan (RNF-05, RNF-07) | `a58361a` |
| Disparador de la bitácora de correcciones, migración 0002 (RNF-06) | `d1a4ed8` |
| Inicio de sesión con correo y opciones según el rol (RF-01, RF-02) | `42ef692` |
| Comando `seed_demo` | `6914857` |
| Pruebas de login, registro duplicado y bitácora | `100678a` |
| Cierre de la fase | `47411dc` |
| Publicación del repositorio en GitHub | 15/10/2026 |

Extra de esta semana: **RF-16 · alta de usuarios con rol desde el admin de Django**. Primera versión el 13/10 (`87c2fb4`); reglas de rol, bajas y protección del último administrador el 15/10 (`ac77eef`, `4cf82d3`, `229d225`). El rol decide `is_staff` y los permisos, los usuarios no se borran sino que se desactivan, y no se puede desactivar ni quitar el rol al último administrador activo. 38 pruebas en `test_usuarios.py`.

### S4 y S5 · 19/10 al 30/10 · E · Módulo de grupos y sesiones
- **Responsable:** desarrollador backend. **Ruta crítica:** sí, sin holgura.
- **Resultado esperado:** alta de grupos, carga de listas y programación de sesiones funcionando.
- **Estado:** **terminada el 13/10**, 17 días antes del cierre previsto.

| Requisito | Qué hace | Commit |
|---|---|---|
| RNF-04 | Mixins de acceso: un recurso ajeno responde 404 | `ab7dbbb` |
| RF-03 | Alta, edición y baja de grupos, con confirmación | `6f09cc7` |
| RF-04 | Carga de la lista de alumnos desde CSV, con errores por fila | `f2ae8ba` |
| RF-05 | Inscribir y dar de baja alumnos de forma individual | `6842506` |
| RF-06 | Generar sesiones desde horario y periodo, con calendario | `4d096dd` |
| RF-07 | Editar o cancelar una sesión programada | `26935e0` |
| Cierre | Fase E terminada | `61904b5` |
| RNF-04 | Páginas 403 y 404 propias (se hicieron justo después del cierre, por eso el historial de la sección 7 las cuenta en F) | `28b5de0` |

Pruebas: `test_grupos` (14), `test_importar_alumnos` (19), `test_inscripciones` (11), `test_generar_sesiones` (25), `test_editar_sesiones` (15), `test_aislamiento` (9) y `test_errores` (4).

### S6 y S7 · 02/11 al 13/11 · F · Módulo de asistencia (la de mayor riesgo)
- **Responsable:** desarrollador frontend. **Ruta crítica:** sí, sin holgura.
- **Resultado esperado:** pase de lista funcionando con validaciones y bitácora de correcciones.
- **Estado:** **terminada el 13/10**, 31 días antes del cierre previsto.

| Requisito | Qué hace | Commit |
|---|---|---|
| RF-08, RF-09 | Pase de lista con envío atómico y sin duplicados; pantalla y sesiones de hoy | `55f188c`, `a8aca57` |
| RF-09 | Pruebas de doble envío y de envíos simultáneos con hilos reales contra MySQL | `f629994` |
| RF-10 | Consulta única de sesiones sin pase de lista o con el pase incompleto, y alerta | `4c0cc31`, `05c1e3d` |
| RF-11 | Corrección con bitácora visible y admin de solo lectura | `fc74cfa` |
| RF-08 | El pase de lista solo se permite hasta hoy; una sesión futura muestra un mensaje | `0a41d5a` |
| RNF-02 | Barra fija «Guardar» en el teléfono | `d736c56` |
| Cierre | Fase F terminada | `fae4f9c` |

Pruebas: `test_pase_de_lista` (23), `test_correccion` (28), `test_pendientes` (33), `test_sesion_futura` (10), `test_integridad` (5) y `test_bitacora_admin` (2).

Extra: **RF-12 · justificantes de asistencia**, terminado el 15/10 (`3a3c3ea`, `3ec450e`, `e9d2010`). PDF, JPG y PNG de hasta 5 MB; se valida la extensión y la firma del contenido; el archivo se guarda con nombre aleatorio, solo se descarga por la vista y se borra al quitarlo o al eliminar el grupo. 37 pruebas en `test_justificantes.py`.

### S6 · 02/11 al 06/11 · G · Módulo de reportes
- **Responsable:** desarrollador backend. **Ruta crítica:** no (holgura hasta S7).
- **Resultado esperado:** reportes por grupo y por alumno exportables.
- **Estado:** **terminada el 14/10**, 23 días antes del cierre previsto.

| Requisito | Qué hace | Commit |
|---|---|---|
| RF-13, RF-14 | Porcentaje con enteros, truncado a un decimal, y marca de bajo el mínimo | `dfda717` |
| RF-13, RF-14 | Pantallas de reportes por periodo, grupo y alumno | `4f7f7b3` |
| RF-15 | Exportación a PDF y Excel, con texto escapado y celdas siempre como texto | `5303fe4`, `15c2cc4` |
| RNF-02 | Reportes legibles en 375 px | `d321d9f` |
| Cierre | Fase G terminada | `30c79a6` |

Pruebas: `test_reportes` (68) y `test_exportar` (34).

### S6 · 02/11 al 06/11 (holgura hasta S8) · I · Manuales y documentación
- **Responsable:** documentador. **Ruta crítica:** no.
- **Resultado esperado:** manual de usuario y manual de administrador terminados.
- **Estado:** **en curso.**
  - [x] README de instalación y uso (RNF-09).
  - [x] Este documento de seguimiento.
  - [ ] Manual de usuario.
  - [ ] Manual de administrador.
- **Observación:** conviene escribir los manuales ya. La fase H terminó y las pantallas no deberían cambiar.

### S8 · 16/11 al 20/11 · H · Integración y pruebas del sistema
- **Responsable:** responsable de pruebas. **Ruta crítica:** sí, sin holgura.
- **Resultado esperado:** informe de pruebas con los defectos corregidos.
- **Estado:** **terminada el 15/10**, 36 días antes del cierre previsto. Informe completo en [informe_pruebas.md](informe_pruebas.md).

| Actividad | Resultado | Commit |
|---|---|---|
| Flujos de extremo a extremo | 8 pruebas y un recorrido manual en el navegador: las cifras en pantalla coincidieron con las calculadas a mano | `2140ed3` |
| Matriz de acceso | 7 pruebas sobre las 25 rutas; sin accesos indebidos (RNF-04) | `71d609e` |
| Consultas que no crecen con los datos | 7 pruebas contra un N+1 (RNF-07) | `faa131d` |
| RNF-07 con 50 alumnos | 6 grupos × 50 alumnos × 48 sesiones (14 400 registros): peor caso 570 ms contra 3 s | |
| RNF-01 | 5 excepciones = 5 toques y un envío; botones de 48 px; no se cronometró con personas | |
| RNF-02 | Sin desbordes horizontales a 375, 768 y 1280 px | |
| Informe de pruebas | `docs/informe_pruebas.md` | `fee1cb2` |

Defectos: ninguno crítico ni mayor. Tres hallazgos menores siguen abiertos (sección 8).

### S9 · 23/11 al 27/11 · J · Despliegue, capacitación y entrega final
- **Responsable:** líder de proyecto. **Ruta crítica:** sí, sin holgura. Fecha límite: **viernes 27/11/2026**.
- **Resultado esperado:** sistema desplegado y acta de aceptación firmada.
- **Estado:** **por hacer.** Punto de partida: el código está publicado y las 406 pruebas pasan. El plan técnico está en [DESPLIEGUE.md](DESPLIEGUE.md), revisado el 15/10/2026 contra el código y con pruebas desechables; el `.gitignore` ya cubre `.env.*` para que `.env.prod` no se suba por error.
  - [ ] Definir el hosting y desplegar el sistema.
  - [ ] Respaldo diario con `mysqldump` y cron, incluyendo la carpeta `media/` (RNF-08).
  - [ ] Cambiar la contraseña de demostración de `seed_demo` antes de desplegar (el repositorio es público).
  - [ ] Página 500 propia (hallazgo H-02).
  - [ ] Capacitación a los docentes.
  - [ ] Acta de aceptación firmada.

## 4. Requisitos funcionales

| Requisito | Prioridad | Estado | Pruebas | Terminado |
|---|---|---|---|---|
| RF-01, RF-02 · Inicio de sesión y opciones por rol | Alta | Hecho | `test_auth` (9) | 13/10 |
| RF-03 · Grupos | Alta | Hecho | `test_grupos` (14) | 13/10 |
| RF-04 · Lista de alumnos desde CSV | Alta | Hecho | `test_importar_alumnos` (19) | 13/10 |
| RF-05 · Inscripción individual | Media | Hecho | `test_inscripciones` (11) | 13/10 |
| RF-06 · Generar sesiones | Alta | Hecho | `test_generar_sesiones` (25) | 13/10 |
| RF-07 · Editar o cancelar sesión | Media | Hecho | `test_editar_sesiones` (15) | 13/10 |
| RF-08 · Registrar asistencia | Alta | Hecho | `test_pase_de_lista` (23), `test_sesion_futura` (10) | 13/10 |
| RF-09 · Sin registros duplicados | Alta | Hecho | `test_integridad` (5), `test_pase_de_lista` | 13/10 |
| RF-10 · Aviso de sesión sin registrar | Alta | Hecho | `test_pendientes` (33) | 13/10 |
| RF-11 · Corrección con bitácora | Alta | Hecho | `test_correccion` (28), `test_bitacora_admin` (2) | 13/10 |
| RF-12 · Justificante | Media | Hecho | `test_justificantes` (37) | 15/10 |
| RF-13 · Porcentaje de asistencia | Alta | Hecho | `test_reportes` (68) | 14/10 |
| RF-14 · Alumnos bajo el mínimo | Alta | Hecho | `test_reportes` | 14/10 |
| RF-15 · Exportar a PDF y Excel | Media | Hecho | `test_exportar` (34) | 14/10 |
| RF-16 · Alta de usuarios con rol | Media | Hecho | `test_usuarios` (38) | 15/10 |

## 5. Requisitos no funcionales

| Requisito | Estado | Evidencia |
|---|---|---|
| RNF-01 · Pase de 40 alumnos en 3 min | Diseñado y medido el costo de interacción | 5 excepciones = 5 toques y 1 envío; falta probarlo con docentes |
| RNF-02 · Responsiva | Verificado a mano | Sin desbordes a 375, 768 y 1280 px; no hay prueba automática |
| RNF-03 · Contraseñas cifradas | Hecho | `pbkdf2_sha256`, comprobado en `test_usuarios` |
| RNF-04 · Cada docente ve solo sus grupos | Hecho | `test_aislamiento` (9), `test_matriz_de_acceso` (7) |
| RNF-05 · Integridad referencial | Hecho | Restricciones del Apéndice A, `test_integridad` |
| RNF-06 · Correcciones con autor y fecha | Hecho | Disparador de la base de datos, `test_integridad`, `test_correccion` |
| RNF-07 · Consultas en menos de 3 s | Medido | Peor caso 570 ms con 50 alumnos; `test_rendimiento` (7) |
| RNF-08 · Respaldo diario | **Pendiente** | Fase J |
| RNF-09 · Código versionado y documentación | Parcial | Código en GitHub y README listos; faltan los manuales (fase I) |

## 6. Métricas del código

| Medida | Valor |
|---|---|
| Commits | 63 (39 el 13/10, 10 el 14/10 y 14 el 15/10) |
| Archivos versionados | 96 |
| Código de la aplicación (Python, sin pruebas) | 3 525 líneas |
| Pruebas (Python) | 5 959 líneas, 406 pruebas en 21 archivos |
| Plantillas HTML | 25 archivos, 1 281 líneas |
| Modelos / migraciones / rutas | 7 / 2 / 25 |
| Servicios de negocio | 12 módulos en `asistencia/services/` |

Entorno: Python 3.11, Django 5.2, MySQL 8.0 en Docker, `openpyxl` y `reportlab`.

## 7. Historial por fase

| Fase | Fechas de los commits | Commits | Primer y último commit |
|---|---|---:|---|
| D · Entorno y autenticación | 13/10 | 9 | `c0000bd` a `47411dc` |
| E · Grupos y sesiones | 13/10 | 17 | `ab7dbbb` a `61904b5` |
| F · Asistencia | 13/10 | 13 | `28b5de0` a `b5e98d9` |
| G · Reportes | 14/10 | 10 | `dfda717` a `30c79a6` |
| RF-12 y RF-16 | 15/10 | 6 | `3a3c3ea` a `229d225` |
| Documentación | 15/10 | 2 | `b064f23`, `5989873` |
| H · Integración y pruebas | 15/10 | 6 | `2140ed3` a `f2f4a9b` |

## 8. Decisiones abiertas, hallazgos y riesgos

**Decisiones abiertas** (también en la sección 12 de CLAUDE.md):
1. **Mínimo de asistencia de 80 %.** Sigue siendo un supuesto sin confirmar (`ASISTENCIA_MINIMA`).
2. **Hosting.** Sin definir; la actividad J depende de esta decisión.
3. **Respaldo de `media/`.** Los justificantes viven ahí y no se versionan; el respaldo diario debe incluirla.
4. **El administrador solo gestiona usuarios.** Es el valor por defecto, sin confirmar.

**Hallazgos menores de la fase H** (ninguno crítico ni mayor):

| Id | Hallazgo | Propuesta |
|---|---|---|
| H-01 | Los botones secundarios miden unos 31 px en el teléfono | Quitar `btn-sm` en esas pantallas |
| H-02 | No hay página 500 propia | Agregarla y probarla con `DEBUG` desactivado |
| H-03 | Importar un CSV de 500 filas tarda 3.8 s (con 50 filas, 0.4 s) | Importar por bloques en lugar de por fila |

**Riesgos**
- **Ruta crítica en J.** Es la única actividad pendiente de la ruta crítica y depende de una decisión que sigue abierta (el hosting).
- **RNF-01 sin evidencia con personas.** El diseño no impone esperas, pero solo se puede confirmar con docentes.
- **Repositorio público.** La contraseña de demostración de `seed_demo` está escrita en el código y cada commit lleva el correo del autor. Conviene cambiar esa contraseña antes de desplegar, o hacer el repositorio privado.
- **Cambios después de la fase H.** Cada cambio exige repetir la suite (unos siete minutos) y conviene actualizar el informe de pruebas.

## 9. Qué se anotó en Trello

El 15/10/2026 se actualizó el tablero con este avance:
- Un comentario con el resultado y la evidencia en las tarjetas D, E, F, G, H, I y J.
- Una lista de subtareas en cada tarjeta, con lo hecho marcado y lo pendiente sin marcar.
- Las tarjetas D, E, F, G y H pasaron a «Hecho» y se marcaron completas; la I pasó a «En curso».
- Dos tarjetas nuevas en «Hecho» para requisitos que el cronograma no lista por separado: RF-12 (justificantes) y RF-16 (alta de usuarios).
- Las tarjetas A, B y C no se tocaron.
