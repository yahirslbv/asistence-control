"""Pruebas del alta de usuarios con rol desde el admin (RF-16)."""

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from asistencia.models import Usuario
from asistencia.services.usuarios import (
    CODIGOS_DE_PERMISO_DEL_ADMINISTRADOR, ErrorDeUsuario, aplicar_rol,
    sincronizar_permisos, validar_cambio,
)

from .utils import PASSWORD, crear_docente, crear_grupo

CLAVE_NUEVA = 'Clave-Nueva-2026#x'
RUTA_ALTA = '/admin/asistencia/usuario/add/'
RUTA_LISTA = '/admin/asistencia/usuario/'
ADMINISTRADOR = Usuario.Rol.ADMINISTRADOR
DOCENTE = Usuario.Rol.DOCENTE


def ruta_cambio(usuario):
    return f'/admin/asistencia/usuario/{usuario.pk}/change/'


def datos_de_alta(**cambios):
    datos = {
        'username': 'nueva', 'usable_password': 'true',
        'password1': CLAVE_NUEVA, 'password2': CLAVE_NUEVA,
        'first_name': 'Nora', 'last_name': 'Núñez', 'email': 'nora@asistencia.test',
        'rol': DOCENTE, '_save': 'Guardar',
    }
    datos.update(cambios)
    return datos


def datos_de_cambio(usuario, **cambios):
    """El cuerpo del formulario de edición tal como está hoy, con `cambios`."""
    datos = {
        'username': usuario.username, 'first_name': usuario.first_name,
        'last_name': usuario.last_name, 'email': usuario.email,
        'rol': usuario.rol, '_save': 'Guardar',
    }
    if usuario.is_active:
        datos['is_active'] = 'on'        # una casilla sin marcar no se envía
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not None}


def permisos_de(usuario):
    return set(usuario.user_permissions.values_list('codename', flat=True))


class BaseDelAdmin(TestCase):
    """Un administrador (actor habitual) y un superusuario."""

    @classmethod
    def setUpTestData(cls):
        from .utils import crear_administrador
        cls.admin = crear_administrador()
        cls.root = Usuario.objects.create_superuser(
            username='root', email='root@asistencia.test', password=PASSWORD)

    def entrar_como(self, usuario):
        self.assertTrue(self.client.login(username=usuario.email, password=PASSWORD))


