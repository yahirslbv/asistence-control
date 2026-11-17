#!/usr/bin/env bash
# Prueba de restauración del respaldo (RNF-08). Una copia que no se ha
# restaurado no es una copia.
#
#   scripts/probar_restauracion.sh                  # la copia más reciente
#   scripts/probar_restauracion.sh respaldos/db_2026-11-20_0300.sql.gz
#
# Restaura el volcado, como root, en una base temporal (restauracion_prueba) y
# comprueba que:
#   1. cada tabla tiene las mismas filas que la base real;
#   2. el disparador de la bitácora existe en la copia y su dueño (DEFINER)
#      existe en este servidor; si no existiera, todo UPDATE sobre la
#      asistencia fallaría con el error 1449;
#   3. un UPDATE de `estado` sobre la copia funciona y escribe en la bitácora
#      (dentro de una transacción que se deshace);
#   4. la copia de media/ del mismo momento se puede leer.
# Al terminar elimina solo la base temporal. No modifica la base real.
#
# Córrelo justo después de scripts/respaldo.sh: si alguien registra asistencia
# entre la copia y la prueba, los conteos difieren aunque la copia esté bien.
# Funciona en Linux y en Git Bash (Windows).
set -euo pipefail

# Git Bash convierte los argumentos que parecen rutas de Linux; aquí no debe.
export MSYS_NO_PATHCONV=1

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && { pwd -W 2>/dev/null || pwd; })"
COMPOSE=(docker compose -f "$RAIZ/docker-compose.prod.yml" -p control_asistencia_prod)
DESTINO="${RESPALDOS_DIR:-$RAIZ/respaldos}"
TEMPORAL="restauracion_prueba"
TABLAS="usuario periodo grupo alumno inscripcion sesion asistencia bitacora_cambio"

volcado="${1:-}"
if [ -z "$volcado" ]; then
    volcado="$(find "$DESTINO" -maxdepth 1 -type f -name 'db_*.sql.gz' | sort | tail -n 1)"
fi
if [ -z "$volcado" ] || [ ! -s "$volcado" ]; then
    echo "ERROR: no hay ningún volcado db_*.sql.gz en $DESTINO. Ejecuta antes scripts/respaldo.sh." >&2
    exit 1
fi
echo "Volcado a probar: $volcado"

# Ejecuta SQL como root dentro del contenedor `db`. El SQL llega por la entrada
# estándar y la contraseña sale del entorno del contenedor.
sql_root() {
    "${COMPOSE[@]}" exec -T db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot -N -B "$@"' sh "$@"
}

base_real="$("${COMPOSE[@]}" exec -T db sh -c 'printf %s "$DB_NAME"' < /dev/null)"
if [ -z "$base_real" ] || [ "$base_real" = "$TEMPORAL" ]; then
    echo "ERROR: no se pudo leer DB_NAME, o la base real se llama $TEMPORAL. No se toca nada." >&2
    exit 1
fi

duenio=""          # dueño del disparador al que se le dieron permisos temporales
limpiar() {
    if [ -n "$duenio" ]; then
        echo "REVOKE ALL PRIVILEGES ON \`$TEMPORAL\`.* FROM $duenio;" | sql_root > /dev/null 2>&1 || true
    fi
    echo "DROP DATABASE IF EXISTS \`$TEMPORAL\`;" | sql_root > /dev/null 2>&1 || true
}
trap limpiar EXIT

fallos=0
fallo() { echo "   FALLA: $1" >&2; fallos=$((fallos + 1)); }

