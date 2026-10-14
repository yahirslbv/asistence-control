"""Pase de lista y corrección (RF-08 a RF-11). Las vistas solo coordinan: la
lógica está en services/asistencia.py."""

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from ..models import Asistencia, Sesion
from ..permissions import SesionDelDocenteMixin, SoloDocenteMixin
from ..services.asistencia import (
    ConflictoDeSesion, DatosInvalidos, ErrorDePaseDeLista, corregir_pase_de_lista,
    historial_de_cambios, lista_de_la_sesion, registrar_pase_de_lista,
    sesion_es_futura,
)
from ..services.pendientes import sesiones_pendientes

MODO_CAPTURA = 'captura'
MODO_CORRECCION = 'correccion'

PREFIJO_DEL_CAMPO = 'estado_'

COLOR_POR_ESTADO = {
    Asistencia.Estado.PRESENTE: 'success',
    Asistencia.Estado.RETARDO: 'warning',
    Asistencia.Estado.AUSENTE: 'danger',
    Asistencia.Estado.JUSTIFICADO: 'info',
}

# (valor, etiqueta, color de Bootstrap) en el orden en que se muestran.
ESTADOS_EN_PANTALLA = [
    (valor, etiqueta, COLOR_POR_ESTADO[valor])
    for valor, etiqueta in Asistencia.Estado.choices
]


def _plural(cantidad, singular, plural):
    return f'{cantidad} {singular if cantidad == 1 else plural}'


def _estados_del_envio(post):
    """{alumno_id: estado} de los campos `estado_<id>` del formulario. Lo que
    no tenga esa forma se ignora; la validación de fondo es del servicio."""
    enviados = {}
    for clave in post:
        if not clave.startswith(PREFIJO_DEL_CAMPO):
            continue
        try:
            alumno_id = int(clave[len(PREFIJO_DEL_CAMPO):])
        except ValueError:
            continue
        enviados[alumno_id] = post.get(clave)
    return enviados


class PaseDeListaView(SesionDelDocenteMixin, TemplateView):
    """Pase de lista de una sesión: primera captura o corrección, según su estado.

    programada = primera captura; realizada = corrección; cancelada = no admite
    registros. El formulario manda su `modo` para que un envío viejo no se
    aplique como si fuera otro (por ejemplo, un doble clic en «Guardar»).
    """

    template_name = 'asistencia/pase_de_lista.html'
    http_method_names = ['get', 'post', 'head', 'options']

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        sesion = self.sesion
        contexto.update(
            sesion=sesion, grupo=self.grupo, estados=ESTADOS_EN_PANTALLA, modo=None,
            futura=False)
        if sesion.estado == Sesion.Estado.CANCELADA:
            return contexto
        if sesion_es_futura(sesion):
            contexto['futura'] = True   # solo mensaje, sin formulario
            return contexto

        filas = lista_de_la_sesion(sesion)
        modo = MODO_CORRECCION if sesion.estado == Sesion.Estado.REALIZADA else MODO_CAPTURA
        contexto.update(
            modo=modo,
            filas=filas,
            sin_registrar=sum(1 for fila in filas if fila.estado is None),
        )
        if modo == MODO_CORRECCION:
            contexto['historial'] = historial_de_cambios(sesion)
        return contexto

    def post(self, request, *args, **kwargs):
        modo = request.POST.get('modo')
        enviados = _estados_del_envio(request.POST)
        try:
            if modo == MODO_CAPTURA:
                resultado = registrar_pase_de_lista(self.sesion.pk, enviados, request.user)
                messages.success(
                    request,
                    'Pase de lista guardado: '
                    f"{_plural(resultado.registrados, 'registro', 'registros')}.")
                if resultado.sin_enviar:
                    messages.warning(
                        request,
                        f"{_plural(resultado.sin_enviar, 'alumno', 'alumnos')} no venían "
                        'en el envío y quedaron sin registrar.')
            elif modo == MODO_CORRECCION:
                resultado = corregir_pase_de_lista(self.sesion.pk, enviados, request.user)
                if resultado.cambiados or resultado.nuevos:
                    partes = []
                    if resultado.cambiados:
                        partes.append(_plural(resultado.cambiados, 'cambio', 'cambios'))
                    if resultado.nuevos:
                        partes.append(_plural(
                            resultado.nuevos, 'registro nuevo', 'registros nuevos'))
                    messages.success(request, f"Corrección guardada: {' y '.join(partes)}.")
                else:
                    messages.info(request, 'No había cambios que guardar.')
            else:
                raise DatosInvalidos('El formulario no es válido. No se guardó nada.')
        except ConflictoDeSesion as error:
            messages.warning(request, str(error))
        except ErrorDePaseDeLista as error:
            messages.error(request, str(error))
        return redirect('pase_de_lista', sesion_id=self.sesion.pk)


class PaseDeListaInicioView(SoloDocenteMixin, TemplateView):
    """Punto de entrada del menú «Pase de lista»: las sesiones de hoy y las
    pendientes de días anteriores (RF-10)."""

    template_name = 'asistencia/pase_de_lista_inicio.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        todas = sesiones_pendientes(self.request.user)
        ids_pendientes = {sesion.pk for sesion in todas}

        de_hoy = list(
            Sesion.objects.filter(grupo__docente=self.request.user, fecha=hoy)
            .select_related('grupo')
            .order_by('hora_inicio', 'grupo__clave')
        )
        for sesion in de_hoy:
            sesion.pendiente = sesion.pk in ids_pendientes   # hoy y ya terminó

        contexto.update(
            hoy=hoy,
            sesiones_de_hoy=de_hoy,
            # Las de hoy ya salen arriba; aquí van solo las de días anteriores.
            pendientes=[s for s in todas if s.fecha != hoy],
        )
        return contexto
