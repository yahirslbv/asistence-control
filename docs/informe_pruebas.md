# Informe de pruebas · Fase H

Sistema de Control de Asistencia · UABC, FCITEC · Administración de Proyectos de Software.
Fecha de las pruebas: 15/10/2026. Las cifras de este informe son las medidas en esta fase; lo que no se midió ni se probó aparece en «Limitaciones».

## 1. Alcance

Esta fase no agrega funciones. Comprueba lo ya construido (RF-01 a RF-16 y los RNF que se pueden probar sin desplegar) con cinco actividades:

1. Flujos de extremo a extremo, automáticos y a mano en el navegador.
2. Matriz de acceso de todas las rutas (RNF-04).
3. Medición del RNF-07 con grupos de 50 alumnos contra MySQL.
4. Análisis del RNF-01 (pase de lista de 40 alumnos).
5. Revisión responsiva (RNF-02).

Fuera de alcance: manuales (fase I), despliegue y respaldo diario (RNF-08, fase J).

## 2. Entorno

| Componente | Versión |
|---|---|
| Python | 3.11.9 |
| Django | 5.2.18 |
| MySQL | 8.0.46, en Docker (`control_asistencia_db`, UTC), valores por defecto del contenedor (`innodb_buffer_pool_size` = 128 MB) |
| mysqlclient / openpyxl / reportlab | 2.3.0 / 3.1.5 / 5.0.1 |
| Sistema | Windows 11, servidor de desarrollo de Django (`runserver`, un solo hilo), `DEBUG` activo |
| Navegador | Navegador integrado de la aplicación de escritorio de Claude |

Las mediciones corrieron en el mismo equipo que MySQL y que el servidor: no incluyen red. Un servidor real con otro hardware dará otros tiempos.

## 3. Resumen

| Actividad | Resultado |
|---|---|
| Suite automática | 406 pruebas, todas en verde (22 de ellas nuevas en esta fase) |
| Flujos de extremo a extremo | 8 pruebas automáticas y un recorrido completo en el navegador: sin diferencias entre lo esperado y lo obtenido |
| Matriz de acceso (RNF-04) | 7 pruebas sobre las 25 rutas de la aplicación: sin fugas ni accesos indebidos |
| RNF-07 (menos de 3 s con grupos de 50) | Cumple con holgura: el peor caso medido con 50 alumnos fue 570 ms. Importar un CSV de 500 filas (fuera del alcance del requisito) tarda 3.8 s (sección 7) |
| RNF-01 (pase de 40 alumnos en 3 min) | No se puede cronometrar a una persona aquí; se midieron el costo de interacción y el tiempo de servidor (sección 8) |
| RNF-02 (responsiva) | Sin desbordes horizontales a 375, 768 y 1280 px; un hallazgo menor (sección 9) |
| Defectos | Ninguno crítico ni mayor. Dos hallazgos menores y una observación (sección 11) |

## 4. Trazabilidad requisito → pruebas

Cada requisito de prioridad Alta tiene al menos una prueba (regla del CLAUDE.md). Los nombres son los reales de `asistencia/tests/`.

