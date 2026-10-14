from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Inicio de sesión con el correo institucional (RF-01).

    Hereda de ModelBackend para conservar los permisos y la regla de que un
    usuario inactivo (baja lógica) no puede entrar.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('email')
        if username is None or password is None:
            return None

        Usuario = get_user_model()
        try:
            usuario = Usuario.objects.get(email__iexact=username)
        except Usuario.DoesNotExist:
            # Calcula un hash igualmente para no revelar por tiempo de
            # respuesta si el correo existe.
            Usuario().set_password(password)
            return None

        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
