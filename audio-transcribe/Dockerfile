FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Ставим PyTorch CPU-only — отдельным слоем для кэша
RUN pip install --no-cache-dir \
    torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
COPY constraints.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    --constraint constraints.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

COPY app.py .
COPY index.html .

ENV MODEL_SIZE=medium
ENV DEVICE=cpu
ENV LANGUAGE=
ENV CPU_THREADS=0
ENV BATCH_SIZE=1

EXPOSE 9000

CMD ["python", "app.py"]