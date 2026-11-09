"""Panel del administrador (RF-20) y aprobación de cuentas (RF-19).

El administrador solo gestiona usuarios y periodos: el panel muestra cuentas, el periodo
activo y cifras, pero no abre los grupos de los docentes. Las pantallas de usuarios y
periodos siguen siendo las del admin de Django (RF-16 y RF-17); aquí solo se enlazan.
"""

from django.contrib import messages
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from ..permissions import SoloAdministradorMixin
from ..services.registro import (
    CuentaNoPendiente, aprobar_cuenta, cuentas_pendientes, rechazar_cuenta,
)
from ..services.resumen import resumen_del_administrador


def _nombre(usuario):
    return usuario.get_full_name() or usuario.email


class PanelAdministradorView(SoloAdministradorMixin, TemplateView):
    """Inicio del administrador: cuentas por aprobar, periodo activo y cifras."""

    template_name = 'asistencia/panel_admin.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            resumen=resumen_del_administrador(),
            cuentas=list(cuentas_pendientes()),
        )
        return contexto


class AprobarCuentaView(SoloAdministradorMixin, View):
    """Aprueba una cuenta pendiente. Solo por POST: no hay nada que confirmar."""

    http_method_names = ['post', 'options']

    def post(self, request, usuario_id):
        try:
            usuario = aprobar_cuenta(usuario_id, request.user)
        except CuentaNoPendiente as error:
            messages.warning(request, str(error))
        else:
            messages.success(
                request, f'Cuenta de {_nombre(usuario)} aprobada: ya puede iniciar sesión.')
        return redirect('panel_admin')


class RechazarCuentaView(SoloAdministradorMixin, TemplateView):
    """Rechaza una cuenta pendiente, con confirmación: deja la cuenta desactivada."""

    template_name = 'asistencia/cuenta_confirmar_rechazo.html'
    http_method_names = ['get', 'post', 'head', 'options']

    def get(self, request, usuario_id):
        cuenta = cuentas_pendientes().filter(pk=usuario_id).first()
        if cuenta is None:
            messages.warning(request, 'Esa cuenta ya no está esperando aprobación.')
            return redirect('panel_admin')
        return self.render_to_response(self.get_context_data(cuenta=cuenta))

    def post(self, request, usuario_id):
        try:
            usuario = rechazar_cuenta(usuario_id, request.user)
        except CuentaNoPendiente as error:
            messages.warning(request, str(error))
        else:
            messages.success(
                request, f'Cuenta de {_nombre(usuario)} rechazada: quedó desactivada.')
        return redirect('panel_admin')
