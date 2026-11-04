# Atlas: Autonomous Web Exploration & Screen Mapping Agent
# Maintained by Andrés (Eval, Deploy, Pitch)

FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Python dependencies from the project's requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browser binaries
RUN playwright install chromium

# Copy codebase
COPY . /app

# Expose default port
EXPOSE 8000

# Start FastAPI server
CMD ["sh", "-c", "uvicorn backend.atlas.api:app --host 0.0.0.0 --port ${PORT}"]
