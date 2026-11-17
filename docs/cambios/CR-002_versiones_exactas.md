# CR-002 · Versiones exactas de las dependencias

Formato de [CR-000_plantilla.md](CR-000_plantilla.md). Proceso en [gestion_configuracion.md](../gestion_configuracion.md), sección 7.

| Campo | Contenido |
|---|---|
| **ID** | CR-002 |
| **Fecha de la solicitud** | 2026-11-16 |
| **Solicitante** | Líder de proyecto |
| **Tipo** | Mejora de la configuración (sin cambio funcional) |
| **Origen** | Riesgo R13 y criterio de salida S10 del [plan de liberación](../plan_liberacion.md): `requirements.txt` tenía `Django>=5.2,<5.3` y cuatro paquetes sin versión |
| **Prioridad** | Alta: debe estar integrada antes de construir la imagen (bloque B4 de [DESPLIEGUE.md](../DESPLIEGUE.md)) |

## 1. Descripción del cambio

Fijar con `==` la versión de cada dependencia en `requirements.txt`, con las versiones del entorno en el que pasa la suite hoy, y agregar las dos dependencias del despliegue: `whitenoise` (archivos estáticos) y `gunicorn` (servidor de aplicación, solo fuera de Windows).

| Paquete | Antes | Ahora | Tipo |
|---|---|---|---|
| Django | `>=5.2,<5.3` | `==5.2.18` | Directa |
| mysqlclient | sin versión | `==2.3.0` | Directa |
| python-dotenv | sin versión | `==1.2.4` | Directa |
| openpyxl | sin versión | `==3.1.5` | Directa |
| reportlab | sin versión | `==5.0.1` | Directa |
| whitenoise | no estaba | `==6.12.0` | Directa, nueva |
| gunicorn | no estaba | `==27.0.1; sys_platform != "win32"` | Directa, nueva |
| asgiref, sqlparse | sin declarar | `==3.12.1`, `==0.6.0` | Indirectas (Django) |
| tzdata | sin declarar | `==2026.5; sys_platform == "win32"` | Indirecta (Django, solo Windows) |
| et_xmlfile | sin declarar | `==2.0.0` | Indirecta (openpyxl) |
| pillow, charset-normalizer | sin declarar | `==12.3.0`, `==3.5.2` | Indirectas (reportlab) |
| packaging | sin declarar | `==26.3; sys_platform != "win32"` | Indirecta (gunicorn) |

## 2. Justificación

Sin versiones exactas, la imagen que se construye hoy y la que se construye dentro de una semana pueden traer paquetes distintos sin que nadie los haya cambiado. Eso rompe dos cosas del plan de liberación: la candidata `rc.1` y la versión final podrían no ser el mismo producto, y la reversión («volver a la etiqueta anterior y reconstruir») dejaría de devolver la imagen anterior.

## 3. Elementos de configuración afectados

| ECS | Elemento | Línea base | Cambio |
|---|---|---|---|
| ECS-08 | `requirements.txt` | LB-C | Versiones exactas y dos dependencias nuevas |
| ECS-01 | `CLAUDE.md` (Apéndice C) | LB-F | El bloque de `requirements.txt` pasa a remitir al archivo |
| ECS-15 | `CHANGELOG.md` | LB-L | Entrada en `Unreleased` |
| ECS-16 | `docs/gestion_configuracion.md` y `docs/cambios/` | LB-L | Fila en el registro del comité y esta solicitud |

## 4. Evaluación de impacto

| Aspecto | Impacto |
|---|---|
| Alcance y requisitos | No cambia ningún RF. Es parte del RNF-09 (código versionado) y condición del criterio S10 |
| Base de datos (modelo y migraciones) | Ninguno |
| Código | Ninguno: solo cambia `requirements.txt`. `whitenoise` y `gunicorn` quedan instalables, pero ningún módulo los usa todavía (eso es de los bloques B3 y B4) |
| Pruebas | Ninguna prueba cambia. La suite completa se corre con las versiones fijadas |
| Documentación | `CLAUDE.md` (Apéndice C), `CHANGELOG` y el registro del comité |
| Riesgo | Bajo. Las versiones directas son las que ya estaban instaladas. El riesgo que queda es el contrario al de antes: una corrección de seguridad de una dependencia ya no entra sola; hay que subir la versión con otra solicitud de cambio |
| Esfuerzo | Menos de dos horas, casi todo en correr la suite |

