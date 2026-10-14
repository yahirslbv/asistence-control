"""Generación de las sesiones de un grupo a partir de su horario (RF-06).

`Grupo` no guarda el horario: se captura al generar. Cada ejecución crea las
sesiones de los días elegidos, con una hora de inicio y fin, entre dos fechas
(ambas incluidas). Es seguro repetirla: no duplica las sesiones que ya existen.
"""

from dataclasses import dataclass
from datetime import timedelta

from ..models import Sesion

# Número de día como lo devuelve date.weekday(): lunes = 0.
DIAS_SEMANA = [
    (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'),
    (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
]

MAX_DIAS_PERIODO = 366


@dataclass
class ResultadoGeneracion:
    creadas: int
    existentes: int   # ya estaban programadas a esa fecha y hora de inicio


def fechas_de_clase(dias, fecha_inicio, fecha_fin):
    """Fechas entre `fecha_inicio` y `fecha_fin` (incluidas) cuyo día de la
    semana está en `dias`."""
    dias = set(dias)
    fecha = fecha_inicio
    while fecha <= fecha_fin:
        if fecha.weekday() in dias:
            yield fecha
        fecha += timedelta(days=1)


def generar_sesiones(grupo, dias, hora_inicio, hora_fin, fecha_inicio, fecha_fin):
    """Crea las sesiones del grupo y cuenta las nuevas y las que ya existían.

    Valida el horario aquí y no confía en la base de datos: `bulk_create` con
    `ignore_conflicts` usa INSERT IGNORE, que descartaría en silencio una
    sesión que viola `hora_fin > hora_inicio` en lugar de fallar.
    """
    if hora_fin <= hora_inicio:
        raise ValueError('La hora de fin debe ser posterior a la de inicio.')
    if fecha_fin < fecha_inicio:
        raise ValueError('La fecha de fin no puede ser anterior a la de inicio.')
    if (fecha_fin - fecha_inicio).days > MAX_DIAS_PERIODO:
        raise ValueError(f'El periodo no puede pasar de {MAX_DIAS_PERIODO} días.')

    fechas = list(fechas_de_clase(dias, fecha_inicio, fecha_fin))
    existentes = set(
        Sesion.objects.filter(grupo=grupo, hora_inicio=hora_inicio, fecha__in=fechas)
        .values_list('fecha', flat=True)
    )
    nuevas = [
        Sesion(grupo=grupo, fecha=fecha, hora_inicio=hora_inicio, hora_fin=hora_fin)
        for fecha in fechas if fecha not in existentes
    ]
    # ignore_conflicts es la última defensa ante una ejecución simultánea.
    Sesion.objects.bulk_create(nuevas, ignore_conflicts=True)
    return ResultadoGeneracion(creadas=len(nuevas), existentes=len(existentes))
