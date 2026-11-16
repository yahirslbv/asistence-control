# Aceptación simulada (criterio S7 y RNF-01)

Sistema de Control de Asistencia · UABC, FCITEC · Administración de Proyectos de Software.

| | |
|---|---|
| **Fecha** | 16/11/2026 |
| **Qué se probó** | Código de `main` (`0053cd0`) con la documentación de la fase I (`b8e1d50`) |
| **Quién la hizo** | El asistente de IA, por decisión de Victo del 16/11/2026 |
| **Qué sustituye** | El recorrido de aceptación por una persona que no programó el sistema (S7) y la medición del RNF-01 con personas |
| **Resultado** | S7 cumplido **por simulación**. RNF-01 **estimado**, no medido con personas |

## 1. Qué es y qué no es

El plan de liberación ([plan_liberacion.md](plan_liberacion.md), criterio S7) pedía que una persona ajena al proyecto recorriera los flujos principales, y que el RNF-01 (pase de lista de 40 alumnos en máximo 3 minutos) se cronometrara con docentes. Victo decidió el 16/11/2026 que, por ser un proyecto escolar, ambas pruebas se simulen.

Lo que esta prueba **sí** hace: recorre cada flujo por las mismas URL y formularios que usa una persona, comprueba en cada paso el mensaje que esa persona vería y compara las cifras de los reportes con las calculadas a mano.

Lo que **no** hace: no comprueba si una persona entiende las pantallas, no cronometra a nadie y no corre en la pila de producción (todavía no existe: es la fase J). Por eso el resultado se llama «simulado» y no «aceptado».

## 2. Recorrido del criterio S7

Se ejecutó con el ejecutor de pruebas de Django sobre MySQL 8, en una base de pruebas propia:

```bash
python manage.py test --noinput asistencia.tests.test_flujos asistencia.tests.test_registro asistencia.tests.test_panel_admin asistencia.tests.test_periodos_admin asistencia.tests.test_periodos asistencia.tests.test_casillas asistencia.tests.test_justificantes asistencia.tests.test_reportes asistencia.tests.test_exportar asistencia.tests.test_estilo
```

**Resultado: 333 pruebas, `OK` (330 s).**

El recorrido principal es `test_flujos.CicloCompletoDelDocenteTests.test_del_alta_del_docente_al_reporte_exportado`: un grupo de 40 alumnos, sin tocar el ORM para preparar datos. Los pasos y su comprobación:

| # | Paso (quién) | Qué se comprueba |
|---|---|---|
| 1 | El administrador da de alta al docente en el admin | La cuenta nace con rol docente y sin acceso al admin |
| 2 | El administrador crea el periodo con **Guardar y activar** | El periodo queda activo |
| 3 | El docente inicia sesión | Llega al inicio y ve sus tres accesos (Grupos, Pase de lista y Reportes) |
| 4 | El docente crea el grupo | El grupo queda a su nombre y en el periodo activo |
| 5 | El docente carga un CSV de 40 alumnos con 2 filas con error | Se inscriben los 40 y el error de cada fila se informa sin abortar el archivo |
| 6 | El docente genera las sesiones | «Se programaron 6 sesiones.», en las fechas esperadas |
| 7 | El docente pasa lista en 4 sesiones | «Pase de lista guardado: 40 registros.» y la sesión pasa a realizada |
| 8 | Una sesión pasada queda sin registro | El inicio del pase de lista y el grupo la avisan (RF-10) |
| 9 | El docente corrige un registro | «Corrección guardada: 1 cambio.» y la bitácora guarda quién, cuándo y el valor anterior |
| 10 | El docente adjunta un justificante | «Justificante adjuntado.» y la descarga es idéntica byte a byte |
| 11 | El docente abre el reporte del grupo | Cada fila y el total ponderado coinciden con las cifras calculadas a mano; el aviso de la sesión pendiente aparece |
| 12 | El docente exporta a Excel y a PDF | Ambos traen las mismas cifras que la pantalla |
| 13 | El docente pasa lista de la sesión pendiente | El aviso desaparece y el 80.0 % exacto cuenta como «Cumple» |

