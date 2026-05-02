FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

ENV CHROMIUM_FLAGS="--no-sandbox"

# Instalar Chromium + dependencias compatibles con Debian Trixie
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    libnss3 \
    libxi6 \
    libxcursor1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2t64 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcups2 \
    libxcomposite1 \
    libxfixes3 \
    libxrender1 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements primero (optimiza caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar solo lo estrictamente necesario
COPY Config.py .
COPY src/tasks/      ./src/tasks/ 
COPY main_Recoleccion.py .
COPY main_generacion.py .

# Verificar instalación
RUN chromium --version && chromedriver --version

CMD ["python", "main_Recoleccion.py"]