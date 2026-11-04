# Atlas: Autonomous Web Exploration & Screen Mapping Agent
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/ ./data/
COPY eval/ ./eval/

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.atlas.api:app --host 0.0.0.0 --port ${PORT}"]