Otros módulos del mismo comando cubren el resto del S7:

| Flujo | Pruebas |
|---|---|
| Registro de un docente desde la pantalla de acceso, cuenta pendiente y aviso al intentar entrar | `test_registro` |
| El administrador aprueba o rechaza desde su Panel | `test_panel_admin` |
| Activar y desactivar periodos; el grupo de un periodo inactivo queda en solo lectura y todo vuelve al reactivarlo | `test_periodos_admin`, `test_periodos` y `test_flujos` (cierre de un periodo) |
| Reglas de las casillas del pase de lista | `test_casillas` |
| Reportes y exportaciones | `test_reportes`, `test_exportar` |

## 3. Estimación del RNF-01

El RNF-01 pide un pase de lista de 40 alumnos en máximo 3 minutos (180 s).

**Parte medida (el servidor).** Se abrió y se guardó el pase de lista de un grupo de 40 alumnos con 5 excepciones (2 ausentes, 2 retardos y 1 justificado) en 8 sesiones distintas:

| Operación | Mediana | Peor caso |
|---|---|---|
| Abrir la pantalla del pase de lista | 25 ms | 67 ms |
| Guardar el pase (un solo envío de 40 registros) | 56 ms | 87 ms |

Están medidos sin red ni navegador, con MySQL en la misma máquina. Se comprobó además que quedaron guardados 35 presentes, 2 retardos, 2 ausentes y 1 justificado.

**Parte estimada (la persona).** Con las casillas del RF-18, un retardo cuesta 1 toque, una falta 2 y una falta justificada 3, así que las 5 excepciones cuestan **9 toques** y el guardado es un solo toque. El tiempo se estima con supuestos conservadores, mayores que los del modelo clásico de tiempos por operación (Card, Moran y Newell, 1980):

| Concepto | Cuenta | Tiempo |
|---|---|---|
| Llegar a la sesión (menú y elegir la sesión) | 2 toques × 2 s | 4 s |
| Marcar las excepciones | 9 toques × 2 s | 18 s |
| Desplazarse por la lista (unos 2 600 px a 375 px: unas 4 pantallas) | 4 gestos × 1.5 s | 6 s |
| Decidir cada excepción | 5 × 1.35 s | 7 s |
| Guardar | 1 toque × 2 s | 2 s |
| Servidor (abrir y guardar) | | menos de 0.2 s |
| **Total** | | **unos 37 s** |

Son unos 37 s contra un límite de 180 s: aun si la persona fuera tres veces más lenta (unos 111 s), cabría con margen.

## 4. Límites de esta prueba

- Es una **simulación**: el resultado no equivale a una aceptación por una persona ajena al proyecto ni a un cronometraje con docentes. Si la profesora lo pide, S7 y RNF-01 se repiten con personas y este documento se actualiza.
- La estimación del RNF-01 solo cubre el tiempo de interacción con el sistema. **No incluye lo más lento de un pase de lista real:** identificar quién falta, algo que depende del grupo y no de la aplicación.
- Los tiempos del servidor no incluyen la red ni el dibujado del navegador.
- Se corrió sobre el código, no sobre la pila de producción. El bloque B8 de [DESPLIEGUE.md](DESPLIEGUE.md) repite en la pila real una parte de los pasos (inicio de sesión, periodo, grupo, pase de lista, corrección y justificante: puntos 2, 4 y 5 de su lista de verificación) y su resultado va al informe de la liberación. La carga del CSV, la generación de sesiones, los reportes y las exportaciones quedan cubiertos solo por esta simulación.
- Cada texto de interfaz que citan los manuales se comprobó aparte con un script contra el código y las plantillas (fase I); eso verifica los manuales, no la comprensión de quien los lee.
