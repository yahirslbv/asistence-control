"""Mixins de acceso para las vistas del docente (RNF-04).

Cada docente ve y modifica solo sus grupos. Un grupo o una sesión ajena
responde 404, no 403, para no revelar que existe. Un administrador no tiene
grupos: las pantallas del docente le responden 403.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Grupo, Sesion, Usuario


class SoloDocenteMixin(LoginRequiredMixin):
    """Exige sesión iniciada y rol docente."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.rol != Usuario.Rol.DOCENTE:
                raise PermissionDenied
            self.cargar_recursos(*args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def cargar_recursos(self, *args, **kwargs):
        """Gancho para resolver el recurso de la URL; puede lanzar Http404."""


class GrupoDelDocenteMixin(SoloDocenteMixin):
    """Para vistas con `grupo_id` en la URL: deja el grupo en `self.grupo`."""

    def cargar_recursos(self, *args, **kwargs):
        self.grupo = get_object_or_404(
            Grupo, pk=kwargs['grupo_id'], docente=self.request.user,
        )
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
        super().cargar_recursos(*args, **kwargs)