class AltaDeUsuariosTests(BaseDelAdmin):

    def setUp(self):
        self.entrar_como(self.admin)

    def test_alta_de_un_docente_sin_acceso_al_admin(self):
        respuesta = self.client.post(RUTA_ALTA, datos_de_alta())

        nuevo = Usuario.objects.get(email='nora@asistencia.test')
        # El admin de usuarios lleva a la ficha del usuario recién creado.
        self.assertRedirects(respuesta, ruta_cambio(nuevo), fetch_redirect_response=False)
        self.assertEqual((nuevo.rol, nuevo.first_name, nuevo.last_name), (DOCENTE, 'Nora', 'Núñez'))
        self.assertFalse(nuevo.is_staff)
        self.assertEqual(permisos_de(nuevo), set())

    def test_alta_de_un_administrador_con_acceso_solo_a_usuarios(self):
        self.client.post(RUTA_ALTA, datos_de_alta(rol=ADMINISTRADOR, username='jefa'))

        nuevo = Usuario.objects.get(username='jefa')
        self.assertTrue(nuevo.is_staff)
        self.assertEqual(permisos_de(nuevo), set(CODIGOS_DE_PERMISO_DEL_ADMINISTRADOR))
        self.assertTrue(nuevo.has_perm('asistencia.add_usuario'))
        self.assertTrue(nuevo.has_perm('asistencia.change_usuario'))
        self.assertTrue(nuevo.has_perm('asistencia.view_usuario'))
        self.assertFalse(nuevo.has_perm('asistencia.delete_usuario'))
        self.assertFalse(nuevo.has_perm('asistencia.add_grupo'))
        self.assertFalse(nuevo.has_perm('asistencia.view_asistencia'))

    def test_nombre_apellido_y_correo_son_obligatorios(self):
        for campo in ('first_name', 'last_name', 'email'):
            with self.subTest(campo):
                respuesta = self.client.post(RUTA_ALTA, datos_de_alta(**{campo: ''}))

                self.assertEqual(respuesta.status_code, 200)
                self.assertFormError(respuesta.context['adminform'].form, campo, 'Este campo es obligatorio.')
        self.assertFalse(Usuario.objects.filter(username='nueva').exists())

    def test_el_correo_repetido_se_rechaza(self):
        respuesta = self.client.post(RUTA_ALTA, datos_de_alta(email=self.admin.email))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username='nueva').exists())

    def test_las_contrasenas_deben_coincidir(self):
        respuesta = self.client.post(RUTA_ALTA, datos_de_alta(password2='otra-distinta-1'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username='nueva').exists())

    def test_la_contrasena_se_guarda_con_hash_y_no_aparece_en_la_respuesta(self):
        respuesta = self.client.post(RUTA_ALTA, datos_de_alta(), follow=True)

        nuevo = Usuario.objects.get(email='nora@asistencia.test')
        self.assertNotEqual(nuevo.password, CLAVE_NUEVA)
        self.assertTrue(nuevo.password.startswith('pbkdf2_sha256$'))
        self.assertTrue(nuevo.check_password(CLAVE_NUEVA))
        self.assertNotContains(respuesta, CLAVE_NUEVA)

    def test_el_usuario_nuevo_entra_con_su_correo_y_se_redirige_segun_su_rol(self):
        self.client.post(RUTA_ALTA, datos_de_alta())
        self.client.post(RUTA_ALTA, datos_de_alta(
            username='jefa', email='jefa@asistencia.test', rol=ADMINISTRADOR))
        self.client.logout()

        self.assertTrue(self.client.login(username='nora@asistencia.test', password=CLAVE_NUEVA))
        self.assertEqual(self.client.get(reverse('inicio')).status_code, 200)    # su inicio de docente
        self.client.logout()

        self.assertTrue(self.client.login(username='jefa@asistencia.test', password=CLAVE_NUEVA))
        self.assertRedirects(
            self.client.get(reverse('inicio')), reverse('admin:index'), fetch_redirect_response=False)

    def test_los_campos_de_acceso_no_se_pueden_forzar_desde_el_formulario(self):
        """is_staff, is_superuser, grupos y permisos los decide el rol, no el envío."""
        permiso = Permission.objects.get(codename='add_grupo')
        datos = datos_de_alta(is_superuser='on', is_staff='on', user_permissions=[permiso.pk])

        self.client.post(RUTA_ALTA, datos)

        nuevo = Usuario.objects.get(email='nora@asistencia.test')
        self.assertFalse(nuevo.is_superuser)
        self.assertFalse(nuevo.is_staff)
        self.assertEqual(permisos_de(nuevo), set())

    def test_el_formulario_de_alta_pide_los_datos_que_dice_el_requisito(self):
        respuesta = self.client.get(RUTA_ALTA)

        campos = set(respuesta.context['adminform'].form.fields)
        self.assertTrue({'username', 'password1', 'password2', 'first_name',
                         'last_name', 'email', 'rol'} <= campos)
        for oculto in ('is_staff', 'is_superuser', 'groups', 'user_permissions'):
            self.assertNotIn(oculto, campos)


