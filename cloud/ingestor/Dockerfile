# Imagem do ingestor cloud (MQTT remoto -> TimescaleDB).
FROM python:3.12-slim

# Não gera .pyc e não bufferiza stdout (logs aparecem na hora em `docker logs`).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências primeiro para aproveitar o cache de camadas do Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["python", "main.py"]