| Requisito | Archivo de pruebas | Ejemplo |
|---|---|---|
| RF-01, RF-02 (inicio de sesión y rol) | `test_auth.py` (9) | `test_login_correcto_con_correo`, `test_administrador_es_redirigido_al_admin` |
| RF-03 (grupos) | `test_grupos.py` (14) | alta, edición y baja con confirmación |
| RF-04 (CSV de alumnos) | `test_importar_alumnos.py` (19) | errores por fila sin abortar el archivo |
| RF-05 (inscripción individual) | `test_inscripciones.py` (11) | |
| RF-06 (generar sesiones) | `test_generar_sesiones.py` (25) | |
| RF-07 (editar o cancelar sesión) | `test_editar_sesiones.py` (15) | |
| RF-08 (pase de lista) | `test_pase_de_lista.py` (23) | `test_guardar_crea_un_registro_por_alumno_y_deja_la_sesion_realizada` |
| RF-09 (sin duplicados) | `test_integridad.py` (5), `test_pase_de_lista.py` | `test_registro_duplicado_lanza_integrity_error`, `test_dos_envios_simultaneos_no_duplican_ni_fallan_con_un_error_inesperado` (hilos reales con MySQL) |
| RF-10 (sesiones sin registrar) | `test_pendientes.py` (33) | |
| RF-11 (corrección y bitácora) | `test_correccion.py` (28), `test_integridad.py`, `test_bitacora_admin.py` (2) | `test_una_correccion_anota_en_la_bitacora_el_autor_y_el_valor_anterior` |
| RF-12 (justificante) | `test_justificantes.py` (37) | |
| RF-13 (porcentajes) | `test_reportes.py` (68) | `test_el_porcentaje_se_trunca_no_se_redondea`, `test_el_porcentaje_del_grupo_es_el_ponderado` |
| RF-14 (bajo el mínimo) | `test_reportes.py` | `test_marca_solo_si_es_estrictamente_menor_al_minimo` |
| RF-15 (PDF y Excel) | `test_exportar.py` (34) | `test_el_pdf_trae_exactamente_las_mismas_cifras_que_la_pantalla` |
| RF-16 (alta de usuarios) | `test_usuarios.py` (38) | |
| RNF-01 | `test_pase_de_lista.py`, `test_flujos.py` | todos empiezan en «presente»; un solo envío |
| RNF-03 (contraseñas cifradas) | `test_usuarios.py` | la contraseña guardada empieza con `pbkdf2_sha256$` |
| RNF-04 (aislamiento) | `test_aislamiento.py` (9), `test_matriz_de_acceso.py` (7), `test_flujos.py` | 404, nunca 403, ante un recurso ajeno |
| RNF-05 y RNF-06 (integridad y bitácora) | `test_integridad.py`, `test_bitacora_admin.py` | el disparador escribe aunque el cambio no pase por el ORM |
| RNF-07 | `test_rendimiento.py` (7), conteos en `test_reportes.py`, `test_pase_de_lista.py`, `test_correccion.py`, `test_pendientes.py` | el número de consultas no crece con los datos |
| Páginas 403 y 404, sesiones futuras | `test_errores.py` (4), `test_sesion_futura.py` (10) | |

Sin prueba automática: **RNF-02** (se verificó a mano, sección 9). **RNF-08** y **RNF-09** pertenecen a las fases J e I. El texto literal de RF-01 y RF-02 no se recuperó (CLAUDE.md, sección 6): las pruebas cubren lo que describe el documento.

## 5. Resultados de la suite

`python manage.py test --noinput`: **406 pruebas, OK, en 444.6 s** (7.4 minutos, con el navegador y las mediciones consumiendo el mismo equipo). Antes de esta fase eran 384 pruebas, que tardaron 259 s con el equipo libre. Las 22 nuevas son `test_flujos.py` (8), `test_matriz_de_acceso.py` (7) y `test_rendimiento.py` (7). Las pruebas escriben sus archivos en una carpeta temporal: no tocan `media/` del proyecto.

Las pruebas nuevas de esta fase se validaron por mutación: se rompió a propósito el código y se comprobó que fallaban.

| Archivo nuevo | Mutaciones aplicadas | Detectadas |
|---|---|---|
| `test_flujos.py` | límite del 80 % (`<` a `<=`), aviso de pendientes, borrado de archivos al eliminar el grupo, marca de sesión realizada, baja de inscripción, lista de alumnos del reporte | 6 de 6 |
| `test_matriz_de_acceso.py` | grupo de otro docente visible, sesión de otro docente visible, administrador que pasa, reporte de alumno sin comprobar la inscripción, justificante sin comprobar la sesión | 5 de 5 |
| `test_rendimiento.py` | detalle del grupo sin `select_related` (N+1) | 1 de 1 |

Una mutación que quitaba el filtro de inscritos de la consulta de conteos sobrevivió porque es equivalente: el reporte ya parte de la lista de alumnos inscritos, así que ese filtro no cambia ningún resultado.

## 6. Flujos de extremo a extremo

### 6.1 Automáticos (`test_flujos.py`, 8 pruebas)

Todo entra por las URL y los formularios reales, con reloj fijo (20/10/2026, 18:00 en Tijuana). Un mundo de 40 alumnos y 6 sesiones, con los porcentajes calculados a mano antes de correr la prueba.

