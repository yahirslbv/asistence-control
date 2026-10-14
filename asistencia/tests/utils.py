"""Ayudas comunes para las pruebas."""

from asistencia.models import Grupo, Usuario

PASSWORD = 'clave-de-prueba-123'


def crear_docente(correo='docente@asistencia.test', username='docente'):
    return Usuario.objects.create_user(
        username=username, email=correo, password=PASSWORD,
        rol=Usuario.Rol.DOCENTE,
    )


def crear_administrador(correo='admin@asistencia.test', username='admin'):
    return Usuario.objects.create_user(
        username=username, email=correo, password=PASSWORD,
        rol=Usuario.Rol.ADMINISTRADOR, is_staff=True,
    )


def crear_grupo(docente, clave='ADM-101', materia='Administración de Proyectos',
                periodo='2026-2'):
    return Grupo.objects.create(
        clave=clave, materia=materia, periodo=periodo, docente=docente,
    )
