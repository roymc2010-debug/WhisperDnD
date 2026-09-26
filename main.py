#!/usr/bin/env python3
"""Main launcher for WhisperDnD Localhost Web Application."""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(override=True)

import os
import json

# Support Google Credentials via Environment Variable (Render Docker / Cloud Run)
credentials_path = "/app/credentials.json"
env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")

if env_creds and not os.path.exists(credentials_path):
    try:
        os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
        with open(credentials_path, "w", encoding="utf-8") as f:
            f.write(env_creds)
        print(f"Archivo {credentials_path} generado con éxito desde variable de entorno.")
    except Exception as e:
        print(f"Error escribiendo credentials.json: {e}")


def main():
    try:
        import uvicorn
    except ImportError:
        print("[!] Error: 'uvicorn' is not installed.")
        print("    Please install the dependencies: pip install -r requirements.txt")
        sys.exit(1)

    import os
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8080))

    print("=" * 60)
    print(" WhisperDnD - Web Application Server")
    print("=" * 60)
    print(f" Starting server at: http://{host}:{port}")
    print(f" Accessible locally: http://localhost:{port}")
    print(f" Accessible on LAN:  http://127.0.0.1:{port}")
    print(" Press Ctrl+C to stop the server.")
    print("=" * 60)

    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
