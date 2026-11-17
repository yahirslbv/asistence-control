# Levanta la demostración local con un solo comando (Windows con Docker Desktop).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo.ps1
#
# La primera vez crea .env.prod a partir de .env.prod.example, con una clave y
# contraseñas aleatorias (el archivo no se versiona). Después construye la
# imagen y levanta la pila de docker-compose.prod.yml en http://localhost.
#
# Es la misma pila que serviría en un servidor; lo único propio de la
# demostración es que el sitio se atiende por HTTP y en este equipo.

$ErrorActionPreference = 'Stop'

$Raiz = Split-Path -Parent $PSScriptRoot
$Entorno = Join-Path $Raiz '.env.prod'
$Ejemplo = Join-Path $Raiz '.env.prod.example'
$Pila = Join-Path $Raiz 'docker-compose.prod.yml'
$VolumenDeLaBase = 'control_asistencia_prod_mysql_data'

function New-Secreto {
    # Letras y números al azar (sin símbolos, para que el valor no necesite comillas).
    param([int]$Largo = 64)
    $alfabeto = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
    $bytes = New-Object byte[] $Largo
    $generador = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generador.GetBytes($bytes) } finally { $generador.Dispose() }
    return -join ($bytes | ForEach-Object { $alfabeto[$_ % $alfabeto.Length] })
}

if (-not (Test-Path -LiteralPath $Entorno)) {
    # MySQL solo toma las contraseñas la primera vez que arranca su volumen. Si
    # el volumen ya existe y se perdió .env.prod, unas contraseñas nuevas no
    # entrarían: es mejor avisar que dejar una pila que no arranca.
    $existentes = @(& docker volume ls --quiet --filter "name=^$VolumenDeLaBase$")
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo hablar con Docker. Abre Docker Desktop y vuelve a intentarlo.'
    }
    if ($existentes -contains $VolumenDeLaBase) {
        throw ("Ya existe una base de datos de esta pila (volumen $VolumenDeLaBase) pero falta " +
            '.env.prod, que guarda sus contraseñas. Recupera ese archivo y ponlo en la carpeta del ' +
            'proyecto. Si la base no tiene nada que conservar, bórrala con ' +
            "'docker volume rm $VolumenDeLaBase' (con la pila apagada) y vuelve a ejecutar este script.")
    }
    $lineas = Get-Content -LiteralPath $Ejemplo -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^(DJANGO_SECRET_KEY|MYSQL_ROOT_PASSWORD|DB_PASSWORD)=CAMBIA-ESTO\s*$') {
            "$($Matches[1])=$(New-Secreto)"
        }
        else { $_ }
    }
    # UTF-8 sin BOM: Docker Compose no entiende el BOM que agrega PowerShell 5.1.
    [System.IO.File]::WriteAllLines($Entorno, $lineas, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output 'Se creó .env.prod con una clave y contraseñas nuevas. No lo subas a Git ni lo borres.'
}

& docker compose -f $Pila up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "La pila no arrancó. Revisa los registros con: docker compose -f docker-compose.prod.yml logs"
}

Write-Output ''
Write-Output 'Listo. Abre http://localhost (no 127.0.0.1: el proxy solo atiende ese nombre).'
Write-Output 'Para apagarla, sin perder los datos: docker compose -f docker-compose.prod.yml down'
