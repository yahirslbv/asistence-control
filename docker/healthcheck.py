"""Comprobación de salud del contenedor `web`.

Pide la pantalla de acceso a gunicorn con un `Host` válido: el primero de
DJANGO_ALLOWED_HOSTS. Con `Host: 127.0.0.1` Django respondería 400 cuando
ALLOWED_HOSTS solo trae el dominio, y el servicio parecería caído sin estarlo.
"""

import os
import sys
import urllib.request


def host_valido():
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(','):
        host = host.strip().lstrip('.')
        if host and host != '*':
            return host
    return 'localhost'


def main():
    peticion = urllib.request.Request(
        'http://127.0.0.1:8000/login/', headers={'Host': host_valido()})
    try:
        with urllib.request.urlopen(peticion, timeout=5) as respuesta:
            return 0 if respuesta.status == 200 else 1
    except Exception as error:
        print(f'healthcheck: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