| Prueba | Qué recorre |
|---|---|
| Del alta del docente al reporte exportado | Alta por el admin, inicio de sesión, grupo, CSV con filas malas, generar sesiones, cuatro pases de lista, aviso de pendiente, corrección con bitácora, justificante (descarga idéntica byte a byte), reporte, Excel y PDF con las mismas cifras que la pantalla, y la regla de que 80.0 % exactos no está bajo el mínimo |
| Registro con justificante | No se cambia de estado hasta quitar el justificante; después sí, con su fila en la bitácora |
| Baja de un alumno | Deja de contar, su reporte responde 404, sus registros siguen visibles en la sesión; al reinscribirlo vuelve a contar |
| Docente desactivado | Pierde el acceso aunque tuviera la sesión abierta; su historial se conserva |
| Eliminar el grupo | Borra sesiones, registros, bitácora y archivos; el padrón de alumnos no se toca |
| Sesión cancelada | No admite registros y deja de ser pendiente |
| Sesión futura | No admite pase de lista |
| Doble envío del mismo pase | No duplica ni falla |

El doble envío simultáneo con hilos ya estaba cubierto por `EnviosSimultaneosTests`.

### 6.2 Recorrido manual en el navegador

Con un docente creado por el administrador desde el admin, se hizo por la interfaz: inicio de sesión, grupo, carga de un CSV de 40 alumnos con 3 filas con error (informadas por línea: falta la matrícula, matrícula repetida, correo inválido), generación de 5 sesiones, aviso de 4 pendientes en el menú y en el grupo, cuatro pases de lista, corrección con bitácora, justificante, reporte, cancelación de la sesión futura y eliminación del grupo.

Resultado: los números en pantalla coincidieron con los calculados de antemano (98.1 % del grupo, 3 alumnos bajo el mínimo, 75.0 % para el alumno corregido). Al eliminar el grupo, el archivo del justificante desapareció del disco. El docente del recorrido se creó con una contraseña generada al momento; todo lo creado se borró al final y la base de demostración quedó como estaba.

## 7. RNF-07: consultas en menos de 3 s con grupos de hasta 50 alumnos

### Método

- **Datos** (MySQL 8 de Docker, base de desarrollo): seis grupos de 50 alumnos con 48 sesiones realizadas cada uno (un semestre de tres sesiones por semana), 14 400 registros de asistencia con una mezcla de ausentes, retardos y justificados, más 12 sesiones pasadas sin pase de lista.
- **Instrumento:** el cliente de pruebas de Django dentro del mismo proceso (incluye consultas y renderizado de plantillas; no incluye red ni navegador), con un calentamiento y 10 repeticiones por vista. El número de consultas y el tiempo SQL salen de una repetición adicional con captura. Los tiempos SQL salen en múltiplos de unos 15.6 ms (la resolución del temporizador de Windows), así que «SQL 0 ms» significa menos de 16 ms.
- Los datos se crearon y se borraron con un script; el script no se versionó. Este apartado describe el método completo para repetirlo.

### Resultados

| Vista | Mediana (ms) | Máximo (ms) | Consultas | SQL (ms) |
|---|---:|---:|---:|---:|
| Lista de grupos (6 grupos de 50) | 87.9 | 111.0 | 4 | 93.0 |
| Detalle del grupo | 43.6 | 62.3 | 5 | 31.0 |
| Lista de sesiones (48 + 12) | 37.3 | 54.7 | 4 | 0 |
| Pase de lista, primera captura (GET, 50) | 35.1 | 40.5 | 4 | 16.0 |
| Pase de lista, corrección (GET, 50) | 45.4 | 51.2 | 6 | 0 |
| Pase de lista, primera captura (POST, 50) | 43.8 | 53.5 | 10 | 31.0 |
| Corrección (POST, 3 cambios con bitácora) | 39.1 | 50.9 | 9 | 16.0 |
| Inicio de reportes (6 grupos) | 21.8 | 25.4 | 6 | 16.0 |
| Reporte del grupo (50 alumnos) | 63.0 | 83.0 | 7 | 46.0 |
| Reporte de un alumno (48 sesiones) | 47.2 | 55.2 | 7 | 47.0 |
| Exportar grupo a PDF | 198.2 | 278.6 | 7 | 15.0 |
| Exportar alumno a PDF | 88.9 | 104.7 | 7 | 15.0 |
| Exportar grupo a Excel | 90.7 | 119.7 | 7 | 47.0 |
| Exportar alumno a Excel | 61.8 | 76.7 | 7 | 16.0 |
| Importar un CSV de 50 alumnos (5 repeticiones) | 524.8 | 570.5 | 256 | 483.0 |
| Generar 48 sesiones (5 repeticiones) | 33.6 | 50.3 | 8 | 16.0 |