class CambioDeRolTests(BaseDelAdmin):

    def setUp(self):
        self.entrar_como(self.admin)

    def test_de_docente_a_administrador_da_acceso_y_permisos(self):
        docente = crear_docente()

        self.client.post(ruta_cambio(docente), datos_de_cambio(docente, rol=ADMINISTRADOR))

        docente.refresh_from_db()
        self.assertEqual(docente.rol, ADMINISTRADOR)
        self.assertTrue(docente.is_staff)
        self.assertEqual(permisos_de(docente), set(CODIGOS_DE_PERMISO_DEL_ADMINISTRADOR))

    def test_de_administrador_a_docente_quita_acceso_y_permisos(self):
        otro = Usuario.objects.get(pk=self.admin.pk)
        segundo = Usuario.objects.create_user(
            username='segundo', email='segundo@asistencia.test', password=PASSWORD,
            rol=ADMINISTRADOR, is_staff=True)
        sincronizar_permisos(segundo)

        self.client.post(ruta_cambio(segundo), datos_de_cambio(segundo, rol=DOCENTE))

        segundo.refresh_from_db()
        self.assertEqual(segundo.rol, DOCENTE)
        self.assertFalse(segundo.is_staff)
        self.assertEqual(permisos_de(segundo), set())
        self.assertEqual(otro.rol, ADMINISTRADOR)

    def test_un_administrador_puede_dejar_de_serlo_si_queda_otro(self):
        # self.admin cede su propio rol: queda root (superusuario) pero no cuenta como
        # administrador; con un segundo administrador activo sí se permite.
        segundo = Usuario.objects.create_user(
            username='segundo', email='segundo@asistencia.test', password=PASSWORD,
            rol=ADMINISTRADOR, is_staff=True)
        sincronizar_permisos(segundo)

        respuesta = self.client.post(
            ruta_cambio(self.admin), datos_de_cambio(self.admin, rol=DOCENTE))

        self.assertRedirects(respuesta, RUTA_LISTA, fetch_redirect_response=False)
        self.admin.refresh_from_db()
        self.assertEqual((self.admin.rol, self.admin.is_staff), (DOCENTE, False))

    def test_un_superusuario_conserva_el_acceso_al_admin_aunque_su_rol_sea_docente(self):
        self.client.logout()
        self.entrar_como(self.root)
        self.assertEqual(self.root.rol, DOCENTE)       # createsuperuser crea el rol docente

        self.client.post(ruta_cambio(self.root), datos_de_cambio(self.root, first_name='Raúl'))

        self.root.refresh_from_db()
        self.assertTrue(self.root.is_staff)
        self.assertTrue(self.root.is_superuser)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_cambiar_el_rol_a_un_superusuario_a_administrador_le_da_los_permisos(self):
        self.client.logout()
        self.entrar_como(self.root)

        self.client.post(ruta_cambio(self.root), datos_de_cambio(self.root, rol=ADMINISTRADOR))

        self.root.refresh_from_db()
        self.assertEqual(self.root.rol, ADMINISTRADOR)
        self.assertTrue(self.root.is_staff)

    def test_el_formulario_de_edicion_no_trae_los_campos_de_acceso(self):
        docente = crear_docente()

        respuesta = self.client.get(ruta_cambio(docente))

        campos = set(respuesta.context['adminform'].form.fields)
        for oculto in ('is_staff', 'is_superuser', 'groups', 'user_permissions'):
            self.assertNotIn(oculto, campos)
        self.assertTrue({'rol', 'is_active'} <= campos)

    def test_un_envio_con_campos_de_acceso_no_escala_privilegios(self):
        docente = crear_docente()

        self.client.post(ruta_cambio(docente), datos_de_cambio(
            docente, is_superuser='on', is_staff='on'))

        docente.refresh_from_db()
        self.assertFalse(docente.is_superuser)
        self.assertFalse(docente.is_staff)


class BajasLogicasTests(BaseDelAdmin):

    def setUp(self):
        self.entrar_como(self.admin)

    def test_desactivar_con_activo_impide_entrar_y_reactivar_lo_permite(self):
        docente = crear_docente()
        self.assertTrue(self.client.login(username=docente.email, password=PASSWORD))
        self.client.logout()
        self.entrar_como(self.admin)

        self.client.post(ruta_cambio(docente), datos_de_cambio(docente, is_active=None))
        docente.refresh_from_db()
        self.assertFalse(docente.is_active)
        self.client.logout()
        self.assertFalse(self.client.login(username=docente.email, password=PASSWORD))

        self.entrar_como(self.admin)
        self.client.post(ruta_cambio(docente), datos_de_cambio(docente, is_active='on'))
        self.client.logout()
        self.assertTrue(self.client.login(username=docente.email, password=PASSWORD))

    def test_no_hay_ruta_de_borrado_ni_para_el_administrador_ni_para_el_superusuario(self):
        docente = crear_docente()
        ruta = f'/admin/asistencia/usuario/{docente.pk}/delete/'

        for actor in (self.admin, self.root):
            with self.subTest(actor=actor.username):
                self.client.logout()
                self.entrar_como(actor)
                self.assertEqual(self.client.get(ruta).status_code, 403)
                self.assertEqual(self.client.post(ruta, {'post': 'yes'}).status_code, 403)
        self.assertTrue(Usuario.objects.filter(pk=docente.pk).exists())

    def test_la_lista_no_ofrece_el_borrado_masivo(self):
        docente = crear_docente()

        pagina = self.client.get(RUTA_LISTA)
        self.assertNotContains(pagina, 'delete_selected')

        respuesta = self.client.post(RUTA_LISTA, {
            'action': 'delete_selected', '_selected_action': [docente.pk], 'post': 'yes'})
        self.assertTrue(Usuario.objects.filter(pk=docente.pk).exists())
        self.assertNotEqual(respuesta.status_code, 500)

    def test_un_usuario_con_historial_no_se_puede_borrar_ni_por_codigo(self):
        docente = crear_docente()
        crear_grupo(docente)

        with self.assertRaises(ProtectedError):
            docente.delete()
        self.assertTrue(Usuario.objects.filter(pk=docente.pk).exists())


