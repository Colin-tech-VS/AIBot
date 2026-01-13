FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUTO_TRAIN=0 \
    DEV_RELOAD=0 \
    HOST=0.0.0.0 \
    PORT=8001 \
    OLLAMA_URL=http://host.docker.internal:11434

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le code de l’application
COPY . /app

EXPOSE 8001

CMD ["python", "app.py"]