echo "DROP DATABASE IF EXISTS \`$TEMPORAL\`;
      CREATE DATABASE \`$TEMPORAL\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" | sql_root

echo "Restaurando como root en la base temporal $TEMPORAL..."
gzip -dc "$volcado" | sql_root "$TEMPORAL"

echo "1. Filas por tabla (base real / copia restaurada)"
for tabla in $TABLAS; do
    real="$(echo "SELECT COUNT(*) FROM \`$base_real\`.\`$tabla\`;" | sql_root)"
    copia="$(echo "SELECT COUNT(*) FROM \`$TEMPORAL\`.\`$tabla\`;" | sql_root)"
    printf '   %-16s %6s / %-6s\n' "$tabla" "$real" "$copia"
    [ "$real" = "$copia" ] || fallo "la tabla $tabla tiene $real filas en la base real y $copia en la copia."
done

echo "2. Disparador de la bitácora en la copia"
definer="$(echo "SELECT DEFINER FROM information_schema.TRIGGERS
                 WHERE TRIGGER_SCHEMA = '$TEMPORAL' AND TRIGGER_NAME = 'trg_asistencia_bitacora';" | sql_root)"
existe=0
if [ -z "$definer" ]; then
    fallo "el disparador trg_asistencia_bitacora no existe en la copia."
else
    echo "   trg_asistencia_bitacora, dueño: $definer"
    existe="$(echo "SELECT COUNT(*) FROM mysql.user WHERE CONCAT(user, '@', host) = '$definer';" | sql_root)"
    if [ "$existe" = "1" ]; then
        echo "   El dueño existe en este servidor."
    else
        fallo "el dueño del disparador ($definer) no existe en este servidor: todo UPDATE sobre la asistencia fallaría con el error 1449. Levanta la pila con el mismo .env.prod antes de restaurar."
    fi
fi

echo "3. UPDATE de estado sobre la copia (con ROLLBACK)"
registros="$(echo "SELECT COUNT(*) FROM \`$TEMPORAL\`.asistencia WHERE justificante IS NULL OR justificante = '';" | sql_root)"
if [ "$existe" != "1" ]; then
    fallo "no se probó el UPDATE: el disparador o su dueño no existen."
elif [ "$registros" = "0" ]; then
    fallo "la copia no tiene registros de asistencia sin justificante: no se pudo probar el UPDATE."
else
    # El disparador corre con los permisos de su dueño, y ese usuario solo los
    # tiene sobre la base real: sin permisos sobre la temporal, el UPDATE falla
    # con el error 1142. Se le dan aquí y se le quitan al terminar.
    duenio="'${definer%@*}'@'${definer##*@}'"
    echo "GRANT ALL PRIVILEGES ON \`$TEMPORAL\`.* TO $duenio;" | sql_root
    resultado="$(echo "
        START TRANSACTION;
        SELECT COUNT(*) INTO @antes FROM bitacora_cambio;
        SELECT MIN(id_asistencia) INTO @id FROM asistencia WHERE justificante IS NULL OR justificante = '';
        UPDATE asistencia SET estado = IF(estado = 'presente', 'ausente', 'presente') WHERE id_asistencia = @id;
        SELECT COUNT(*) INTO @despues FROM bitacora_cambio;
        ROLLBACK;
        SELECT @despues - @antes;" | sql_root "$TEMPORAL" 2>&1)" || true
    if [ "$resultado" = "1" ]; then
        echo "   El UPDATE funcionó y el disparador escribió 1 fila en la bitácora (deshecha con ROLLBACK)."
    else
        fallo "el UPDATE de estado sobre la copia no escribió en la bitácora: $resultado"
    fi
fi

echo "4. Copia de media/ del mismo momento"
media="${volcado%/*}/media_$(basename "$volcado" .sql.gz | sed 's/^db_//').tar.gz"
if [ -s "$media" ]; then
    archivos="$(tar -tzf - < "$media" | grep -c -v '/$' || true)"
    echo "   $(basename "$media"): se lee completa, $archivos archivo(s)."
else
    fallo "no existe la copia de media/ del mismo momento ($(basename "$media"))."
fi

if [ "$fallos" -gt 0 ]; then
    echo "RESULTADO: la prueba de restauración FALLÓ ($fallos problema(s))." >&2
    exit 1
fi
echo "RESULTADO: la restauración de prueba coincide con la base real."
