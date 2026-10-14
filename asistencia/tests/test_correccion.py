"""Pruebas de la corrección del pase de lista y de la bitácora (RF-11, RNF-06)."""

from datetime import date, timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from asistencia.models import Alumno, Asistencia, BitacoraCambio, Inscripcion, Sesion
from asistencia.services.asistencia import (
    ConflictoDeSesion, JustificanteImpideCambio, corregir_pase_de_lista,
)

from .utils import (
    PASSWORD, crear_docente, crear_grupo, crear_sesion, datos_del_pase,
    inscribir_alumnos,
)

PRESENTE = Asistencia.Estado.PRESENTE
RETARDO = Asistencia.Estado.RETARDO
AUSENTE = Asistencia.Estado.AUSENTE
JUSTIFICADO = Asistencia.Estado.JUSTIFICADO

ESTADOS_INICIALES = [PRESENTE, PRESENTE, AUSENTE, RETARDO, PRESENTE]


class CorreccionBase(TestCase):
    """Una sesión realizada con cinco registros que capturó otro usuario, para
    que se note quién queda como autor de cada corrección."""

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.capturista = crear_docente('captura@asistencia.test', 'captura')
        cls.grupo = crear_grupo(cls.docente)
        cls.alumnos = inscribir_alumnos(cls.grupo, 5)
        cls.sesion = crear_sesion(cls.grupo, estado=Sesion.Estado.REALIZADA)
        Asistencia.objects.bulk_create([
            Asistencia(sesion=cls.sesion, alumno=alumno, estado=estado,
                       registrado_por=cls.capturista)
            for alumno, estado in zip(cls.alumnos, ESTADOS_INICIALES)
        ])
        cls.url = reverse('pase_de_lista', args=[cls.sesion.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def estados(self, **cambios):
        """Los estados actuales con `cambios` por posición: a1=AUSENTE."""
        estados = {a.pk: e for a, e in zip(self.alumnos, ESTADOS_INICIALES)}
        for clave, valor in cambios.items():
            estados[self.alumnos[int(clave[1:])].pk] = valor
        return estados

    def corregir(self, estados, **extra):
        return self.client.post(
            self.url, datos_del_pase('correccion', estados), **extra)

    def registro(self, posicion):
        return Asistencia.objects.get(sesion=self.sesion, alumno=self.alumnos[posicion])


class BitacoraDeCorreccionesTests(CorreccionBase):

    def test_una_correccion_anota_en_la_bitacora_el_autor_y_el_valor_anterior(self):
        respuesta = self.corregir(self.estados(a2=PRESENTE), follow=True)

        self.assertContains(respuesta, 'Corrección guardada: 1 cambio.')
        cambio = BitacoraCambio.objects.get()
        self.assertEqual(cambio.asistencia, self.registro(2))
        self.assertEqual(cambio.usuario, self.docente)         # quien corrigió...
        self.assertNotEqual(cambio.usuario, self.capturista)   # ...no quien capturó
        self.assertEqual((cambio.valor_anterior, cambio.valor_nuevo), (AUSENTE, PRESENTE))
        self.assertEqual(self.registro(2).registrado_por, self.docente)

    def test_la_fecha_de_la_correccion_es_la_de_ahora(self):
        antes = timezone.now() - timedelta(seconds=5)

        self.corregir(self.estados(a0=AUSENTE))

        cambio = BitacoraCambio.objects.get()
        # El disparador escribe NOW() en UTC y Django lo lee como UTC: sin desfase de zona.
        self.assertGreaterEqual(cambio.fecha_cambio, antes)
        self.assertLess(cambio.fecha_cambio, timezone.now() + timedelta(seconds=5))

    def test_una_correccion_sin_cambios_no_genera_bitacora_ni_toca_registrado_por(self):
        respuesta = self.corregir(self.estados(), follow=True)

        self.assertContains(respuesta, 'No había cambios que guardar.')
        self.assertFalse(BitacoraCambio.objects.exists())
        autores = set(Asistencia.objects.filter(sesion=self.sesion)
                      .values_list('registrado_por', flat=True))
        self.assertEqual(autores, {self.capturista.pk})

    def test_solo_se_tocan_los_registros_que_cambiaron(self):
        self.corregir(self.estados(a2=PRESENTE, a4=RETARDO))

        corregidos = {self.alumnos[2].pk, self.alumnos[4].pk}
        for alumno in self.alumnos:
            registro = Asistencia.objects.get(sesion=self.sesion, alumno=alumno)
            esperado = self.docente if alumno.pk in corregidos else self.capturista
            self.assertEqual(registro.registrado_por, esperado, alumno.nombre)
        self.assertEqual(BitacoraCambio.objects.count(), 2)

    def test_cada_correccion_deja_su_propia_fila_y_se_encadenan(self):
        self.corregir(self.estados(a2=RETARDO))
        self.corregir(self.estados(a2=PRESENTE))

        pares = list(BitacoraCambio.objects.filter(asistencia=self.registro(2))
                     .order_by('id_bitacora').values_list('valor_anterior', 'valor_nuevo'))
        self.assertEqual(pares, [(AUSENTE, RETARDO), (RETARDO, PRESENTE)])

    def test_la_sesion_sigue_realizada_tras_corregir(self):
        self.corregir(self.estados(a0=AUSENTE))

        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, Sesion.Estado.REALIZADA)

    def test_el_servicio_anota_como_autor_a_quien_recibe(self):
        corregir_pase_de_lista(self.sesion.pk, self.estados(a0=JUSTIFICADO), self.capturista)

        self.assertEqual(BitacoraCambio.objects.get().usuario, self.capturista)


class BitacoraVisibleTests(CorreccionBase):

    def test_sin_correcciones_lo_dice(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Historial de correcciones')
        self.assertContains(respuesta, 'Todavía no hay correcciones en esta sesión.')

    def test_muestra_fecha_alumno_cambio_y_autor_la_mas_reciente_primero(self):
        self.corregir(self.estados(a2=RETARDO))
        # La segunda corrección conserva el a2=RETARDO ya guardado y cambia solo a0.
        self.corregir(self.estados(a2=RETARDO, a0=AUSENTE))

        respuesta = self.client.get(self.url)

        historial = list(respuesta.context['historial'])
        self.assertEqual([c.valor_nuevo for c in historial], [AUSENTE, RETARDO])
        self.assertContains(respuesta, 'Presente → Ausente')
        self.assertContains(respuesta, 'Ausente → Retardo')
        self.assertContains(respuesta, self.alumnos[0].nombre)
        self.assertContains(respuesta, self.docente.email)   # sin nombre, se muestra el correo
        self.assertContains(respuesta, timezone.localtime().strftime('%d/%m/%Y'))

    def test_la_primera_captura_no_muestra_historial(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 20))

        respuesta = self.client.get(reverse('pase_de_lista', args=[sesion.pk]))

        self.assertEqual(respuesta.context['modo'], 'captura')
        self.assertNotContains(respuesta, 'Historial de correcciones')

    def test_solo_aparecen_las_correcciones_de_esa_sesion(self):
        otra = crear_sesion(self.grupo, fecha=date(2026, 10, 21), estado=Sesion.Estado.REALIZADA)
        registro = Asistencia.objects.create(
            sesion=otra, alumno=self.alumnos[0], estado=PRESENTE, registrado_por=self.docente)
        registro.estado = AUSENTE
        registro.registrado_por = self.docente
        registro.save()
        self.assertEqual(BitacoraCambio.objects.count(), 1)

        respuesta = self.client.get(self.url)

        self.assertEqual(list(respuesta.context['historial']), [])


class AlumnosSinRegistroTests(CorreccionBase):

    def test_un_inscrito_sin_registro_aparece_sin_estado_y_se_le_puede_registrar(self):
        nuevo = Alumno.objects.create(matricula='7000001', nombre='Zulema Nueva')
        Inscripcion.objects.create(grupo=self.grupo, alumno=nuevo, fecha_alta=date(2026, 10, 19))

        respuesta = self.client.get(self.url)
        fila = next(f for f in respuesta.context['filas'] if f.alumno == nuevo)
        self.assertIsNone(fila.estado)
        self.assertEqual(respuesta.context['sin_registrar'], 1)
        self.assertContains(respuesta, '1 alumno sin registrar')

        estados = self.estados()
        estados[nuevo.pk] = AUSENTE
        respuesta = self.corregir(estados, follow=True)

        self.assertContains(respuesta, 'Corrección guardada: 1 registro nuevo.')
        registro = Asistencia.objects.get(sesion=self.sesion, alumno=nuevo)
        self.assertEqual((registro.estado, registro.registrado_por), (AUSENTE, self.docente))
        self.assertFalse(BitacoraCambio.objects.exists())  # un alta no es una corrección

    def test_si_no_se_elige_estado_sigue_sin_registrar(self):
        nuevo = Alumno.objects.create(matricula='7000001', nombre='Zulema Nueva')
        Inscripcion.objects.create(grupo=self.grupo, alumno=nuevo, fecha_alta=date(2026, 10, 19))

        self.corregir(self.estados())

        self.assertFalse(Asistencia.objects.filter(alumno=nuevo).exists())

    def test_un_inscrito_posterior_a_la_sesion_no_aparece_ni_se_puede_registrar(self):
        tardio = Alumno.objects.create(matricula='7000002', nombre='Tomás Tardío')
        Inscripcion.objects.create(grupo=self.grupo, alumno=tardio, fecha_alta=date(2026, 10, 20))

        respuesta = self.client.get(self.url)
        self.assertNotIn(tardio, [f.alumno for f in respuesta.context['filas']])

        estados = self.estados()
        estados[tardio.pk] = PRESENTE
        self.corregir(estados)
        self.assertFalse(Asistencia.objects.filter(alumno=tardio).exists())

    def test_un_alumno_dado_de_baja_conserva_su_registro_y_se_puede_corregir(self):
        Inscripcion.objects.filter(grupo=self.grupo, alumno=self.alumnos[2]).delete()

        respuesta = self.client.get(self.url)
        self.assertIn(self.alumnos[2], [f.alumno for f in respuesta.context['filas']])

        self.corregir(self.estados(a2=PRESENTE))

        self.assertEqual(self.registro(2).estado, PRESENTE)
        self.assertEqual(BitacoraCambio.objects.count(), 1)

    def test_un_alumno_dado_de_baja_sin_registro_en_la_sesion_no_aparece(self):
        ajeno = Alumno.objects.create(matricula='7000003', nombre='Bruno Baja')
        # Se dio de baja: ya no tiene inscripción y nunca tuvo registro aquí.
        respuesta = self.client.get(self.url)

        self.assertNotIn(ajeno, [f.alumno for f in respuesta.context['filas']])


class ValidacionDeLaCorreccionTests(CorreccionBase):

    def test_un_estado_inventado_rechaza_toda_la_correccion(self):
        # a0 trae un cambio válido y a1 un estado inventado: no se guarda ninguno.
        respuesta = self.corregir(self.estados(a0=AUSENTE, a1='volando'), follow=True)

        self.assertContains(respuesta, 'un estado que no existe')
        guardados = {a.pk: self.registro(i).estado for i, a in enumerate(self.alumnos)}
        self.assertEqual(guardados, self.estados())
        self.assertFalse(BitacoraCambio.objects.exists())

    def test_los_alumnos_ajenos_a_la_lista_se_ignoran(self):
        ajeno = Alumno.objects.create(matricula='8888888', nombre='No inscrito')
        datos = datos_del_pase('correccion', self.estados(a0=AUSENTE))
        datos[f'estado_{ajeno.pk}'] = AUSENTE
        datos['estado_999999'] = AUSENTE
        datos['estado_x'] = AUSENTE

        self.client.post(self.url, datos)

        self.assertEqual(self.registro(0).estado, AUSENTE)
        self.assertFalse(Asistencia.objects.filter(alumno=ajeno).exists())

    def test_un_envio_de_captura_sobre_una_sesion_realizada_no_se_aplica(self):
        """Un formulario viejo (de primera captura) no debe pisar las correcciones."""
        respuesta = self.client.post(
            self.url, datos_del_pase('captura', {a.pk: AUSENTE for a in self.alumnos}),
            follow=True)

        self.assertContains(respuesta, 'ya tenía el pase de lista guardado')
        self.assertEqual(
            {a.pk: self.registro(i).estado for i, a in enumerate(self.alumnos)}, self.estados())

    def test_una_correccion_sobre_una_sesion_sin_pase_de_lista_se_rechaza(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 22))

        respuesta = self.client.post(
            reverse('pase_de_lista', args=[sesion.pk]),
            datos_del_pase('correccion', {a.pk: AUSENTE for a in self.alumnos}), follow=True)

        self.assertContains(respuesta, 'todavía no tiene el pase de lista guardado')
        self.assertFalse(Asistencia.objects.filter(sesion=sesion).exists())

    def test_una_sesion_cancelada_no_admite_correcciones(self):
        Sesion.objects.filter(pk=self.sesion.pk).update(estado=Sesion.Estado.CANCELADA)

        respuesta = self.corregir(self.estados(a0=AUSENTE), follow=True)

        self.assertContains(respuesta, 'está cancelada y no admite registros')
        self.assertEqual(self.registro(0).estado, PRESENTE)


