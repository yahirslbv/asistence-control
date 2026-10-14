"""Escenario fijo que comparten las pruebas de reportes y de exportación."""

from datetime import date

from django.test import TestCase

from asistencia.models import Alumno, Asistencia, Inscripcion, Sesion

from .utils import RelojFijoMixin, crear_docente, crear_grupo, crear_sesion

PRESENTE = Asistencia.Estado.PRESENTE
RETARDO = Asistencia.Estado.RETARDO
AUSENTE = Asistencia.Estado.AUSENTE
JUSTIFICADO = Asistencia.Estado.JUSTIFICADO
REALIZADA = Sesion.Estado.REALIZADA


class EscenarioFijo(RelojFijoMixin, TestCase):
    """Un grupo con cuatro sesiones realizadas y estos alumnos:

    - A (Ana Alonso): presente, retardo, ausente, justificado -> 3 de 4 = 75.0 %
    - B (Beto Bravo): cuatro presentes -> 100.0 %
    - C (Carla Cruz): inscrita después de las sesiones, sin registros
    - D (Dani Díaz): dado de baja; sus dos registros ya no entran al reporte

    Más dos registros en una sesión programada y una cancelada, que no cuentan.
    """

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        crear = lambda mat, nombre: Alumno.objects.create(matricula=mat, nombre=nombre)  # noqa: E731
        cls.a = crear('1000001', 'Ana Alonso')
        cls.b = crear('1000002', 'Beto Bravo')
        cls.c = crear('1000003', 'Carla Cruz')
        cls.d = crear('1000004', 'Dani Díaz')
        for alumno, alta in ((cls.a, 1), (cls.b, 1), (cls.d, 1), (cls.c, 16)):
            Inscripcion.objects.create(grupo=cls.grupo, alumno=alumno, fecha_alta=date(2026, 10, alta))

        cls.sesiones = [
            crear_sesion(cls.grupo, fecha=date(2026, 10, dia), estado=REALIZADA)
            for dia in (12, 13, 14, 15)
        ]
        estados_de_a = [PRESENTE, RETARDO, AUSENTE, JUSTIFICADO]
        for sesion, estado_a in zip(cls.sesiones, estados_de_a):
            cls.registrar(sesion, cls.a, estado_a)
            cls.registrar(sesion, cls.b, PRESENTE)
        cls.registrar(cls.sesiones[0], cls.d, AUSENTE)
        cls.registrar(cls.sesiones[1], cls.d, AUSENTE)
        # Ya no está inscrito, pero sus registros siguen en la base de datos.
        Inscripcion.objects.filter(grupo=cls.grupo, alumno=cls.d).delete()

        # Registros en sesiones que NO son realizadas: no deben contar.
        cls.programada = crear_sesion(cls.grupo, fecha=date(2026, 10, 17))
        cls.cancelada = crear_sesion(
            cls.grupo, fecha=date(2026, 10, 16), estado=Sesion.Estado.CANCELADA)
        cls.registrar(cls.programada, cls.b, AUSENTE)
        cls.registrar(cls.cancelada, cls.b, AUSENTE)

    @classmethod
    def registrar(cls, sesion, alumno, estado):
        return Asistencia.objects.create(
            sesion=sesion, alumno=alumno, estado=estado, registrado_por=cls.docente)

    def fila(self, reporte, alumno):
        return next(f for f in reporte.filas if f.alumno == alumno)
