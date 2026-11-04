from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.core.exceptions import PermissionDenied
from django.db.models import Count, IntegerField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Grupo, Periodo, Usuario
from .services.periodos import (
    ErrorDePeriodo, activar_periodo, desactivar_periodo, grupos_del_periodo, periodo_activo,
)
from .services.usuarios import (
    ErrorDeUsuario, aplicar_rol, sincronizar_permisos, validar_cambio,
)


# Textos del admin (RF-16 y RF-17). Un administrador no tiene otra pantalla a la que
# volver: el inicio lo regresa aquí, así que no se ofrece «Ver sitio».
admin.site.site_header = 'Control de asistencia'
admin.site.site_title = 'Control de asistencia'
admin.site.index_title = 'Administración'
admin.site.site_url = None
admin.site.enable_nav_sidebar = False   # con dos modelos, la barra lateral solo estorba


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


class PeriodoForm(forms.ModelForm):
    """Alta y edición de un periodo (RF-17). El estado no se edita aquí: se cambia
    con los botones «Activar» y «Desactivar» o con «Guardar y activar»."""

    class Meta:
        model = Periodo
        fields = ('clave', 'fecha_inicio', 'fecha_fin')
        labels = {'clave': 'Clave', 'fecha_inicio': 'Primer día', 'fecha_fin': 'Último día'}
        error_messages = {'clave': {'unique': 'Ya existe un periodo con esa clave.'}}


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    """El administrador crea, edita, activa y desactiva periodos (RF-17).

    Solo uno está activo a la vez: activar uno desactiva el otro. Un periodo
    inactivo deja sus grupos en solo lectura. Los periodos no se borran, se
    desactivan, y la clave no se cambia cuando ya tiene grupos (cada grupo
    guarda la clave como texto). El acceso es por rol, no por permisos sueltos.
    """

    form = PeriodoForm
    change_form_template = 'admin/asistencia/periodo/change_form.html'
    change_list_template = 'admin/asistencia/periodo/change_list.html'

    list_display = ('clave', 'fechas', 'estado', 'grupos', 'acciones')
    list_display_links = ('clave',)
    search_fields = ('clave',)
    ordering = ('-clave',)

    # --- acceso por rol -------------------------------------------------

    def _gestiona_periodos(self, request):
        usuario = request.user
        return usuario.is_active and (
            usuario.is_superuser or usuario.rol == Usuario.Rol.ADMINISTRADOR)

    def has_module_permission(self, request):
        return self._gestiona_periodos(request)

    def has_view_permission(self, request, obj=None):
        return self._gestiona_periodos(request)

    def has_add_permission(self, request):
        return self._gestiona_periodos(request)

    def has_change_permission(self, request, obj=None):
        return self._gestiona_periodos(request)

    def has_delete_permission(self, request, obj=None):
        # Un periodo se desactiva, no se borra: sin fila, sus grupos dejarían de congelarse.
        return False

    # --- lista ----------------------------------------------------------

    def get_queryset(self, request):
        grupos = (
            Grupo.objects.filter(periodo=OuterRef('clave')).order_by()
            .values('periodo').annotate(total=Count('pk')).values('total'))
        return super().get_queryset(request).annotate(
            n_grupos=Coalesce(Subquery(grupos, output_field=IntegerField()), 0))

    @admin.display(description='Fechas')
    def fechas(self, periodo):
        return f'{periodo.fecha_inicio:%d/%m/%Y} – {periodo.fecha_fin:%d/%m/%Y}'

    @admin.display(description='Estado', ordering='activo')
    def estado(self, periodo):
        if periodo.activo:
            return format_html('<span class="etiqueta etiqueta-activa">Activo</span>')
        return format_html('<span class="etiqueta etiqueta-inactiva">Inactivo</span>')

    @admin.display(description='Grupos', ordering='n_grupos')
    def grupos(self, periodo):
        return getattr(periodo, 'n_grupos', None) or grupos_del_periodo(periodo.clave)

    @admin.display(description='')
    def acciones(self, periodo):
        """Un botón que envía el formulario de la página (`form-periodos`, definido
        en la plantilla de la lista), sin anidar formularios."""
        grupos = self.grupos(periodo)
        if periodo.activo:
            aviso = (f'Desactivar {periodo.clave} dejará sus {grupos} grupos en solo lectura. '
                     '¿Continuar?')
            return format_html(
                '<button type="submit" class="boton-periodo" form="form-periodos" name="accion" '
                'value="desactivar-{}" onclick="return confirm(\'{}\')">Desactivar</button>',
                periodo.pk, aviso)
        aviso = (f'Activar {periodo.clave} desactivará el periodo que esté activo y sus grupos '
                 'quedarán en solo lectura. ¿Continuar?')
        return format_html(
            '<button type="submit" class="boton-periodo boton-periodo-principal" form="form-periodos" '
            'name="accion" value="activar-{}" onclick="return confirm(\'{}\')">Activar</button>',
            periodo.pk, aviso)

    # --- formulario -----------------------------------------------------

    def get_readonly_fields(self, request, obj=None):
        # La clave no cambia si ya hay grupos con esa clave (la guardan como texto).
        if obj is not None and grupos_del_periodo(obj.clave):
            return ('clave',)
        return ()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if '_activar' in request.POST:
            self._activar(request, obj)

    # --- activar y desactivar -------------------------------------------

    def get_urls(self):
        propias = [
            path('cambiar-estado/', self.admin_site.admin_view(self.cambiar_estado),
                 name='asistencia_periodo_cambiar_estado'),
        ]
        return propias + super().get_urls()

    def cambiar_estado(self, request):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not self.has_change_permission(request):
            raise PermissionDenied
        accion, _, pk = request.POST.get('accion', '').partition('-')
        if accion not in ('activar', 'desactivar') or not pk.isdigit():
            raise Http404
        try:
            periodo = Periodo.objects.get(pk=int(pk))
        except Periodo.DoesNotExist:
            self.message_user(request, 'Ese periodo ya no existe.', messages.ERROR)
            return redirect(reverse('admin:asistencia_periodo_changelist'))
        if accion == 'activar':
            self._activar(request, periodo)
        else:
            self._desactivar(request, periodo)
        return redirect(reverse('admin:asistencia_periodo_changelist'))

    def _activar(self, request, periodo):
        try:
            anterior = activar_periodo(periodo)
        except ErrorDePeriodo as error:
            self.message_user(request, str(error), messages.ERROR)
            return
        self.log_change(request, periodo, 'Activado.')
        texto = f'Periodo {periodo.clave} activado.'
        if anterior is not None:
            self.log_change(request, anterior, f'Desactivado al activar {periodo.clave}.')
            texto += (f' El periodo {anterior.clave}, que estaba activo, se desactivó: '
                      f'sus {grupos_del_periodo(anterior.clave)} grupos quedan en solo lectura.')
        self.message_user(request, texto, messages.SUCCESS)

    def _desactivar(self, request, periodo):
        try:
            desactivar_periodo(periodo)
        except ErrorDePeriodo as error:
            self.message_user(request, str(error), messages.ERROR)
            return
        self.log_change(request, periodo, 'Desactivado.')
        texto = (f'Periodo {periodo.clave} desactivado: sus {grupos_del_periodo(periodo.clave)} '
                 'grupos quedan en solo lectura.')
        if periodo_activo() is None:
            texto += ' Ya no hay un periodo activo: nadie podrá crear grupos hasta que actives uno.'
        self.message_user(request, texto, messages.SUCCESS)
