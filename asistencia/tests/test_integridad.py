"""Pruebas de integridad en la base de datos (RF-09, RF-11, RNF-05 y RNF-06)."""

from datetime import date, time

from django.db import IntegrityError, transaction
from django.test import TestCase

from asistencia.models import (
    Alumno, Asistencia, BitacoraCambio, Grupo, Sesion, Usuario,
)


class IntegridadAsistenciaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(
            username='docente', email='docente@asistencia.test', password='x-12345678',
        )
        cls.otro_docente = Usuario.objects.create_user(
            username='otro', email='otro@asistencia.test', password='x-12345678',
        )
        cls.alumno = Alumno.objects.create(matricula='1200001', nombre='Ana García')
        cls.grupo = Grupo.objects.create(
            clave='ADM-101', materia='Administración de Proyectos',
            periodo='2026-2', docente=cls.docente,
        )
        cls.sesion = Sesion.objects.create(
            grupo=cls.grupo, fecha=date(2026, 10, 19),
            hora_inicio=time(8, 0), hora_fin=time(10, 0),
        )

    def registrar(self, estado=Asistencia.Estado.PRESENTE):
        return Asistencia.objects.create(
            sesion=self.sesion, alumno=self.alumno, estado=estado,
            registrado_por=self.docente,
        )

    def test_registro_duplicado_lanza_integrity_error(self):
        self.registrar()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.registrar(Asistencia.Estado.AUSENTE)

        self.assertEqual(Asistencia.objects.filter(sesion=self.sesion).count(), 1)

    def test_cambiar_el_estado_crea_una_fila_en_la_bitacora(self):
        asistencia = self.registrar(Asistencia.Estado.PRESENTE)
        self.assertFalse(BitacoraCambio.objects.exists())

        # El disparador toma el autor de registrado_por (regla 3 del CLAUDE.md).
        asistencia.estado = Asistencia.Estado.AUSENTE
        asistencia.registrado_por = self.otro_docente
        asistencia.save()

        cambio = BitacoraCambio.objects.get()
        self.assertEqual(cambio.asistencia_id, asistencia.pk)
        self.assertEqual(cambio.usuario, self.otro_docente)
        self.assertEqual(cambio.valor_anterior, Asistencia.Estado.PRESENTE)
        self.assertEqual(cambio.valor_nuevo, Asistencia.Estado.AUSENTE)
        self.assertIsNotNone(cambio.fecha_cambio)

    def test_cada_correccion_deja_su_propia_fila(self):
        asistencia = self.registrar(Asistencia.Estado.PRESENTE)

        for estado in (Asistencia.Estado.RETARDO, Asistencia.Estado.JUSTIFICADO):
            asistencia.estado = estado
            asistencia.registrado_por = self.otro_docente
            asistencia.save()

        pares = list(
            asistencia.cambios.order_by('id_bitacora')
            .values_list('valor_anterior', 'valor_nuevo')
        )
        self.assertEqual(pares, [('presente', 'retardo'), ('retardo', 'justificado')])

    def test_guardar_sin_cambiar_el_estado_no_crea_bitacora(self):
        asistencia = self.registrar()

        asistencia.save()

        self.assertFalse(BitacoraCambio.objects.exists())

    def test_la_bitacora_se_escribe_aunque_el_cambio_no_pase_por_el_orm(self):
        asistencia = self.registrar(Asistencia.Estado.PRESENTE)

        # Modificación directa en SQL, como la haría alguien desde fuera del sistema.
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE asistencia SET estado = %s WHERE id_asistencia = %s',
                ['ausente', asistencia.pk],
            )

        cambio = BitacoraCambio.objects.get()
        self.assertEqual((cambio.valor_anterior, cambio.valor_nuevo), ('presente', 'ausente'))
        self.assertEqual(cambio.usuario, self.docente)
