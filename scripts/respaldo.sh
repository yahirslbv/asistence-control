#!/usr/bin/env bash
# Respaldo diario de la base de datos y de los justificantes (RNF-08).
#
#   scripts/respaldo.sh
#
# Genera en respaldos/ (o en la carpeta de RESPALDOS_DIR):
#   db_AAAA-MM-DD_HHMM.sql.gz      volcado de la base (mysqldump)
#   media_AAAA-MM-DD_HHMM.tar.gz   carpeta media/ (justificantes)
# y conserva las 14 copias más recientes de cada tipo.
#
# Programarlo con cron (todos los días a las 3:00):
#   0 3 * * * /ruta/al/proyecto/scripts/respaldo.sh >> /ruta/al/proyecto/respaldos/respaldo.log 2>&1
#
# Si algo falla, el script sale con error y NO borra copias antiguas.
# En Windows usa scripts/respaldo.ps1, que hace lo mismo.
set -euo pipefail

# Git Bash (Windows) convierte los argumentos que parecen rutas de Linux
# (/app pasaría a ser C:/Program Files/Git/app). Aquí no debe hacerlo.
export MSYS_NO_PATHCONV=1

# Carpeta del proyecto, en ruta absoluta: cron no hereda el directorio actual.
# `pwd -W` solo existe en Git Bash y da la ruta de Windows que entiende docker.
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && { pwd -W 2>/dev/null || pwd; })"
COMPOSE=(docker compose -f "$RAIZ/docker-compose.prod.yml" -p control_asistencia_prod)
DESTINO="${RESPALDOS_DIR:-$RAIZ/respaldos}"
CONSERVAR=14

# Las copias traen nombres y matrículas de alumnos: solo las lee su dueño.
umask 077
mkdir -p "$DESTINO"

marca="$(date +%Y-%m-%d_%H%M)"
archivo_db="$DESTINO/db_$marca.sql.gz"
archivo_media="$DESTINO/media_$marca.tar.gz"

# Un archivo a medias nunca queda con nombre de copia buena.
trap 'rm -f "$archivo_db.parcial" "$archivo_media.parcial"' EXIT

# 1. Base de datos. mysqldump corre dentro del contenedor `db`, con el usuario
#    de la aplicación y la contraseña de su propio entorno (en MYSQL_PWD, no en
#    la línea de comandos). --no-tablespaces: ese usuario no tiene PROCESS.
"${COMPOSE[@]}" exec -T db sh -c \
    'MYSQL_PWD="$DB_PASSWORD" exec mysqldump --single-transaction --routines --triggers --no-tablespaces -u "$DB_USER" "$DB_NAME"' \
    < /dev/null | gzip > "$archivo_db.parcial"

# mysqldump termina con la línea «-- Dump completed»: sin ella, el volcado
# está vacío o truncado.
if ! gzip -dc "$archivo_db.parcial" | tail -n 1 | grep -q 'Dump completed'; then
    echo "ERROR: el volcado de la base está vacío o incompleto. No se borró ninguna copia." >&2
    exit 1
fi
mv -f "$archivo_db.parcial" "$archivo_db"

# 2. Justificantes: la carpeta media/ del contenedor `web`.
"${COMPOSE[@]}" exec -T web sh -c 'exec tar -czf - -C /app media' \
    < /dev/null > "$archivo_media.parcial"

# Se lee por la entrada estándar: GNU tar toma «C:» por un equipo remoto.
if ! tar -tzf - < "$archivo_media.parcial" > /dev/null; then
    echo "ERROR: la copia de media/ está vacía o dañada. No se borró ninguna copia." >&2
    exit 1
fi
mv -f "$archivo_media.parcial" "$archivo_media"

echo "Respaldo listo: $(basename "$archivo_db") y $(basename "$archivo_media") en $DESTINO"

# 3. Retención. Solo se llega aquí si las dos copias nuevas están completas.
#    Solo toca archivos db_* y media_* de la carpeta de respaldos; el nombre
#    lleva la fecha, así que el orden alfabético es el cronológico.
depurar() {
    find "$DESTINO" -maxdepth 1 -type f -name "$1" | sort | head -n "-$CONSERVAR" \
        | while IFS= read -r antiguo; do
            rm -f -- "$antiguo"
            echo "Copia antigua eliminada: $(basename "$antiguo")"
        done
}
depurar 'db_*.sql.gz'
depurar 'media_*.tar.gz'
