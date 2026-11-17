# Respaldo diario de la base de datos y de los justificantes (RNF-08), en Windows.
# Hace lo mismo que scripts/respaldo.sh; funciona con Windows PowerShell 5.1.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\respaldo.ps1
#
# Genera en respaldos\ (o en la carpeta de RESPALDOS_DIR):
#   db_AAAA-MM-DD_HHMM.sql.gz      volcado de la base (mysqldump)
#   media_AAAA-MM-DD_HHMM.tar.gz   carpeta media/ (justificantes)
# y conserva las 14 copias más recientes de cada tipo.
#
# Si algo falla, el script sale con error y NO borra copias antiguas.
#
# PowerShell 5.1 altera los datos binarios que pasan por una tubería, así que
# cada copia se comprime dentro del contenedor y se trae con `docker compose cp`.
# Por lo mismo, los comandos que corren dentro del contenedor no llevan comillas
# dobles (PowerShell 5.1 las pierde al pasarlas a un programa).

$ErrorActionPreference = 'Stop'

$Raiz = Split-Path -Parent $PSScriptRoot
$Compose = @('compose', '-f', (Join-Path $Raiz 'docker-compose.prod.yml'), '-p', 'control_asistencia_prod')
$Destino = if ($env:RESPALDOS_DIR) { $env:RESPALDOS_DIR } else { Join-Path $Raiz 'respaldos' }
$Conservar = 14

function Invoke-Compose {
    # Ejecuta `docker compose ...` y detiene el script si termina con error.
    & docker @Compose @args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($args -join ' ') terminó con el código $LASTEXITCODE."
    }
}

function Copy-DesdeContenedor {
    param([string]$Servicio, [string]$Origen, [string]$Final)
    # Se trae con un nombre provisional: un archivo a medias nunca queda con
    # nombre de copia buena.
    $parcial = "$Final.parcial"
    try {
        Invoke-Compose cp "${Servicio}:$Origen" $parcial
        if ((Get-Item -LiteralPath $parcial).Length -eq 0) {
            throw "La copia $Origen llegó vacía."
        }
        Move-Item -LiteralPath $parcial -Destination $Final -Force
    }
    finally {
        if (Test-Path -LiteralPath $parcial) { Remove-Item -LiteralPath $parcial -Force }
        & docker @Compose exec -T $Servicio rm -f $Origen | Out-Null
    }
}

New-Item -ItemType Directory -Force -Path $Destino | Out-Null

$marca = Get-Date -Format 'yyyy-MM-dd_HHmm'
$archivoDb = Join-Path $Destino "db_$marca.sql.gz"
$archivoMedia = Join-Path $Destino "media_$marca.tar.gz"

# 1. Base de datos. mysqldump corre dentro del contenedor `db`, con el usuario
#    de la aplicación y la contraseña de su propio entorno (en MYSQL_PWD, no en
#    la línea de comandos). --no-tablespaces: ese usuario no tiene PROCESS.
#    La última línea de mysqldump es «-- Dump completed»: sin ella, el volcado
#    está vacío o truncado y el comando falla.
$volcar = 'set -o pipefail; export MYSQL_PWD=$DB_PASSWORD; ' +
    'mysqldump --single-transaction --routines --triggers --no-tablespaces -u $DB_USER $DB_NAME ' +
    '| gzip > /tmp/respaldo_db.sql.gz ' +
    '&& gzip -dc /tmp/respaldo_db.sql.gz | tail -n 1 | grep -q Dump.completed'
try {
    Invoke-Compose exec -T db bash -c $volcar
}
catch {
    & docker @Compose exec -T db rm -f /tmp/respaldo_db.sql.gz | Out-Null
    throw 'El volcado de la base falló o quedó incompleto. No se borró ninguna copia.'
}
Copy-DesdeContenedor -Servicio 'db' -Origen '/tmp/respaldo_db.sql.gz' -Final $archivoDb

# 2. Justificantes: la carpeta media/ del contenedor `web`.
$empacar = 'tar -czf /tmp/respaldo_media.tar.gz -C /app media && tar -tzf /tmp/respaldo_media.tar.gz > /dev/null'
try {
    Invoke-Compose exec -T web sh -c $empacar
}
catch {
    & docker @Compose exec -T web rm -f /tmp/respaldo_media.tar.gz | Out-Null
    throw 'La copia de media/ falló. No se borró ninguna copia.'
}
Copy-DesdeContenedor -Servicio 'web' -Origen '/tmp/respaldo_media.tar.gz' -Final $archivoMedia

Write-Output "Respaldo listo: db_$marca.sql.gz y media_$marca.tar.gz en $Destino"

# 3. Retención. Solo se llega aquí si las dos copias nuevas están completas.
#    Solo toca archivos db_* y media_* de la carpeta de respaldos; el nombre
#    lleva la fecha, así que el orden alfabético es el cronológico.
foreach ($patron in 'db_*.sql.gz', 'media_*.tar.gz') {
    Get-ChildItem -LiteralPath $Destino -File -Filter $patron |
        Sort-Object Name -Descending |
        Select-Object -Skip $Conservar |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force
            Write-Output "Copia antigua eliminada: $($_.Name)"
        }
}
