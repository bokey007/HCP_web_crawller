# ─── Stage 1: Build ──────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install UV
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system --no-cache ".[streamlit]"

# ─── Stage 2: Runtime ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Install Chromium for PyDoll
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r crawler && useradd -r -g crawler -d /app -s /sbin/nologin crawler

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY frontend/ ./frontend/

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMIUM_FLAGS="--headless --no-sandbox --disable-dev-shm-usage"

# Create data directory
RUN mkdir -p /app/data && chown -R crawler:crawler /app

USER crawler

# Expose ports
EXPOSE 8000 8501

# Default: start FastAPI
CMD ["uvicorn", "hcp_crawler.main:app", "--host", "0.0.0.0", "--port", "8000"]
