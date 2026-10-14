from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from ..forms import LoginForm
from ..models import Usuario


class IniciarSesionView(LoginView):
    template_name = 'asistencia/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def inicio(request):
    """Punto de entrada tras iniciar sesión: cada rol va a su pantalla (RF-02).

    El administrador gestiona usuarios (RF-16) desde el admin de Django; el
    docente ve su pantalla de inicio.
    """
    if request.user.rol == Usuario.Rol.ADMINISTRADOR:
        return redirect('admin:index')
    return render(request, 'asistencia/inicio.html')
