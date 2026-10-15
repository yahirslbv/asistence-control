"""Justificantes de asistencia (RF-12). Las vistas solo coordinan: la lógica
está en services/justificantes.py.

Todo pasa por SesionDelDocenteMixin: una sesión ajena responde 404, el
administrador 403 y quien no inició sesión va al login. El archivo solo se
entrega por la vista de descarga; no hay URL pública de `media/`.
"""

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView, TemplateView, View

from ..forms import JustificanteForm
from ..models import Asistencia
from ..permissions import SesionDelDocenteMixin
from ..services.exportar import nombre_de_archivo
from ..services.justificantes import (
    ErrorDeJustificante, SinJustificante, abrir_justificante,
    adjuntar_justificante, quitar_justificante,
)


class RegistroDeLaSesionMixin(SesionDelDocenteMixin):
    """Para vistas con `sesion_id` y `alumno_id`: deja el registro del alumno en
    esa sesión en `self.registro`. Si no tiene registro, responde 404."""

    def cargar_recursos(self, *args, **kwargs):
        super().cargar_recursos(*args, **kwargs)
        self.registro = get_object_or_404(
            Asistencia.objects.select_related('alumno'),
            sesion=self.sesion, alumno_id=kwargs['alumno_id'],
        )

    def volver_a_la_sesion(self):
        return redirect('pase_de_lista', sesion_id=self.sesion.pk)


class JustificanteView(RegistroDeLaSesionMixin, FormView):
    """Ver el estado del justificante y adjuntarlo o reemplazarlo."""

    form_class = JustificanteForm
    template_name = 'asistencia/justificante.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        registro = self.registro
        tiene = bool(registro.justificante)
        tamano = None
        if tiene:
            try:
                tamano = registro.justificante.size
            except OSError:
                tamano = None   # el archivo ya no está en el disco
        contexto.update(
            sesion=self.sesion,
            grupo=self.grupo,
            registro=registro,
            alumno=registro.alumno,
            admite=registro.estado == Asistencia.Estado.JUSTIFICADO,
            tiene=tiene,
            tipo=registro.justificante.name.rsplit('.', 1)[-1].upper() if tiene else None,
            tamano=tamano,
        )
        return contexto

    def form_valid(self, form):
        tenia = bool(self.registro.justificante)
        try:
            adjuntar_justificante(
                self.sesion.pk, self.registro.alumno_id, form.cleaned_data['archivo'])
        except ErrorDeJustificante as error:
            messages.error(self.request, str(error))
            return redirect(self.request.path)
        messages.success(
            self.request, 'Justificante reemplazado.' if tenia else 'Justificante adjuntado.')
        return self.volver_a_la_sesion()


class DescargarJustificanteView(RegistroDeLaSesionMixin, View):
    """Entrega el archivo como adjunto, con un nombre seguro y sin guardarlo en
    cachés."""

    def get(self, request, *args, **kwargs):
        try:
            archivo, tipo, tipo_de_contenido = abrir_justificante(self.registro)
        except SinJustificante:
            raise Http404
        nombre = nombre_de_archivo(
            f'justificante_{self.registro.alumno.matricula}_{self.sesion.fecha:%Y-%m-%d}', tipo)
        respuesta = FileResponse(
            archivo, as_attachment=True, filename=nombre, content_type=tipo_de_contenido)
        respuesta['Cache-Control'] = 'private, no-store'
        return respuesta


class QuitarJustificanteView(RegistroDeLaSesionMixin, TemplateView):
    """Quita el justificante (y borra el archivo), con confirmación."""

    template_name = 'asistencia/justificante_confirmar_quitar.html'

    def cargar_recursos(self, *args, **kwargs):
        super().cargar_recursos(*args, **kwargs)
        if not self.registro.justificante:
            raise Http404

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(sesion=self.sesion, grupo=self.grupo, alumno=self.registro.alumno)
        return contexto

    def post(self, request, *args, **kwargs):
        try:
            quitar_justificante(self.sesion.pk, self.registro.alumno_id)
        except ErrorDeJustificante as error:
            messages.error(request, str(error))
        else:
            messages.success(request, 'Justificante quitado.')
        return self.volver_a_la_sesion()
