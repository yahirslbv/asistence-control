"""Inscripción de alumnos en un grupo (RF-04 y RF-05)."""

from typing import NamedTuple

from django.utils import timezone

from ..models import Alumno, Inscripcion


class ResultadoInscripcion(NamedTuple):
    alumno: Alumno
    alumno_nuevo: bool        # False si ya estaba en el padrón
    inscripcion_nueva: bool   # False si ya estaba inscrito en el grupo


def inscribir_alumno(grupo, matricula, nombre, correo=None):
    """Crea o reutiliza el alumno por matrícula y lo inscribe en el grupo.

    Si el alumno ya existe se conservan sus datos del padrón: un mismo alumno
    puede estar en varios grupos sin duplicarse. Es seguro repetirla: nunca
    crea dos inscripciones para el mismo alumno y grupo.
    """
    alumno, alumno_nuevo = Alumno.objects.get_or_create(
        matricula=matricula,
        defaults={'nombre': nombre, 'correo': correo or None},
    )
    _, inscripcion_nueva = Inscripcion.objects.get_or_create(
        grupo=grupo, alumno=alumno,
        defaults={'fecha_alta': timezone.localdate()},
    )
    return ResultadoInscripcion(alumno, alumno_nuevo, inscripcion_nueva)
