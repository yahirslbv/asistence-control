"""Reportes de asistencia (RF-13 y RF-14). Las vistas solo coordinan: los
cálculos están en services/reportes.py."""

from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from ..models import Inscripcion
from ..permissions import GrupoDelDocenteMixin, SoloDocenteMixin
from ..services.reportes import (
    minimo_de_asistencia, periodos_del_docente, reporte_del_alumno,
    reporte_del_grupo, reporte_del_periodo, tabla_del_alumno, tabla_del_grupo,
)


class ReportesInicioView(SoloDocenteMixin, TemplateView):
    """Menú «Reportes»: los grupos del docente en un periodo, con su porcentaje
    y cuántos alumnos están bajo el mínimo."""

    template_name = 'asistencia/reportes_inicio.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        periodos = periodos_del_docente(self.request.user)
        pedido = self.request.GET.get('periodo')
        # Un periodo que no es del docente (o mal escrito) cae en el más reciente.
        periodo = pedido if pedido in periodos else (periodos[0] if periodos else None)
        contexto.update(
            periodos=periodos,
            periodo=periodo,
            minimo=minimo_de_asistencia(),
            reporte=reporte_del_periodo(self.request.user, periodo) if periodo else None,
        )
        return contexto


class ReporteGrupoView(GrupoDelDocenteMixin, TemplateView):
    template_name = 'asistencia/reporte_grupo.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        reporte = reporte_del_grupo(self.grupo)
        contexto.update(grupo=self.grupo, reporte=reporte, tabla=tabla_del_grupo(reporte))
        return contexto


class ReporteAlumnoView(GrupoDelDocenteMixin, TemplateView):
    """Reporte de un alumno inscrito en el grupo. Un alumno que no está inscrito
    (por ejemplo, dado de baja) responde 404."""

    template_name = 'asistencia/reporte_alumno.html'

    def cargar_recursos(self, *args, **kwargs):
        super().cargar_recursos(*args, **kwargs)
        self.inscripcion = get_object_or_404(
            Inscripcion.objects.select_related('alumno'),
            grupo=self.grupo, alumno_id=kwargs['alumno_id'],
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        reporte = reporte_del_alumno(self.grupo, self.inscripcion.alumno)
        contexto.update(
            grupo=self.grupo, alumno=self.inscripcion.alumno, reporte=reporte,
            tabla=tabla_del_alumno(reporte))
        return contexto
