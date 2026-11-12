# CR-001 · Página 500 propia (hallazgo H-02)

Formato de [CR-000_plantilla.md](CR-000_plantilla.md). Proceso en [gestion_configuracion.md](../gestion_configuracion.md), sección 7.

| Campo | Contenido |
|---|---|
| **ID** | CR-001 |
| **Fecha de la solicitud** | 2026-11-11 |
| **Solicitante** | Responsable de pruebas (hallazgo de la fase H) |
| **Tipo** | Mejora (hallazgo menor, sin defecto funcional) |
| **Origen** | H-02 del [informe de pruebas](../informe_pruebas.md): con `DEBUG` desactivado Django muestra solo su texto mínimo de error. Ya figura en el [plan de despliegue](../DESPLIEGUE.md) (B2) y en la lista de verificación final (punto 7) |
| **Prioridad** | Media: no bloquea nada hoy, pero hace falta antes de producción |

## 1. Descripción del cambio

Agregar una plantilla `500.html` propia, en español, con la paleta de la aplicación y un enlace al inicio, para que un error del servidor no muestre el texto en inglés `Server Error (500)` con `DEBUG` desactivado.

## 2. Justificación

En producción `DEBUG` está apagado. Un error del servidor (por ejemplo, una base de datos que no responde) deja al docente frente a una pantalla en blanco, sin saber qué pasó ni a dónde ir. Las páginas 403 y 404 ya son propias; la 500 es la única que falta.

## 3. Elementos de configuración afectados

| ECS | Elemento | Línea base | Cambio |
|---|---|---|---|
| ECS-06 | Plantillas (`asistencia/templates/500.html`) | LB-C | Archivo nuevo |
| ECS-07 | Pruebas (`asistencia/tests/test_pagina_500.py`) | LB-C | Archivo nuevo |
| ECS-01 | `CLAUDE.md` (estado de los hallazgos) | LB-F | El H-02 pasa a corregido |
| ECS-12 | Informe de pruebas y seguimiento semanal | LB-C | El H-02 pasa a corregido |
| ECS-15 | `CHANGELOG.md` | LB-L | Entrada en `Unreleased` |

## 4. Evaluación de impacto

| Aspecto | Impacto |
|---|---|
| Alcance y requisitos | No cambia ningún RF ni RNF. Cierra el hallazgo H-02 |
| Base de datos | Ninguno: no toca `models.py` ni migraciones |
| Código | Una plantilla nueva. Sin cambios en Python: Django usa `500.html` por sí solo |
| Pruebas | Un archivo nuevo. Las pruebas existentes no cambian |
| Documentación | `CLAUDE.md`, informe de pruebas, seguimiento semanal y `CHANGELOG` |
| Riesgo | Bajo. El riesgo propio de una página de error es que falle al mostrarse (un segundo error): por eso no debe depender de la base, de la sesión ni de los archivos estáticos, y se prueba con una base de datos caída simulada |
| Esfuerzo | Menos de una hora |

## 5. Alternativas consideradas

1. **Dejar la página por defecto de Django.** Se descarta: sin marca, sin enlace y en inglés.
2. **Extender `base.html`, como hacen la 403 y la 404.** Se descarta: la base usa el usuario, las rutas y el archivo estático de la hoja de estilos. Si el error viene de la base de datos o de `collectstatic`, la página de error fallaría también.
3. **Escribir una vista `handler500` propia con contexto.** Se descarta: más código y más puntos de falla para un caso que debe ser lo más simple posible.

## 6. Decisión del comité de control de cambios

| Campo | Contenido |
|---|---|
| **Decisión** | Aprobada |
| **Fecha** | 2026-11-11 |
| **Responsable de la decisión** | Líder de proyecto (comité unipersonal, ver gestion_configuracion.md sección 1) |
| **Razón** | Riesgo bajo, ya planeada en el despliegue y necesaria para el punto 7 de la lista de verificación final |
| **Condiciones** | La plantilla no usa herencia de plantillas, rutas, usuario ni archivos estáticos. Se prueba con `DEBUG=False`. La suite completa pasa antes de fusionar |

## 7. Implementación y verificación

| Campo | Contenido |
|---|---|
| **Rama** | `cambio/cr-001-pagina-500` |
| **Pull request** | [#2](https://github.com/yahirslbv/asistence-control/pull/2) |
| **Versión en la que entra** | 0.9.0 |
| **Pruebas** | 5 pruebas nuevas en `test_pagina_500.py` (página propia, base de datos caída, sin filtrar detalles del error, sin menú ni hojas de estilo, plantilla sin herencia ni rutas). Suite completa en MySQL 8.0: 650 pruebas, todas correctas (645 de la v0.9.0 más las 5 nuevas), 176.7 s. Verificación inversa: sin `500.html` (plantilla estándar de Django) 3 de las 5 pruebas fallan, así que sí detectan la ausencia de la página propia |