**Conclusión:** con grupos de 50 alumnos, todas las vistas quedan por debajo de 3 s con un margen de más de cinco veces; el peor caso fue la importación del CSV (570 ms). Con ninguna vista fue necesario revisar `EXPLAIN` (el criterio era pasar de 1 s).

### Índices

`SHOW INDEX` coincide con la sección 7 del CLAUDE.md: `ix_asistencia_alumno`, `ix_inscripcion_alumno` e `ix_bitacora_asistencia` existen una sola vez, y `sesion(grupo, fecha)` lo cubre el prefijo de `uq_sesion_grupo_fecha_hora`.

### Segunda medición: navegador real

Con un grupo nuevo de 50 alumnos y 48 sesiones, a través de `runserver` y el navegador (la carga incluye el renderizado):

| Pantalla | Respuesta del servidor (ms) | Carga completa (ms) |
|---|---:|---:|
| Reporte del grupo | 69 | 97 |
| Detalle del grupo | 36 | 62 |
| Lista de sesiones | 36 | 66 |
| Reporte de un alumno | 42 | 66 |

Descargas medidas con `fetch` (mediana de 3): PDF del grupo 180 ms, Excel del grupo 89 ms, PDF del alumno 99 ms, Excel del alumno 71 ms; pase de lista de 50 alumnos 51 ms (87 KB de HTML). Eliminar ese grupo (48 sesiones, 50 inscripciones y 2 400 registros en cascada) tardó 230 ms en el servidor y 290 ms en cargar la pantalla siguiente.

### Importación de CSV con más filas

La aplicación acepta CSV de hasta 500 filas (`MAX_FILAS`). Como la importación hizo unas cinco consultas por fila, se midió con tres tamaños (equipo libre, grupos nuevos y vacíos, mediana de 3 envíos):

| Filas del CSV | Mediana (ms) | Máximo (ms) | Consultas |
|---:|---:|---:|---:|
| 50 | 419 | 1 354 | 255 |
| 200 | 1 592 | 2 076 | 1 005 |
| 500 | 3 838 | 5 018 | 2 505 |

El tiempo crece de forma lineal con las filas. Con 50 alumnos, que es el alcance del RNF-07, tarda alrededor de medio segundo y cumple. Con 500 filas supera los 3 s, pero un grupo de 500 alumnos queda fuera de lo que el requisito acota; se registra como hallazgo H-03.

## 8. RNF-01: pase de lista de 40 alumnos en máximo 3 minutos

No se cronometró a una persona; un tiempo inventado no probaría nada. Esto es lo que sí se midió, con 40 alumnos a 375 px de ancho:

- Los 40 alumnos empiezan en «Presente»: solo se marcan las excepciones.
- Marcar 5 excepciones (2 ausentes, 2 retardos, 1 justificado) costó **5 toques**, y guardar otro: **6 interacciones**, en un único envío que guardó los 40 registros.
- Cada botón de estado mide 48 px de alto y al menos 81 px de ancho (la recomendación habitual es 44 px).
- El botón «Guardar pase de lista» es fijo en la parte baja de la pantalla (47 px de alto): no hay que desplazarse para encontrarlo.
- La página mide 5 405 px de alto, unas 6.7 pantallas de teléfono: pasar lista a 40 alumnos exige desplazarse.
- Servidor: guardar un pase de 50 alumnos tardó una mediana de 43.8 ms (máximo 53.5 ms).

El diseño no impone esperas que se acerquen a los 3 minutos; el tiempo real dependerá de la persona. Verificarlo requiere una prueba con docentes, que no se hizo.

## 9. RNF-02: revisión responsiva

Se cargó cada pantalla del docente (21) con una función en el navegador que mide el ancho de contenido contra el ancho de la ventana, y se revisaron a ojo el pase de lista, los reportes y la pantalla de justificante.

