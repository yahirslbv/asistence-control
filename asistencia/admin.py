from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import Usuario
from .services.usuarios import (
    ErrorDeUsuario, aplicar_rol, sincronizar_permisos, validar_cambio,
)


class UsuarioCreationForm(AdminUserCreationForm):
    """Alta de usuarios (RF-16): nombre, apellido, correo y rol son obligatorios."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ('first_name', 'last_name', 'email'):
            self.fields[campo].required = True


class UsuarioChangeForm(UserChangeForm):
    """Edición de usuarios: no deja desactivar ni quitar el rol al último
    administrador activo, ni que alguien se desactive a sí mismo."""

    quien = None   # el usuario que edita; lo pone UsuarioAdmin.get_form

    def clean(self):
        datos = super().clean()
        rol, activo = datos.get('rol'), datos.get('is_active')
        if self.instance.pk and rol is not None and activo is not None:
            try:
                validar_cambio(self.instance, rol, activo, self.quien)
            except ErrorDeUsuario as error:
                raise forms.ValidationError(str(error))
        return datos


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Alta de usuarios con rol (RF-16), cubierta con el admin de Django.

    El rol manda sobre `is_staff` y los permisos (services/usuarios.py), así que
    esos campos, los grupos y los permisos sueltos no se editan aquí: de otro
    modo un administrador podría darse acceso a todo.
    """

    form = UsuarioChangeForm
    add_form = UsuarioCreationForm

    list_display = ('email', 'username', 'first_name', 'last_name', 'rol', 'is_active')
    list_filter = ('rol', 'is_active')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Datos personales', {'fields': ('first_name', 'last_name', 'email')}),
        ('Rol y acceso', {
            'fields': ('rol', 'is_active'),
            'description': 'Un usuario no se borra: se desactiva con «Activo».',
        }),
        ('Fechas', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'usable_password', 'password1', 'password2'),
        }),
        ('Datos personales', {'classes': ('wide',), 'fields': ('first_name', 'last_name', 'email')}),
        ('Rol', {'classes': ('wide',), 'fields': ('rol',)}),
    )
    readonly_fields = ('last_login', 'date_joined')

    def get_form(self, request, obj=None, **kwargs):
        formulario = super().get_form(request, obj, **kwargs)
        quien = request.user

        class FormularioConUsuario(formulario):
            pass

        FormularioConUsuario.quien = quien
        return FormularioConUsuario

    def save_model(self, request, obj, form, change):
        aplicar_rol(obj)
        super().save_model(request, obj, form, change)
        sincronizar_permisos(obj)

    def has_delete_permission(self, request, obj=None):
        # Regla 9.5: los usuarios se desactivan, no se borran. Sin este permiso
        # tampoco existe la acción de borrado masivo.
        return False

    def has_change_permission(self, request, obj=None):
        # Quien gestiona usuarios no puede tocar a un superusuario (por ejemplo,
        # cambiarle la contraseña).
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)
