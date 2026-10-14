"""Datos de demostración: 1 administrador, 2 docentes, 2 grupos y 40 alumnos.

Es idempotente: se puede ejecutar varias veces sin duplicar nada. Los 40
alumnos se reparten en dos grupos de 25, con 10 inscritos en ambos, para
mostrar que un alumno puede estar en varios grupos.

Solo sirve para desarrollo y pruebas manuales.
"""

import os
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from asistencia.models import Alumno, Grupo, Inscripcion

# Contraseña de las cuentas de demostración. Se puede cambiar con la variable
# de entorno SEED_PASSWORD.
PASSWORD_DEMO = 'Asistencia#2026'

PERIODO = '2026-2'

NOMBRES = [
    'Ana', 'Luis', 'María', 'Carlos', 'Sofía', 'Jorge', 'Valeria', 'Diego',
    'Fernanda', 'Andrés', 'Camila', 'Ricardo', 'Daniela', 'Mauricio', 'Paola',
    'Héctor', 'Regina', 'Iván', 'Lucía', 'Emilio',
]
APELLIDOS = [
    'García', 'Martínez', 'López', 'Hernández', 'Ramírez', 'Torres', 'Flores',
    'Rivera', 'Gómez', 'Díaz',
]

TOTAL_ALUMNOS = 40
MATRICULA_BASE = 1200000


class Command(BaseCommand):
    help = 'Crea datos de demostración (administrador, docentes, grupos y alumnos).'

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get('SEED_PASSWORD', PASSWORD_DEMO)
        Usuario = get_user_model()

        administrador = self._usuario(
            Usuario, 'admin@asistencia.test', 'Administrador', 'Demo',
            Usuario.Rol.ADMINISTRADOR, password,
        )
        self._permisos_de_administrador(administrador)
        docente1 = self._usuario(
            Usuario, 'docente1@asistencia.test', 'Elena', 'Ruiz',
            Usuario.Rol.DOCENTE, password,
        )
        docente2 = self._usuario(
            Usuario, 'docente2@asistencia.test', 'Marco', 'Salazar',
            Usuario.Rol.DOCENTE, password,
        )

        grupo_a, _ = Grupo.objects.get_or_create(
            clave='ADM-101', periodo=PERIODO,
            defaults={'materia': 'Administración de Proyectos de Software', 'docente': docente1},
        )
        grupo_b, _ = Grupo.objects.get_or_create(
            clave='BD-201', periodo=PERIODO,
            defaults={'materia': 'Bases de Datos', 'docente': docente2},
        )

        alumnos = [self._alumno(i) for i in range(TOTAL_ALUMNOS)]
        hoy = date.today()
        # Alumnos 0-24 en el grupo A; 15-39 en el grupo B (15-24 en ambos).
        for alumno in alumnos[:25]:
            Inscripcion.objects.get_or_create(
                grupo=grupo_a, alumno=alumno, defaults={'fecha_alta': hoy})
        for alumno in alumnos[15:]:
            Inscripcion.objects.get_or_create(
                grupo=grupo_b, alumno=alumno, defaults={'fecha_alta': hoy})

        self.stdout.write(self.style.SUCCESS(
            f'Listo: 3 usuarios, 2 grupos y {TOTAL_ALUMNOS} alumnos '
            f'(periodo {PERIODO}).'
        ))
        self.stdout.write(
            'Cuentas: admin@asistencia.test, docente1@asistencia.test y '
            'docente2@asistencia.test. La contraseña está en seed_demo.py '
            '(PASSWORD_DEMO) o en la variable SEED_PASSWORD.'
        )

    def _usuario(self, Usuario, correo, nombre, apellido, rol, password):
        usuario, _ = Usuario.objects.update_or_create(
            email=correo,
            defaults={
                'username': correo.split('@')[0],
                'first_name': nombre,
                'last_name': apellido,
                'rol': rol,
                'is_active': True,
                # El administrador entra al admin de Django para dar de alta usuarios.
                'is_staff': rol == Usuario.Rol.ADMINISTRADOR,
            },
        )
        usuario.set_password(password)
        usuario.save(update_fields=['password'])
        return usuario

    def _permisos_de_administrador(self, administrador):
        """El administrador solo gestiona usuarios (supuesto 5 del CLAUDE.md)."""
        permisos = Permission.objects.filter(
            content_type__app_label='asistencia',
            content_type__model='usuario',
            codename__in=['add_usuario', 'change_usuario', 'view_usuario'],
        )
        administrador.user_permissions.set(permisos)

    def _alumno(self, indice):
        nombre = NOMBRES[indice % len(NOMBRES)]
        apellido1 = APELLIDOS[indice % len(APELLIDOS)]
        apellido2 = APELLIDOS[(indice * 3 + 1) % len(APELLIDOS)]
        matricula = str(MATRICULA_BASE + indice)
        alumno, _ = Alumno.objects.update_or_create(
            matricula=matricula,
            defaults={
                'nombre': f'{nombre} {apellido1} {apellido2}',
                'correo': f'a{matricula}@asistencia.test',
            },
        )
        return alumno
