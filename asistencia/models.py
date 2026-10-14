"""Modelos del Sistema de Control de Asistencia.

Requiere Django 5.1 o superior: CheckConstraint usa el argumento `condition`.
En versiones anteriores el argumento se llama `check=`.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Usuario(AbstractUser):
    """Docentes y administradores. Extiende AbstractUser para no reimplementar
    el hash de contrasena, el inicio de sesion ni el sistema de permisos."""

    class Rol(models.TextChoices):
        DOCENTE = 'docente', 'Docente'
        ADMINISTRADOR = 'administrador', 'Administrador'

    email = models.EmailField('correo institucional', unique=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.DOCENTE)

    class Meta:
        db_table = 'usuario'
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def __str__(self):
        return self.get_full_name() or self.username


class Alumno(models.Model):
    """Padron de alumnos, independiente del grupo en que esten inscritos."""

    id_alumno = models.AutoField(primary_key=True)
    matricula = models.CharField(max_length=15, unique=True)
    nombre = models.CharField(max_length=120)
    correo = models.EmailField(max_length=120, blank=True, null=True)

    class Meta:
        db_table = 'alumno'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.matricula} - {self.nombre}'


class Grupo(models.Model):
    """Grupo que imparte un docente en un periodo determinado."""

    id_grupo = models.AutoField(primary_key=True)
    clave = models.CharField(max_length=20)
    materia = models.CharField(max_length=120)
    periodo = models.CharField(max_length=10)
    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,      # RNF-05: no se borra un usuario con historial
        db_column='id_usuario',
        related_name='grupos',
    )

    class Meta:
        db_table = 'grupo'
        ordering = ['periodo', 'clave']
        constraints = [
            models.UniqueConstraint(
                fields=['clave', 'periodo'],
                name='uq_grupo_clave_periodo',
            ),
        ]

    def __str__(self):
        return f'{self.clave} ({self.periodo})'


class Inscripcion(models.Model):
    """Resuelve la relacion muchos a muchos entre grupo y alumno."""

    id_inscripcion = models.AutoField(primary_key=True)
    grupo = models.ForeignKey(
        Grupo, on_delete=models.CASCADE, db_column='id_grupo',
        related_name='inscripciones',
    )
    alumno = models.ForeignKey(
        Alumno, on_delete=models.PROTECT, db_column='id_alumno',
        related_name='inscripciones',
    )
    fecha_alta = models.DateField()

    class Meta:
        db_table = 'inscripcion'
        constraints = [
            # RF-05: impide inscribir dos veces al mismo alumno en el mismo grupo
            models.UniqueConstraint(
                fields=['grupo', 'alumno'],
                name='uq_inscripcion_grupo_alumno',
            ),
        ]
        indexes = [
            models.Index(fields=['alumno'], name='ix_inscripcion_alumno'),
        ]

    def __str__(self):
        return f'{self.alumno} en {self.grupo}'


class Sesion(models.Model):
    """Cada clase programada de un grupo."""

    class Estado(models.TextChoices):
        PROGRAMADA = 'programada', 'Programada'
        REALIZADA = 'realizada', 'Realizada'
        CANCELADA = 'cancelada', 'Cancelada'

    id_sesion = models.AutoField(primary_key=True)
    grupo = models.ForeignKey(
        Grupo, on_delete=models.CASCADE, db_column='id_grupo',
        related_name='sesiones',
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PROGRAMADA,
    )

    class Meta:
        db_table = 'sesion'
        ordering = ['fecha', 'hora_inicio']
        constraints = [
            # RF-06: impide programar dos veces la misma sesion
            models.UniqueConstraint(
                fields=['grupo', 'fecha', 'hora_inicio'],
                name='uq_sesion_grupo_fecha_hora',
            ),
            models.CheckConstraint(
                condition=Q(hora_fin__gt=F('hora_inicio')),
                name='ck_sesion_horas',
            ),
        ]
        # sesion(grupo, fecha) no lleva indice propio: es el prefijo de
        # uq_sesion_grupo_fecha_hora y MySQL ya lo usa para esa consulta.

    def __str__(self):
        return f'{self.grupo} - {self.fecha}'


class Asistencia(models.Model):
    """Registro de un alumno en una sesion. Tabla central del sistema."""

    class Estado(models.TextChoices):
        PRESENTE = 'presente', 'Presente'
        RETARDO = 'retardo', 'Retardo'
        AUSENTE = 'ausente', 'Ausente'
        JUSTIFICADO = 'justificado', 'Justificado'

    CUENTAN_COMO_ASISTENCIA = (Estado.PRESENTE, Estado.RETARDO, Estado.JUSTIFICADO)

    id_asistencia = models.AutoField(primary_key=True)
    sesion = models.ForeignKey(
        Sesion, on_delete=models.CASCADE, db_column='id_sesion',
        related_name='asistencias',
    )
    alumno = models.ForeignKey(
        Alumno, on_delete=models.PROTECT, db_column='id_alumno',
        related_name='asistencias',
    )
    estado = models.CharField(max_length=12, choices=Estado.choices)
    hora_registro = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='id_usuario', related_name='asistencias_registradas',
    )
    justificante = models.FileField(
        upload_to='justificantes/', blank=True, null=True,
    )

    class Meta:
        db_table = 'asistencia'
        constraints = [
            # RF-09: un alumno no puede tener dos registros en la misma sesion.
            # Es la regla que impide por diseno el error detectado en la entrevista.
            models.UniqueConstraint(
                fields=['sesion', 'alumno'],
                name='uq_asistencia_sesion_alumno',
            ),
            # RF-12: solo un registro justificado admite justificante
            models.CheckConstraint(
                condition=Q(justificante='') | Q(justificante__isnull=True)
                          | Q(estado='justificado'),
                name='ck_asistencia_justificante',
            ),
        ]
        indexes = [
            models.Index(fields=['alumno'], name='ix_asistencia_alumno'),
        ]

    def clean(self):
        if self.justificante and self.estado != self.Estado.JUSTIFICADO:
            raise ValidationError(
                {'justificante': 'Solo se puede adjuntar un justificante a un '
                                 'registro marcado como justificado.'}
            )

    def __str__(self):
        return f'{self.alumno} - {self.sesion} - {self.get_estado_display()}'


class BitacoraCambio(models.Model):
    """Historial de correcciones de asistencia (RF-11 y RNF-06).

    Solo admite inserciones: si se pudiera editar o borrar dejaria de servir
    como evidencia en una aclaracion de faltas. Las filas las escribe un
    disparador de la base de datos, definido en la migracion 0002.
    """

    id_bitacora = models.AutoField(primary_key=True)
    asistencia = models.ForeignKey(
        Asistencia, on_delete=models.CASCADE, db_column='id_asistencia',
        related_name='cambios',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='id_usuario', related_name='correcciones',
    )
    valor_anterior = models.CharField(max_length=12, choices=Asistencia.Estado.choices)
    valor_nuevo = models.CharField(max_length=12, choices=Asistencia.Estado.choices)
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bitacora_cambio'
        ordering = ['-fecha_cambio']
        constraints = [
            models.CheckConstraint(
                condition=~Q(valor_anterior=F('valor_nuevo')),
                name='ck_bitacora_cambio_real',
            ),
        ]
        indexes = [
            models.Index(fields=['asistencia'], name='ix_bitacora_asistencia'),
        ]

    def __str__(self):
        return f'{self.asistencia_id}: {self.valor_anterior} -> {self.valor_nuevo}'
