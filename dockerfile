FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV CHROMIUM_FLAGS="--no-sandbox"
# Decirle a Selenium dónde está Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    # Librerías del renderer que faltaban
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    libxi6 \
    libxcursor1 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    fonts-liberation \
    xdg-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

#COPY Config.py .
#COPY src/tasks/          ./src/tasks/
#COPY main_Recoleccion.py .
#COPY main_generacion.py .

RUN chromium --version && chromedriver --version

CMD ["python", "main_Recoleccion.py"]