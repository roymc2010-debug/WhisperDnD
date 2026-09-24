#!/usr/bin/env python3
"""
Dynamic HTTPS Mobile Tunnel Runner for Whisper AI.
Exposes localhost:8080 via Cloudflare Quick Tunnel (cloudflared) with zero configuration.
"""

import os
import re
import socket
import sys
import time
import shutil
import urllib.request
import subprocess
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent
CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    if sys.platform == "win32"
    else "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
)
BIN_DIR = PROJECT_ROOT / ".bin"
LOCAL_CLOUDFLARED = BIN_DIR / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")
PORT = 8080


def is_port_open(host: str = "127.0.0.1", port: int = PORT) -> bool:
    """Check if the given host/port is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def ensure_server_running() -> Optional[subprocess.Popen]:
    """Verify local server is responding; if not, spawn it in background."""
    if is_port_open():
        print(f"[+] Servidor WhisperDnD ya está corriendo en el puerto {PORT}.")
        return None

    print(f"[*] Iniciando servidor WhisperDnD en segundo plano (puerto {PORT})...")
    server_proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait up to 15 seconds for server to start
    for _ in range(30):
        time.sleep(0.5)
        if is_port_open():
            print(f"[+] Servidor WhisperDnD iniciado correctamente en http://127.0.0.1:{PORT}.")
            return server_proc

    print("[!] Advertencia: No se pudo verificar la apertura del puerto 8080 en 15s.")
    return server_proc


def resolve_cloudflared() -> str:
    """Find cloudflared in PATH, local .bin, or project root; download if missing."""
    # 1. System PATH
    which_bin = shutil.which("cloudflared") or shutil.which("cloudflared.exe")
    if which_bin:
        return which_bin

    # 2. Local bin or root
    if LOCAL_CLOUDFLARED.is_file():
        return str(LOCAL_CLOUDFLARED)

    root_bin = PROJECT_ROOT / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")
    if root_bin.is_file():
        return str(root_bin)

    # 3. Download standalone binary
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = LOCAL_CLOUDFLARED
    print(f"[*] 'cloudflared' no encontrado en el sistema.")
    print(f"[*] Descargando ejecutable oficial de Cloudflare Tunnel...")

    def _progress(count, block_size, total_size):
        if total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            mb_downloaded = (count * block_size) / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            sys.stdout.write(f"\r    Descargando: {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)...")
            sys.stdout.flush()

    try:
        req = urllib.request.Request(
            CLOUDFLARED_URL,
            headers={"User-Agent": "Mozilla/5.0 (WhisperAI-TunnelRunner)"},
        )
        with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out_file:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 65536
            while True:
                buf = resp.read(block_size)
                if not buf:
                    break
                out_file.write(buf)
                downloaded += len(buf)
                if total_size > 0:
                    percent = int(downloaded * 100 / total_size)
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    sys.stdout.write(f"\r    Descargando: {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)...")
                    sys.stdout.flush()

        print("\n[+] Descarga completada exitosamente.")
        if sys.platform != "win32":
            dest_path.chmod(0o755)
        return str(dest_path)
    except Exception as exc:
        if dest_path.exists():
            dest_path.unlink()
        print(f"\n[!] Error descargando cloudflared: {exc}")
        print("    Puedes descargarlo manualmente desde: https://github.com/cloudflare/cloudflared/releases")
        sys.exit(1)


def main():
    print("=" * 60)
    print(" 🛡️ Whisper AI - Lanzador de Túnel Móvil HTTPS (Cloudflare)")
    print("=" * 60)

    server_proc = ensure_server_running()
    cloudflared_bin = resolve_cloudflared()

    print(f"[*] Iniciando túnel seguro hacia http://127.0.0.1:{PORT}...")
    cmd = [cloudflared_bin, "tunnel", "--url", f"http://127.0.0.1:{PORT}"]

    # Run cloudflared; tunnel URL is output to stderr by cloudflared
    tunnel_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    url_found = False
    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    try:
        for line in tunnel_proc.stdout:
            # Check for tunnel URL in cloudflared logs
            if not url_found:
                match = url_pattern.search(line)
                if match:
                    tunnel_url = match.group(0)
                    url_found = True
                    print()
                    print("=" * 60)
                    print(" 📱 WHISPER AI - ACCESO MÓVIL SEGURO (HTTPS)")
                    print("=" * 60)
                    print(" Enlace para tu celular:")
                    print(f" 👉 {tunnel_url}")
                    print("=" * 60)
                    print("(Abre este enlace en tu navegador móvil para probar o instalar)")
                    print(" Presiona Ctrl+C para detener el túnel.")
                    print("=" * 60)
                    print()
    except KeyboardInterrupt:
        print("\n[*] Deteniendo túnel y servicios...")
    finally:
        try:
            tunnel_proc.terminate()
            tunnel_proc.wait(timeout=3)
        except Exception:
            tunnel_proc.kill()

        if server_proc:
            try:
                server_proc.terminate()
                server_proc.wait(timeout=3)
            except Exception:
                server_proc.kill()

        print("[+] Túnel cerrado correctamente.")


if __name__ == "__main__":
    main()
