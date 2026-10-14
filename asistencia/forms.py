from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    """Formulario de inicio de sesión con correo institucional y contraseña."""

    username = forms.EmailField(
        label='Correo institucional',
        widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Correo o contraseña incorrectos.',
    }
