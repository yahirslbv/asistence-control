from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, FormView, ListView, TemplateView,
    UpdateView,
)

from ..forms import GrupoForm, ImportarAlumnosForm, InscribirAlumnoForm
from ..models import Grupo, Inscripcion
from ..permissions import GrupoDelDocenteMixin, SoloDocenteMixin
from ..services.grupos import impacto_de_eliminar
from ..services.importar_alumnos import ErrorDeArchivo, importar_alumnos
from ..services.inscripciones import (
    dar_de_baja, inscribir_alumno, registros_que_se_conservan,
)
from ..services.pendientes import sesiones_pendientes

MENSAJE_GRUPO_DUPLICADO = 'Ya existe un grupo con esa clave en ese periodo.'


class GuardarGrupoMixin:
    """Guarda el grupo capturando el IntegrityError de la restricción única
    (regla 9.1): la base de datos es la defensa final ante una carrera."""

    def form_valid(self, form):
        try:
            with transaction.atomic():
                respuesta = super().form_valid(form)
        except IntegrityError:
            form.add_error(None, MENSAJE_GRUPO_DUPLICADO)
            return self.form_invalid(form)
        messages.success(self.request, self.mensaje_de_exito())
        return respuesta


class GrupoListView(SoloDocenteMixin, ListView):
    template_name = 'asistencia/grupos_lista.html'
    context_object_name = 'grupos'

    def get_queryset(self):
        return (
            Grupo.objects.filter(docente=self.request.user)
            .annotate(
                num_alumnos=Count('inscripciones', distinct=True),
                num_sesiones=Count('sesiones', distinct=True),
            )
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['pendientes'] = sesiones_pendientes(self.request.user)   # RF-10
        return contexto


class GrupoCrearView(SoloDocenteMixin, GuardarGrupoMixin, CreateView):
    form_class = GrupoForm
    template_name = 'asistencia/grupo_form.html'

    def form_valid(self, form):
        form.instance.docente = self.request.user
        return super().form_valid(form)

    def mensaje_de_exito(self):
        return f'Grupo {self.object.clave} creado.'

    def get_success_url(self):
        return reverse_lazy('grupo_detalle', kwargs={'grupo_id': self.object.pk})


class GrupoEditarView(GrupoDelDocenteMixin, GuardarGrupoMixin, UpdateView):
    form_class = GrupoForm
    template_name = 'asistencia/grupo_form.html'

    def get_object(self, queryset=None):
        return self.grupo

    def mensaje_de_exito(self):
        return 'Cambios guardados.'

    def get_success_url(self):
        return reverse_lazy('grupo_detalle', kwargs={'grupo_id': self.grupo.pk})


class GrupoDetalleView(GrupoDelDocenteMixin, DetailView):
    template_name = 'asistencia/grupo_detalle.html'
    context_object_name = 'grupo'

    def get_object(self, queryset=None):
        return self.grupo

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['inscripciones'] = (
            self.grupo.inscripciones.select_related('alumno').order_by('alumno__nombre')
        )
        contexto['pendientes'] = sesiones_pendientes(self.request.user, grupo=self.grupo)  # RF-10
        return contexto


class ImportarAlumnosView(GrupoDelDocenteMixin, FormView):
    """Carga de la lista de alumnos desde un CSV (RF-04).

    Tras importar muestra el resumen en la misma página, con los errores por
    fila. Repetir el envío es inofensivo: la importación es idempotente.
    """

    form_class = ImportarAlumnosForm
    template_name = 'asistencia/grupo_importar.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['grupo'] = self.grupo
        return contexto

    def form_valid(self, form):
        try:
            resultado = importar_alumnos(self.grupo, form.cleaned_data['archivo'])
        except ErrorDeArchivo as error:
            form.add_error('archivo', str(error))
            return self.form_invalid(form)
        return self.render_to_response(
            self.get_context_data(form=self.form_class(), resultado=resultado))


class InscribirAlumnoView(GrupoDelDocenteMixin, FormView):
    """Inscripción individual de un alumno (RF-05)."""

    form_class = InscribirAlumnoForm
    template_name = 'asistencia/grupo_inscribir.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['grupo'] = self.grupo
        return contexto

    def form_valid(self, form):
        datos = form.cleaned_data
        resultado = inscribir_alumno(
            self.grupo, datos['matricula'], datos['nombre'], datos['correo'])
        alumno = resultado.alumno

        if not resultado.inscripcion_nueva:
            messages.warning(
                self.request, f'{alumno.nombre} ya forma parte de este grupo.')
        elif resultado.alumno_nuevo:
            messages.success(
                self.request, f'{alumno.nombre} se agregó a {self.grupo.clave}.')
        else:
            messages.success(
                self.request,
                f'{alumno.nombre} ya estaba en el padrón y se agregó a '
                f'{self.grupo.clave}.')
        return redirect('grupo_detalle', grupo_id=self.grupo.pk)


class BajaAlumnoView(GrupoDelDocenteMixin, TemplateView):
    """Baja individual de un alumno del grupo (RF-05), con confirmación."""

    template_name = 'asistencia/inscripcion_confirmar_baja.html'

    def cargar_recursos(self, *args, **kwargs):
        super().cargar_recursos(*args, **kwargs)
        self.inscripcion = get_object_or_404(
            Inscripcion.objects.select_related('alumno'),
            grupo=self.grupo, alumno_id=kwargs['alumno_id'],
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            grupo=self.grupo,
            alumno=self.inscripcion.alumno,
            registros=registros_que_se_conservan(self.inscripcion),
        )
        return contexto

    def post(self, request, *args, **kwargs):
        nombre = self.inscripcion.alumno.nombre
        dar_de_baja(self.inscripcion)
        messages.success(request, f'{nombre} se dio de baja del grupo {self.grupo.clave}.')
        return redirect('grupo_detalle', grupo_id=self.grupo.pk)


class GrupoEliminarView(GrupoDelDocenteMixin, DeleteView):
    """Baja de un grupo (RF-03). Borra en cascada, así que pide confirmación."""

    template_name = 'asistencia/grupo_confirmar_eliminar.html'
    context_object_name = 'grupo'
    success_url = reverse_lazy('grupos')

    def get_object(self, queryset=None):
        return self.grupo

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['impacto'] = impacto_de_eliminar(self.grupo)
        return contexto

    def form_valid(self, form):
        clave = self.grupo.clave
        respuesta = super().form_valid(form)
        messages.success(self.request, f'Grupo {clave} eliminado junto con su historial.')
        return respuesta
