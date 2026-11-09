from django.contrib import messages
from django.contrib.auth import password_validation
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView

from ..forms import LoginForm, RegistroForm
from ..models import Usuario
from ..services.registro import dominios_permitidos, registro_abierto
from ..services.resumen import resumen_del_docente


class IniciarSesionView(LoginView):
    template_name = 'asistencia/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['registro_abierto'] = registro_abierto()   # RF-19: el enlace «Regístrate aquí»
        return contexto


class RegistroView(FormView):
    """Registro de un docente (RF-19). La cuenta queda pendiente de aprobación.

    Quien ya tiene sesión va al inicio. Sin dominios permitidos configurados el
    registro está cerrado y la ruta responde 404.
    """

    template_name = 'asistencia/registro.html'
    form_class = RegistroForm
    success_url = reverse_lazy('login')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('inicio')
        if not registro_abierto():
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['dominios'] = dominios_permitidos()
        contexto['ayuda_contrasena'] = password_validation.password_validators_help_texts()
        return contexto

    def form_valid(self, form):
        if form.guardar() is None:      # el correo se ocupó mientras tanto: el error ya está en el formulario
            return self.form_invalid(form)
        messages.success(
            self.request,
            'Tu cuenta quedó registrada y está pendiente de aprobación. Podrás iniciar '
            'sesión cuando un administrador la apruebe.')
        return super().form_valid(form)


@login_required
def inicio(request):
    """Punto de entrada tras iniciar sesión: cada rol va a su pantalla (RF-02).

    El administrador va a su panel (RF-20), desde donde llega al admin de Django
    para gestionar usuarios (RF-16) y periodos (RF-17); el docente ve su pantalla
    de inicio.
    """
    if request.user.rol == Usuario.Rol.ADMINISTRADOR:
        return redirect('panel_admin')
    return render(request, 'asistencia/inicio.html', {
        'resumen': resumen_del_docente(request.user),
    })
