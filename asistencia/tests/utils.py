"""Ayudas comunes para las pruebas."""

from datetime import date, time

from asistencia.models import Alumno, Grupo, Inscripcion, Sesion, Usuario

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


def crear_sesion(grupo, fecha=date(2026, 10, 19), inicio=time(8, 0), fin=time(10, 0),
                 estado=Sesion.Estado.PROGRAMADA):
    return Sesion.objects.create(
        grupo=grupo, fecha=fecha, hora_inicio=inicio, hora_fin=fin, estado=estado)


def inscribir_alumnos(grupo, cantidad, primera_matricula=1200000,
                      fecha_alta=date(2026, 10, 1)):
    """Inscribe `cantidad` alumnos llamados «Alumno 00», «Alumno 01»..., que
    quedan en ese orden. Reutiliza al alumno si la matrícula ya existe."""
    alumnos = []
    for i in range(cantidad):
        alumno, _ = Alumno.objects.get_or_create(
            matricula=str(primera_matricula + i), defaults={'nombre': f'Alumno {i:02d}'})
        Inscripcion.objects.create(grupo=grupo, alumno=alumno, fecha_alta=fecha_alta)
        alumnos.append(alumno)
    return alumnos


def datos_del_pase(modo, estados):
    """Cuerpo del POST del pase de lista: {alumno_id: estado} -> campos del formulario."""
    datos = {'modo': modo}
    datos.update({f'estado_{alumno_id}': estado for alumno_id, estado in estados.items()})
    return datos