class UltimoAdministradorTests(BaseDelAdmin):

    def desactivar(self, actor, objetivo):
        self.client.logout()
        self.entrar_como(actor)
        return self.client.post(ruta_cambio(objetivo), datos_de_cambio(objetivo, is_active=None))

    def administrador(self, usuario, **extra):
        nuevo = Usuario.objects.create_user(
            username=usuario, email=f'{usuario}@asistencia.test', password=PASSWORD,
            rol=ADMINISTRADOR, is_staff=True, **extra)
        sincronizar_permisos(nuevo)
        return nuevo

    def test_no_se_desactiva_al_ultimo_administrador_activo(self):
        respuesta = self.desactivar(self.root, self.admin)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'último administrador activo')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_no_se_le_quita_el_rol_al_ultimo_administrador_activo(self):
        self.entrar_como(self.root)

        respuesta = self.client.post(
            ruta_cambio(self.admin), datos_de_cambio(self.admin, rol=DOCENTE))

        self.assertContains(respuesta, 'último administrador activo')
        self.admin.refresh_from_db()
        self.assertEqual((self.admin.rol, self.admin.is_staff), (ADMINISTRADOR, True))

    def test_un_administrador_no_se_desactiva_a_si_mismo(self):
        self.administrador('segundo')

        respuesta = self.desactivar(self.admin, self.admin)

        self.assertContains(respuesta, 'No puedes desactivarte a ti mismo.')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_con_dos_administradores_se_puede_desactivar_a_uno(self):
        segundo = self.administrador('segundo')

        respuesta = self.desactivar(self.root, segundo)

        self.assertRedirects(respuesta, RUTA_LISTA, fetch_redirect_response=False)
        segundo.refresh_from_db()
        self.assertFalse(segundo.is_active)

    def test_un_administrador_inactivo_no_cuenta(self):
        self.administrador('inactivo', is_active=False)

        respuesta = self.desactivar(self.root, self.admin)

        self.assertContains(respuesta, 'último administrador activo')

    def test_los_docentes_se_desactivan_sin_restriccion(self):
        docente = crear_docente()

        respuesta = self.desactivar(self.admin, docente)

        self.assertRedirects(respuesta, RUTA_LISTA, fetch_redirect_response=False)