| Ancho | Pantallas revisadas | Desbordes horizontales |
|---|---:|---:|
| 375 px (teléfono) | 22 (las 21 con sesión y el inicio de sesión) | 0 |
| 768 px (tableta) | 21 | 0 |
| 1280 px (escritorio) | 10 | 0 |

- El reporte del grupo se adapta al teléfono (solo nombre, porcentaje y situación) y la tabla completa se desplaza dentro de su contenedor.
- La página 404 técnica que muestra Django con `DEBUG` activo desborda a 375 px. No es la página de producción: las páginas 403 y 404 propias extienden la plantilla base y tienen sus pruebas.
- Hallazgo H-01 (sección 11): botones secundarios pequeños.

## 10. RNF-04: matriz de acceso

Las rutas salen de `asistencia/urls.py`: una ruta nueva sin clasificar rompe la primera prueba. Por cada ruta con recurso (18) y las del docente sin recurso (4), con GET y POST:

| Visitante | Resultado esperado y obtenido |
|---|---|
| Anónimo | Redirige al inicio de sesión |
| Administrador | 403, sin cambios en la base |
| Docente ajeno | 404 (nunca 403), sin cambios en la base ni en los archivos |
| Docente con su propio grupo o sesión pero con un alumno ajeno | 404 |
| Dueño | 200 |

## 11. Defectos y observaciones

No se encontró ningún defecto crítico ni mayor.

| Id | Severidad | Descripción | Estado |
|---|---|---|---|
| H-01 | Menor | Los botones secundarios (`btn-sm`) miden unos 31 px de alto en el teléfono: «Abrir» (lista de grupos), «Agregar alumno» y «Cargar lista (CSV)» (detalle del grupo), «Ver asistencia» (sesiones) y «Reporte» (reportes). En tableta y escritorio también «Cerrar sesión» y «Dar de baja». El RNF-02 pide botones grandes en el pase de lista, y esos miden 48 px | Sin corregir: ver mejoras |
| H-02 | Observación | No hay página 500 propia: con `DEBUG` desactivado, Django muestra su texto mínimo | Para la fase J |
| H-03 | Menor | La importación de CSV hace unas cinco consultas por fila y tarda 0.4 s con 50 filas, 1.6 s con 200 y 3.8 s con 500 (hasta 5.0 s); el máximo que acepta la aplicación son 500 filas. Con 50 alumnos cumple el RNF-07, que es lo que el requisito acota (sección 7) | Sin corregir: decisión pendiente |

## 12. Mejoras sugeridas (no implementadas)

- Quitar `btn-sm` de los botones secundarios en pantallas de teléfono (H-01).
- Agregar una página 500 propia y probarla con `DEBUG` desactivado (H-02).
- Importar el CSV con una consulta por bloque de filas en lugar de por fila (H-03).
- Una prueba automática de las etiquetas de ventana y los tamaños de botones, para que RNF-02 deje de depender de una revisión manual.

## 13. Limitaciones

- **Sin personas.** No se probó con docentes reales; RNF-01 y la usabilidad no tienen evidencia de uso.
- **Un solo navegador y equipo.** Todo se probó en el navegador integrado de la aplicación y con una emulación del tamaño de pantalla, no en teléfonos ni en otros navegadores.
- **Sin red ni carga concurrente.** Las mediciones son de un usuario a la vez, en el mismo equipo que MySQL. La concurrencia solo se probó en el pase de lista (dos envíos simultáneos).
- **Servidor de desarrollo.** `runserver` con `DEBUG` activo; el despliegue (fase J) puede cambiar los tiempos.
- **Rutas probadas.** La matriz cubre las rutas de la aplicación; las del admin de Django se cubren en `test_usuarios.py` y `test_bitacora_admin.py`.
- **No cubierto en esta fase:** respaldo diario (RNF-08) y documentación de instalación y manuales (RNF-09, fase I).

## 14. Cómo repetir las pruebas

```bash
python manage.py test --noinput
```

La medición del RNF-07 se repite con el método de la sección 7. El usuario de MySQL necesita permiso para crear la base `test_control_asistencia` (en el contenedor, `root` ya lo tiene).
