"""Mixins de acceso para las vistas del docente (RNF-04).

Cada docente ve y modifica solo sus grupos. Un grupo o una sesión ajena
responde 404, no 403, para no revelar que existe. Un administrador no tiene
grupos: las pantallas del docente le responden 403.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect

from .models import Grupo, Sesion, Usuario
from .services.periodos import PeriodoCerrado, asegurar_periodo_abierto


class SoloDocenteMixin(LoginRequiredMixin):
    """Exige sesión iniciada y rol docente.

    Una vista que modifica un grupo pone `exige_periodo_abierto = True` (RF-17):
    si el periodo del grupo está inactivo, el docente vuelve al grupo con un
    aviso y no se toca nada. Una vista que solo modifica con POST (como el pase
    de lista, que también se consulta) redefine `requiere_periodo_abierto`.
    """

    exige_periodo_abierto = False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.rol != Usuario.Rol.DOCENTE:
                raise PermissionDenied
            try:
                self.cargar_recursos(*args, **kwargs)
            except PeriodoCerrado as error:
                messages.warning(request, str(error))
                return redirect('grupo_detalle', grupo_id=self.grupo.pk)
        return super().dispatch(request, *args, **kwargs)

    def cargar_recursos(self, *args, **kwargs):
        """Gancho para resolver el recurso de la URL; puede lanzar Http404."""

    def requiere_periodo_abierto(self):
        return self.exige_periodo_abierto

    def verificar_periodo(self):
        """Lanza PeriodoCerrado si esta petición modifica un grupo de un periodo
        inactivo. Se llama cuando `self.grupo` ya está cargado."""
        if self.requiere_periodo_abierto():
            asegurar_periodo_abierto(self.grupo)


class GrupoDelDocenteMixin(SoloDocenteMixin):
    """Para vistas con `grupo_id` en la URL: deja el grupo en `self.grupo`."""

    def cargar_recursos(self, *args, **kwargs):
        self.grupo = get_object_or_404(
            Grupo, pk=kwargs['grupo_id'], docente=self.request.user,
        )
        self.verificar_periodo()
        super().cargar_recursos(*args, **kwargs)


class SesionDelDocenteMixin(SoloDocenteMixin):
    """Para vistas con `sesion_id` en la URL: deja la sesión en `self.sesion`
    y su grupo en `self.grupo`."""

    def cargar_recursos(self, *args, **kwargs):
        self.sesion = get_object_or_404(
            Sesion.objects.select_related('grupo'),
            pk=kwargs['sesion_id'], grupo__docente=self.request.user,
        )
        self.grupo = self.sesion.grupo
        self.verificar_periodo()
        super().cargar_recursos(*args, **kwargs)
