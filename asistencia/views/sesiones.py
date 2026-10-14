from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.utils.dateparse import parse_date
from django.views.generic import FormView, TemplateView, UpdateView

from ..forms import GenerarSesionesForm, SesionForm
from ..permissions import GrupoDelDocenteMixin, SesionDelDocenteMixin
from ..services.generar_sesiones import generar_sesiones
from ..services.sesiones import (
    SesionNoModificable, asegurar_programada, calendario_de_sesiones,
    cancelar_sesion,
)


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


class SesionProgramadaMixin(SesionDelDocenteMixin):
    """Para vistas que cambian una sesión (RF-07): solo las programadas.

    Una sesión ajena sigue respondiendo 404 (lo resuelve el mixin base antes);
    una propia que ya no está programada vuelve al calendario con el motivo.
    """

    def cargar_recursos(self, *args, **kwargs):
        super().cargar_recursos(*args, **kwargs)
        asegurar_programada(self.sesion)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except SesionNoModificable as error:
            messages.error(request, str(error))
            return redirect('sesiones', grupo_id=self.sesion.grupo_id)


class SesionEditarView(SesionProgramadaMixin, UpdateView):
    """Edita la fecha y el horario de una sesión programada (RF-07)."""

    form_class = SesionForm
    template_name = 'asistencia/sesion_form.html'

    def get_object(self, queryset=None):
        return self.sesion

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['grupo'] = self.grupo
        return contexto

    def form_valid(self, form):
        # La restricción única es la defensa final ante una carrera (regla 9.1).
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error(
                None, 'Este grupo ya tiene una sesión en esa fecha y hora de inicio.')
            return self.form_invalid(form)
        messages.success(self.request, 'Sesión actualizada.')
        return redirect('sesiones', grupo_id=self.grupo.pk)


class SesionCancelarView(SesionProgramadaMixin, TemplateView):
    """Cancela una sesión programada (RF-07), con confirmación."""

    template_name = 'asistencia/sesion_confirmar_cancelar.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(grupo=self.grupo, sesion=self.sesion)
        return contexto

    def post(self, request, *args, **kwargs):
        cancelar_sesion(self.sesion)
        messages.success(request, 'Sesión cancelada.')
        return redirect('sesiones', grupo_id=self.grupo.pk)


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
