"""Standalone CLI verification script for Google Drive OAuth and upload pipeline."""

import datetime
import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.storage.drive_client import GoogleDriveStorage, DEFAULT_FOLDER_NAME


def run_e2e_verification():
    print("=" * 65)
    print(" WhisperDnD - Google Drive OAuth & Upload Verification")
    print("=" * 65)

    credentials_path = project_root / "credentials.json"
    token_path = project_root / "token.json"
    output_dir = project_root / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Check credentials.json
    print(f"\n[1/4] Verificando archivo de credenciales...")
    if not credentials_path.is_file():
        print(f"❌ ERROR: No se encontró 'credentials.json' en {credentials_path}")
        print("   Por favor descarga el archivo de credenciales OAuth de tipo 'Desktop App'")
        print("   desde Google Cloud Console y colócalo en la raíz del proyecto.")
        sys.exit(1)
    print(f"✓ Archivo 'credentials.json' encontrado.")

    # 2. Check token.json
    print(f"\n[2/4] Verificando token de autenticación...")
    if token_path.is_file():
        print(f"✓ 'token.json' existente encontrado en {token_path}")
    else:
        print(f"ℹ️ 'token.json' no existe aún.")
        print("   Se abrirá tu navegador web predeterminado para iniciar sesión con Google")
        print("   y autorizar el acceso a Google Drive...")

    # 3. Authenticate
    try:
        drive_storage = GoogleDriveStorage(
            credentials_path=str(credentials_path),
            token_path=str(token_path),
        )
        print("   Conectando con Google Drive API...")
        drive_storage.authenticate()
        print(f"✓ Autenticación exitosa. 'token.json' guardado/actualizado.")
    except Exception as exc:
        print(f"❌ Error durante la autenticación de Google Drive: {exc}")
        sys.exit(1)

    # 4. Create test file and upload
    print(f"\n[3/4] Creando archivo de prueba local...")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_file_path = output_dir / f"verificacion_drive_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    test_content = (
        f"WhisperDnD - Verificación de Conexión con Google Drive\n"
        f"Fecha y hora: {now_str}\n"
        f"Carpeta destino: {DEFAULT_FOLDER_NAME}\n\n"
        f"Este es un archivo de prueba generado automáticamente para validar el flujo OAuth 2.0\n"
        f"y la carga exitosa de documentos en Google Drive.\n"
    )
    test_file_path.write_text(test_content, encoding="utf-8")
    print(f"✓ Archivo local creado en: {test_file_path}")

    print(f"\n[4/4] Subiendo archivo a la carpeta '{DEFAULT_FOLDER_NAME}' en Drive...")
    try:
        result = drive_storage.upload_file(str(test_file_path), folder_name=DEFAULT_FOLDER_NAME)
        print("\n" + "=" * 65)
        print(" 🎉 ¡SUBIDA A GOOGLE DRIVE COMPLETADA CON ÉXITO!")
        print("=" * 65)
        print(f"📁 Nombre en Drive: {result['file_name']}")
        print(f"🆔 ID de archivo:   {result['file_id']}")
        print(f"🔗 Enlace directo:  {result['web_view_link']}")
        print("=" * 65)
        print("Puedes hacer clic en el enlace superior para abrir el archivo en tu navegador.\n")
    except Exception as exc:
        print(f"❌ Error al subir el archivo a Google Drive: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    run_e2e_verification()
