from django.contrib import messages
from django.shortcuts import redirect
from django.utils.dateparse import parse_date
from django.views.generic import FormView, TemplateView

from ..forms import GenerarSesionesForm
from ..permissions import GrupoDelDocenteMixin
from ..services.generar_sesiones import generar_sesiones
from ..services.sesiones import calendario_de_sesiones


def _fecha_o_none(texto):
    """Fecha de un parámetro de la URL; una fecha mal escrita se ignora."""
    try:
        return parse_date(texto or '')
    except ValueError:
        return None


class SesionListView(GrupoDelDocenteMixin, TemplateView):
    """Calendario de sesiones del grupo, con filtro opcional por fechas."""

    template_name = 'asistencia/sesiones_lista.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        desde = _fecha_o_none(self.request.GET.get('desde'))
        hasta = _fecha_o_none(self.request.GET.get('hasta'))
        contexto.update(
            grupo=self.grupo,
            sesiones=calendario_de_sesiones(self.grupo, desde, hasta),
            desde=desde,
            hasta=hasta,
        )
        return contexto


class GenerarSesionesView(GrupoDelDocenteMixin, FormView):
    """Genera las sesiones del grupo desde su horario y periodo (RF-06)."""

    form_class = GenerarSesionesForm
    template_name = 'asistencia/sesiones_generar.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['grupo'] = self.grupo
        return contexto

    def form_valid(self, form):
        resultado = generar_sesiones(self.grupo, **form.cleaned_data)
        if resultado.creadas:
            messages.success(
                self.request,
                f'Se programaron {resultado.creadas} '
                f"sesi{'ón' if resultado.creadas == 1 else 'ones'}.")
        if resultado.existentes:
            messages.info(
                self.request,
                f'{resultado.existentes} ya estaban programadas a esa fecha y '
                'hora de inicio, y no se tocaron.')
        return redirect('sesiones', grupo_id=self.grupo.pk)
