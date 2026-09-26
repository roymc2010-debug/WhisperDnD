# Dockerfile para Google Cloud Run - WhisperDnD & Study
FROM python:3.10-slim

# Evitar prompts interactivos y habilitar logs inmediatos
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    WHISPER_INPUT_DIR=/tmp \
    WHISPER_OUTPUT_DIR=/app/outputs \
    WHISPER_CAMPAIGNS_DIR=/app/data/campaigns

WORKDIR /app

# Instalar ffmpeg y bibliotecas del sistema operativo para procesamiento de audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libasound2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar la caché de capas de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código fuente del proyecto
COPY . .

# Crear y preparar los directorios de almacenamiento en el contenedor
RUN mkdir -p /app/outputs /app/data/campaigns /app/data/input /app/data/output /tmp

# Puerto por defecto (Cloud Run inyecta PORT dinámicamente)
EXPOSE 8080

# Enlace dinámico a 0.0.0.0 y lectura de variable de entorno PORT
CMD exec uvicorn src.api.server:app --host 0.0.0.0 --port ${PORT:-8080}
