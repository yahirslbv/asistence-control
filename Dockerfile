# Imagen de la aplicación (fase J, bloque B4 de docs/DESPLIEGUE.md).
#
# Dos etapas: la primera compila `mysqlclient` (necesita compilador y cabeceras)
# y la segunda solo lleva lo que hace falta para correr, sin esas herramientas.

FROM python:3.11-slim-trixie AS construccion

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r /tmp/requirements.txt \
    && /opt/venv/bin/pip check


FROM python:3.11-slim-trixie

# DJANGO_STATIC_MANIFEST=1: `collectstatic` (al construir) y `gunicorn` (al
# correr) usan el mismo almacenamiento de archivos estáticos, con huella.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_STATIC_MANIFEST=1

# Biblioteca cliente de MySQL (solo la de ejecución) y un usuario sin privilegios.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin asistencia

COPY --from=construccion /opt/venv /opt/venv

WORKDIR /app
COPY . /app

# La clave de esta línea es desechable: solo deja que `settings.py` se importe
# durante la construcción. No queda en la imagen; el contenedor usa la de .env.prod.
RUN sed -i 's/\r$//' /app/docker/entrypoint.sh \
    && chmod 755 /app/docker/entrypoint.sh \
    && DJANGO_DEBUG=0 DJANGO_SECRET_KEY=solo-para-construir-la-imagen \
        python manage.py collectstatic --noinput \
    && mkdir -p /app/media/justificantes \
    && chown -R asistencia:asistencia /app/media

USER asistencia

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