## 5. Alternativas consideradas

1. **Dejar los rangos.** Se descarta: es el riesgo R13.
2. **Fijar solo las dependencias directas.** Era la idea inicial y se descartó al probarla. En una imagen `python:3.11-slim` limpia, con solo las directas fijadas, `pip` instaló `asgiref 3.13.0`, `pillow 13.0.0` y `sqlparse 0.6.1`; el entorno donde pasa la suite tiene `3.12.1`, `12.3.0` y `0.6.0`. La imagen habría salido con tres paquetes que la suite nunca probó. Por eso también se fijan las indirectas.
3. **Un archivo de restricciones aparte (`constraints.txt`) para las indirectas.** Se descarta: serían dos archivos que mantener en sincronía, y el criterio S10 revisa `requirements.txt`.
4. **Una herramienta de bloqueo con huellas (`pip-tools`, `uv` o Poetry).** Se descarta: es una herramienta nueva a diez días de la entrega y no la pide ningún requisito. Queda como mejora posible después de la `1.0.0`.

## 6. Decisión del comité de control de cambios

| Campo | Contenido |
|---|---|
| **Decisión** | Aprobada |
| **Fecha** | 2026-11-16 |
| **Responsable de la decisión** | Líder de proyecto (comité unipersonal, ver gestion_configuracion.md sección 1) |
| **Razón** | Estaba prevista en el plan de liberación (sección 2 y riesgo R13). `gunicorn` y `whitenoise` se aprobaron el mismo día como únicas dependencias nuevas del despliegue |
| **Condiciones** | `pip check` sin conflictos y la suite completa en verde antes de fusionar; `gunicorn` con el marcador que lo excluye de Windows. **A revisar en el pull request:** la solicitud pedía fijar las dependencias directas; las indirectas se agregaron durante la implementación por el hallazgo de la alternativa 2 |

## 7. Implementación y verificación

| Campo | Contenido |
|---|---|
| **Rama** | `cambio/cr-002-versiones-exactas` |
| **Pull request** | Se abre desde <https://github.com/yahirslbv/asistence-control/compare/main...cambio/cr-002-versiones-exactas?expand=1> |
| **Versión en la que entra** | 1.0.0 |
| **Pruebas** | Ver la tabla siguiente |

Comprobaciones del 16/11/2026, sobre esta rama:

| Comprobación | Resultado |
|---|---|
| `pip install -r requirements.txt` en el equipo de desarrollo (Windows, Python 3.11.9) | Solo instala `whitenoise 6.12.0`; todo lo demás ya estaba en la versión fijada. `gunicorn` y `packaging` se omiten por su marcador |
| `pip check` en Windows | `No broken requirements found.` |
| Instalación en un contenedor desechable `python:3.11-slim` (Debian 13, Python 3.11.18), con `build-essential`, `pkg-config` y `default-libmysqlclient-dev` | `mysqlclient 2.3.0` compila (`Successfully built mysqlclient`) contra el cliente de MariaDB 3.4.9; `pip check` sin conflictos; `pip freeze` devuelve exactamente las versiones fijadas, más `gunicorn 27.0.1` y `packaging 26.3` |
| Suite completa en MySQL 8.0 (`python manage.py test --noinput`), sobre el commit `ef02f01` | `Ran 650 tests in 638.686s`, `OK`, código de salida 0 |

**Lo que esta solicitud no comprueba.** Que `mysqlclient` compile no prueba que se autentique contra MySQL 8 desde Linux (`caching_sha2_password`): eso se verifica en los bloques B4 y B5, con `migrate` dentro del contenedor. Tampoco se ejecutó `gunicorn` sirviendo la aplicación; solo se instaló y respondió a `gunicorn --version`.
