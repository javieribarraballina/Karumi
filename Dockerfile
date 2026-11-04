# Atlas: Autonomous Web Exploration & Screen Mapping Agent
# Maintained by Andrés (Eval, Deploy, Pitch)

FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Python dependencies from the project's requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browser binaries
RUN playwright install chromium

# Clean layered copy of application subdirectories
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/ ./data/
COPY eval/ ./eval/

# Expose default port
EXPOSE 8000

# Start FastAPI server
CMD ["sh", "-c", "uvicorn backend.atlas.api:app --host 0.0.0.0 --port ${PORT}"]
