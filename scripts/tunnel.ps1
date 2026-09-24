# ==============================================================================
# WhisperDnD - Mobile Remote Access & HTTPS Tunnel Launcher
# ==============================================================================
# Este script inicia un túnel HTTPS seguro (Cloudflare Tunnel o Localtunnel)
# para permitir que tu teléfono móvil o tableta se conecte a WhisperDnD,
# instale la aplicación como PWA y capture audio desde el micrófono del móvil.
# ==============================================================================

$Host.UI.RawUI.WindowTitle = "WhisperDnD - Túnel Móvil & PWA"

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "       WHISPER D&D / WORK & STUDY - ACCESO MÓVIL & TÚNEL        " -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Comprobar si el servidor local está activo en el puerto 8080
$serverActive = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $async = $tcp.BeginConnect("127.0.0.1", 8080, $null, $null)
    $success = $async.AsyncWaitHandle.WaitOne(800, $false)
    if ($success -and $tcp.Connected) {
        $serverActive = $true
        $tcp.EndConnect($async)
    }
    $tcp.Close()
} catch {
    $serverActive = $false
}

if ($serverActive) {
    Write-Host "[OK] Servidor local WhisperDnD detectado en http://localhost:8080" -ForegroundColor Green
} else {
    Write-Host "[AVISO] No se detectó un servidor activo en http://localhost:8080." -ForegroundColor Yellow
    Write-Host "        Asegúrate de iniciar el backend antes o en otra consola: (python main.py)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Selecciona el método de túnel HTTPS para conectar tu móvil:" -ForegroundColor White
Write-Host "  [1] Cloudflare Quick Tunnel (Recomendado - Gratuito, rápido, URL *.trycloudflare.com)" -ForegroundColor Yellow
Write-Host "  [2] Localtunnel (Requiere Node.js / npx - URL *.loca.lt)" -ForegroundColor Cyan
Write-Host "  [3] Abrir interfaz local en el navegador (http://localhost:8080)" -ForegroundColor Gray
Write-Host "  [Q] Salir" -ForegroundColor DarkGray
Write-Host ""

$choice = Read-Host "Elige una opción [1/2/3/Q] (Predeterminado: 1)"
if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "Iniciando Cloudflare Tunnel hacia http://localhost:8080..." -ForegroundColor Cyan
        $cfCmd = Get-Command cloudflared -ErrorAction SilentlyContinue
        if ($cfCmd) {
            Write-Host "Ejecutando: cloudflared tunnel --url http://localhost:8080" -ForegroundColor Green
            Write-Host "Busca la línea que contiene '*.trycloudflare.com' y ábrela en tu móvil." -ForegroundColor Yellow
            Write-Host ""
            & cloudflared tunnel --url http://localhost:8080
        } else {
            Write-Host "No se encontró el ejecutable 'cloudflared' en el PATH del sistema." -ForegroundColor Yellow
            Write-Host "Intentando lanzar mediante npx / localtunnel como alternativa automática..." -ForegroundColor Cyan
            npx -y localtunnel --port 8080
        }
    }
    "2" {
        Write-Host ""
        Write-Host "Iniciando localtunnel en el puerto 8080..." -ForegroundColor Cyan
        Write-Host "Ejecutando: npx -y localtunnel --port 8080" -ForegroundColor Green
        Write-Host "Abre la URL *.loca.lt en tu móvil e ingresa la IP pública si te lo solicita." -ForegroundColor Yellow
        Write-Host ""
        npx -y localtunnel --port 8080
    }
    "3" {
        Write-Host "Abriendo http://localhost:8080 en el navegador..." -ForegroundColor Cyan
        Start-Process "http://localhost:8080"
    }
    "Q" {
        Write-Host "Operación cancelada." -ForegroundColor Gray
        exit 0
    }
    default {
        Write-Host "Opción no reconocida. Iniciando localtunnel por defecto..." -ForegroundColor Yellow
        npx -y localtunnel --port 8080
    }
}
