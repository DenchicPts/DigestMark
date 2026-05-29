FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY index.html .

ENV MODEL_SIZE=large-v3-turbo
ENV DEVICE=cpu
ENV LANGUAGE=
ENV CPU_THREADS=0

# Папка для моделей — сюда маппится volume из docker-compose
RUN mkdir -p /models

EXPOSE 9000

CMD ["python", "app.py"]
