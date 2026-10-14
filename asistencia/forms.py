from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import NON_FIELD_ERRORS

from .models import Grupo
from .services.importar_alumnos import (
    LONGITUD_CORREO, LONGITUD_MATRICULA, LONGITUD_NOMBRE, TAMANO_MAXIMO_BYTES,
)


class EstiloBootstrapMixin:
    """Agrega las clases de Bootstrap 5 a los campos del formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                continue  # las casillas se dibujan en la plantilla
            clase = 'form-select' if isinstance(widget, forms.Select) else 'form-control'
            widget.attrs['class'] = f"{widget.attrs.get('class', '')} {clase}".strip()


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


class GrupoForm(EstiloBootstrapMixin, forms.ModelForm):
    """Alta y edición de un grupo (RF-03). El docente lo asigna la vista."""

    class Meta:
        model = Grupo
        fields = ['clave', 'materia', 'periodo']
        help_texts = {
            'clave': 'Única por periodo. Ejemplo: ADM-101.',
            'periodo': 'Ejemplo: 2026-2.',
        }
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': 'Ya existe un grupo con esa clave en ese periodo.',
            },
        }


class InscribirAlumnoForm(EstiloBootstrapMixin, forms.Form):
    """Inscripción individual de un alumno en un grupo (RF-05)."""

    matricula = forms.CharField(label='Matrícula', max_length=LONGITUD_MATRICULA)
    nombre = forms.CharField(
        label='Nombre completo', max_length=LONGITUD_NOMBRE,
        help_text='Si la matrícula ya existe, se conserva el nombre registrado.',
    )
    correo = forms.EmailField(label='Correo', max_length=LONGITUD_CORREO, required=False)

    def clean_nombre(self):
        return ' '.join(self.cleaned_data['nombre'].split())


class ImportarAlumnosForm(EstiloBootstrapMixin, forms.Form):
    """Archivo CSV con la lista de alumnos de un grupo (RF-04)."""

    archivo = forms.FileField(
        label='Archivo CSV',
        widget=forms.ClearableFileInput(attrs={'accept': '.csv,text/csv'}),
    )

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        if not archivo.name.lower().endswith('.csv'):
            raise forms.ValidationError('El archivo debe tener extensión .csv.')
        if archivo.size > TAMANO_MAXIMO_BYTES:
            raise forms.ValidationError(
                f'El archivo pesa más de {TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB.')
        return archivo
