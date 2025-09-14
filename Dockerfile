# ===== Base image =====
FROM python:3.11-slim AS base


WORKDIR /app

# ===== Install only required system dependencies =====
# (smaller list: OpenCV + Playwright Chromium only)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    fonts-noto \
    fonts-dejavu-core \
    gcc \
    build-essential \
    libffi-dev \
    python3-dev \
    libgl1 \
    libglib2.0-0 \
    libnss3 \
    libasound2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxshmfence1 \
    libx11-xcb1 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*


# ===== Install Python deps separately (better caching) =====
COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt


# ===== Pre-install Chromium only (skip WebKit + Firefox) =====
RUN python -m playwright install --with-deps chromium

# ===== Copy application code =====
COPY . .

# ===== Expose port =====
EXPOSE 10000

# ===== Environment variables =====
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# ===== Run app with Uvicorn =====
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000", "--workers", "1", "--loop", "asyncio"]
# ["python", "start.py"]
