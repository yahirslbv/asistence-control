"""Configuración del Sistema de Control de Asistencia.

Los datos sensibles y los que cambian por entorno se leen del archivo .env
(ver .env.example).
"""

import os
from pathlib import Path

from django.contrib.messages import constants as mensajes
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def lista_del_entorno(nombre, por_defecto=''):
    """Valores de una variable de entorno separados por comas, sin vacíos."""
    return [
        valor.strip()
        for valor in os.environ.get(nombre, por_defecto).split(',')
        if valor.strip()
    ]


DEBUG = os.environ.get('DJANGO_DEBUG', '0') == '1'

# Clave secreta. Con DEBUG apagado (producción) es obligatoria y no puede ser la
# de los archivos de ejemplo, que es pública: la aplicación se niega a arrancar
# antes que firmar las sesiones con ella. En desarrollo se tolera para no estorbar.
CLAVE_DE_EJEMPLO = 'cambia-esto'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if not DEBUG and (not SECRET_KEY or CLAVE_DE_EJEMPLO in SECRET_KEY.lower()):
    raise ImproperlyConfigured(
        'Falta DJANGO_SECRET_KEY o tiene el valor de un archivo de ejemplo. '
        'Con DJANGO_DEBUG=0 la aplicación no arranca sin una clave propia, '
        'larga y aleatoria (se define en .env o en .env.prod).'
    )
SECRET_KEY = SECRET_KEY or CLAVE_DE_EJEMPLO

ALLOWED_HOSTS = lista_del_entorno('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')

# Orígenes de confianza para los formularios, con esquema (https://midominio.com).
CSRF_TRUSTED_ORIGINS = lista_del_entorno('DJANGO_CSRF_TRUSTED_ORIGINS')

# HTTPS. DJANGO_HTTPS=1 solo cuando el sitio se sirve por HTTPS (un dominio real
# detrás del proxy). En la demostración local por HTTP va en 0: con cookies
# «solo HTTPS» nadie podría iniciar sesión.
if os.environ.get('DJANGO_HTTPS', '0') == '1':
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Detrás del proxy Django recibe HTTP; el proxy avisa con esta cabecera que
    # el visitante llegó por HTTPS. Es seguro porque solo el proxy llega a la
    # aplicación (gunicorn no publica puertos).
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # HSTS empieza bajo (una hora) y se sube después: uno largo en un dominio
    # de prueba es difícil de revertir. La redirección de HTTP a HTTPS la hace
    # el proxy, por eso no se activa SECURE_SSL_REDIRECT.
    SECURE_HSTS_SECONDS = 3600


INSTALLED_APPS = [
    # `asistencia` va antes que el admin para que sus plantillas (admin/base_site.html)
    # y su hoja de estilos del admin tengan prioridad sobre las de Django.
    'asistencia',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Base de datos: MySQL 8 con InnoDB. El disparador de la bitácora (migración
# 0002) está escrito para MySQL, así que no hay respaldo en SQLite.
# La sesión de MySQL se fija en UTC porque Django guarda las fechas en UTC y
# el disparador usa NOW(); así ambos escriben en la misma zona.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'control_asistencia'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES', time_zone='+00:00'",
        },
    }
}


# Autenticación: el usuario entra con su correo institucional.
AUTH_USER_MODEL = 'asistencia.Usuario'
AUTHENTICATION_BACKENDS = ['asistencia.backends.EmailBackend']

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'inicio'
LOGOUT_REDIRECT_URL = 'login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'es-mx'

TIME_ZONE = 'America/Tijuana'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Bootstrap nombra "danger" a la alerta de error.
MESSAGE_TAGS = {mensajes.ERROR: 'danger'}


# Porcentaje mínimo de asistencia (supuesto sin confirmar; ver README).
ASISTENCIA_MINIMA = int(os.environ.get('ASISTENCIA_MINIMA', 80))

# Dominios de correo que pueden registrarse solos (RF-19), separados por comas. Quien se
# registra espera la aprobación de un administrador; el dominio solo filtra de entrada.
REGISTRO_DOMINIOS = [
    dominio.strip().lower()
    for dominio in os.environ.get('REGISTRO_DOMINIOS', 'uabc.edu.mx').split(',')
    if dominio.strip()
]