class JustificanteEnLaCorreccionTests(CorreccionBase):
    """El CHECK de la base de datos no admite un justificante en un registro que
    no sea «justificado»: la corrección lo bloquea con un mensaje, sin error 500."""

    def con_justificante(self, posicion=2):
        registro = self.registro(posicion)
        registro.estado = JUSTIFICADO
        registro.justificante = 'justificantes/constancia.pdf'
        registro.save()
        BitacoraCambio.objects.all().delete()
        return registro

    def test_no_se_puede_cambiar_un_registro_con_justificante_a_otro_estado(self):
        self.con_justificante()

        respuesta = self.corregir(self.estados(a2=PRESENTE), follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'tiene un justificante adjunto')
        self.assertContains(respuesta, 'Quita primero el justificante')
        registro = self.registro(2)
        self.assertEqual(registro.estado, JUSTIFICADO)
        self.assertEqual(registro.justificante, 'justificantes/constancia.pdf')
        self.assertFalse(BitacoraCambio.objects.exists())

    def test_el_bloqueo_deshace_tambien_los_demas_cambios_del_envio(self):
        self.con_justificante()

        self.corregir(self.estados(a0=AUSENTE, a2=PRESENTE))

        self.assertEqual(self.registro(0).estado, PRESENTE)   # no quedó a medias
        self.assertFalse(BitacoraCambio.objects.exists())

    def test_el_servicio_lanza_el_error_propio_y_no_un_error_de_base_de_datos(self):
        self.con_justificante()

        with self.assertRaises(JustificanteImpideCambio):
            corregir_pase_de_lista(self.sesion.pk, self.estados(a2=AUSENTE), self.docente)

    def test_dejar_el_mismo_estado_justificado_no_es_un_cambio(self):
        self.con_justificante()
        estados = self.estados(a2=JUSTIFICADO)

        respuesta = self.corregir(estados, follow=True)

        self.assertContains(respuesta, 'No había cambios que guardar.')

    def test_un_justificado_sin_justificante_si_se_puede_cambiar(self):
        registro = self.registro(2)
        registro.estado = JUSTIFICADO
        registro.save()
        BitacoraCambio.objects.all().delete()

        self.corregir(self.estados(a2=AUSENTE))

        self.assertEqual(self.registro(2).estado, AUSENTE)


