FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    curl \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descargar modelo Whisper base (74 MB, evita descarga en runtime)
RUN python -c "import whisper; whisper.load_model('base')"

# Copiar proyecto
COPY . .

# Configurar nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Directorios de trabajo
RUN mkdir -p /data/projects /data/proyectos

# Variables de entorno para HF Spaces
ENV STORAGE_DIR=/data
ENV SUBTITULOS_FONT_PATH=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf
ENV GATEWAY_URL=http://localhost:7861

# Puerto externo de HF Spaces
EXPOSE 7860

# Lanzar todo
COPY start.sh .
RUN chmod +x start.sh
CMD ["./start.sh"]