class AccesoAlAdminTests(BaseDelAdmin):

    def test_un_docente_no_entra_al_admin(self):
        docente = crear_docente()
        self.entrar_como(docente)

        for ruta in ('/admin/', RUTA_LISTA, RUTA_ALTA):
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertRedirects(
                    respuesta, f'/admin/login/?next={ruta}', fetch_redirect_response=False)
        self.client.post(RUTA_ALTA, datos_de_alta())
        self.assertFalse(Usuario.objects.filter(username='nueva').exists())

    def test_el_formulario_de_entrada_del_admin_rechaza_a_un_docente(self):
        crear_docente()

        respuesta = self.client.post('/admin/login/', {
            'username': 'docente@asistencia.test', 'password': PASSWORD, 'next': '/admin/'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_un_administrador_solo_ve_usuarios_en_el_admin(self):
        self.entrar_como(self.admin)

        respuesta = self.client.get('/admin/')

        modelos = [(app['app_label'], m['object_name'])
                   for app in respuesta.context['app_list'] for m in app['models']]
        self.assertEqual(modelos, [('asistencia', 'Usuario')])

    def test_un_administrador_no_entra_a_otros_modelos(self):
        self.entrar_como(self.admin)

        for ruta in ('/admin/auth/group/', '/admin/auth/group/add/'):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 403)
        for modelo in ('grupo', 'sesion', 'asistencia', 'bitacoracambio', 'alumno'):
            with self.subTest(modelo=modelo):
                self.assertEqual(self.client.get(f'/admin/asistencia/{modelo}/').status_code, 404)

    def test_un_administrador_no_toca_a_un_superusuario(self):
        self.entrar_como(self.admin)
        clave_antes = self.root.password

        ficha = self.client.get(ruta_cambio(self.root))
        self.assertEqual(ficha.status_code, 200)                 # solo lectura...
        self.assertNotContains(ficha, 'name="_save"')            # ...sin botón de guardar
        self.assertEqual(self.client.post(
            ruta_cambio(self.root), datos_de_cambio(self.root, first_name='Hack')).status_code, 403)
        ruta_clave = f'/admin/asistencia/usuario/{self.root.pk}/password/'
        self.assertEqual(self.client.post(
            ruta_clave, {'password1': 'otra-Clave-9#', 'password2': 'otra-Clave-9#'}).status_code, 403)
        self.root.refresh_from_db()
        self.assertEqual(self.root.password, clave_antes)
        self.assertNotEqual(self.root.first_name, 'Hack')

    def test_un_administrador_si_edita_a_un_docente_y_le_cambia_la_contrasena(self):
        self.entrar_como(self.admin)
        docente = crear_docente()

        self.assertEqual(self.client.get(ruta_cambio(docente)).status_code, 200)
        respuesta = self.client.post(
            f'/admin/asistencia/usuario/{docente.pk}/password/',
            {'password1': CLAVE_NUEVA, 'password2': CLAVE_NUEVA, 'usable_password': 'true'})

        self.assertEqual(respuesta.status_code, 302)
        docente.refresh_from_db()
        self.assertTrue(docente.check_password(CLAVE_NUEVA))

    def test_un_administrador_desactivado_ya_no_entra(self):
        self.admin.is_active = False
        self.admin.save()

        self.assertFalse(self.client.login(username=self.admin.email, password=PASSWORD))
        self.assertEqual(self.client.get('/admin/').status_code, 302)


class ServicioDeUsuariosTests(TestCase):

    def usuario(self, rol, **extra):
        return Usuario(username=f'u_{rol}', email=f'{rol}@asistencia.test', rol=rol, **extra)

    def test_aplicar_rol(self):
        for rol, superusuario, staff in [(ADMINISTRADOR, False, True), (DOCENTE, False, False),
                                         (DOCENTE, True, True), (ADMINISTRADOR, True, True)]:
            with self.subTest(rol=rol, superusuario=superusuario):
                usuario = self.usuario(rol, is_superuser=superusuario, is_staff=not staff)
                aplicar_rol(usuario)
                self.assertEqual(usuario.is_staff, staff)

    def test_sincronizar_permisos_da_solo_los_tres_y_es_idempotente(self):
        administrador = Usuario.objects.create_user(
            username='adm', email='adm@asistencia.test', password=PASSWORD, rol=ADMINISTRADOR)
        extra = Permission.objects.get(codename='add_grupo')
        administrador.user_permissions.add(extra)

        sincronizar_permisos(administrador)
        sincronizar_permisos(administrador)

        self.assertEqual(permisos_de(administrador), set(CODIGOS_DE_PERMISO_DEL_ADMINISTRADOR))

    def test_sincronizar_permisos_de_un_docente_quita_los_de_usuarios_y_respeta_otros(self):
        docente = crear_docente()
        usuarios = Permission.objects.filter(codename__in=CODIGOS_DE_PERMISO_DEL_ADMINISTRADOR)
        otro = Permission.objects.get(codename='view_grupo')
        docente.user_permissions.add(*usuarios, otro)

        sincronizar_permisos(docente)

        self.assertEqual(permisos_de(docente), {'view_grupo'})

    def test_validar_cambio(self):
        unico = Usuario.objects.create_user(
            username='unico', email='unico@asistencia.test', password=PASSWORD, rol=ADMINISTRADOR)
        otro = Usuario.objects.create_user(
            username='otro', email='otro@asistencia.test', password=PASSWORD, rol=DOCENTE)

        # Un alta no puede dejar al sistema sin administradores.
        validar_cambio(Usuario(), DOCENTE, False, None)
        # Seguir siendo administrador activo está bien.
        validar_cambio(unico, ADMINISTRADOR, True, otro)
        # Cambiar a un docente no afecta a los administradores.
        validar_cambio(otro, DOCENTE, False, unico)
        # Pero el último administrador no puede dejar de serlo ni desactivarse.
        with self.assertRaisesRegex(ErrorDeUsuario, 'último administrador'):
            validar_cambio(unico, DOCENTE, True, otro)
        with self.assertRaisesRegex(ErrorDeUsuario, 'último administrador'):
            validar_cambio(unico, ADMINISTRADOR, False, otro)
        # Nadie se desactiva a sí mismo.
        with self.assertRaisesRegex(ErrorDeUsuario, 'ti mismo'):
            validar_cambio(otro, DOCENTE, False, otro)


class SeedDemoTests(TestCase):

    def test_el_administrador_de_demo_queda_con_acceso_solo_a_usuarios(self):
        call_command('seed_demo', verbosity=0)
        call_command('seed_demo', verbosity=0)          # repetible

        admin = Usuario.objects.get(email='admin@asistencia.test')
        self.assertTrue(admin.is_staff)
        self.assertEqual(permisos_de(admin), set(CODIGOS_DE_PERMISO_DEL_ADMINISTRADOR))
        for correo in ('docente1@asistencia.test', 'docente2@asistencia.test'):
            docente = Usuario.objects.get(email=correo)
            self.assertFalse(docente.is_staff)
            self.assertEqual(permisos_de(docente), set())
        self.assertEqual(Usuario.objects.count(), 3)