class ConsultasDeLaCorreccionTests(TestCase):
    """El número de consultas no depende de cuántos alumnos ni cuántos cambios."""

    def setUp(self):
        self.docente = crear_docente()
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def sesion_realizada(self, cantidad, clave, primera_matricula):
        grupo = crear_grupo(self.docente, clave=clave)
        alumnos = inscribir_alumnos(grupo, cantidad, primera_matricula=primera_matricula)
        sesion = crear_sesion(grupo, estado=Sesion.Estado.REALIZADA)
        Asistencia.objects.bulk_create([
            Asistencia(sesion=sesion, alumno=a, estado=PRESENTE, registrado_por=self.docente)
            for a in alumnos])
        return sesion, alumnos

    def consultas(self, accion):
        with CaptureQueriesContext(connection) as capturadas:
            accion()
        return len(capturadas)

    def test_la_pantalla_de_correccion_no_hace_una_consulta_por_alumno(self):
        chica, _ = self.sesion_realizada(5, 'C-CHICA', 3000000)
        grande, _ = self.sesion_realizada(40, 'C-GRANDE', 3100000)
        # Con correcciones en la bitácora, para que el historial también cuente.
        for sesion in (chica, grande):
            registro = Asistencia.objects.filter(sesion=sesion).first()
            registro.estado = AUSENTE
            registro.registrado_por = self.docente
            registro.save()

        n_chica = self.consultas(
            lambda: self.client.get(reverse('pase_de_lista', args=[chica.pk])))
        n_grande = self.consultas(
            lambda: self.client.get(reverse('pase_de_lista', args=[grande.pk])))

        self.assertEqual(n_chica, n_grande)
        self.assertLessEqual(n_grande, 12)

    def test_guardar_una_correccion_no_hace_una_consulta_por_cambio(self):
        una, alumnos_una = self.sesion_realizada(40, 'C-UNO', 3200000)
        muchas, alumnos_muchas = self.sesion_realizada(40, 'C-DIEZ', 3300000)

        n_una = self.consultas(lambda: self.client.post(
            reverse('pase_de_lista', args=[una.pk]),
            datos_del_pase('correccion', {a.pk: (AUSENTE if i < 1 else PRESENTE)
                                          for i, a in enumerate(alumnos_una)})))
        n_muchas = self.consultas(lambda: self.client.post(
            reverse('pase_de_lista', args=[muchas.pk]),
            datos_del_pase('correccion', {a.pk: (AUSENTE if i < 10 else PRESENTE)
                                          for i, a in enumerate(alumnos_muchas)})))

        self.assertEqual(BitacoraCambio.objects.filter(asistencia__sesion=una).count(), 1)
        self.assertEqual(BitacoraCambio.objects.filter(asistencia__sesion=muchas).count(), 10)
        self.assertEqual(n_una, n_muchas)
