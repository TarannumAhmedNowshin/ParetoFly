# ParetoFly backend — FastAPI + LangGraph.
# Playwright (headless Chromium) is intentionally NOT installed: in production the
# web-enrichment chain relies on Serper -> DuckDuckGo, and PLAYWRIGHT_FALLBACK_ENABLED
# is forced off so the image stays small enough for free 512MB hosts.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_FALLBACK_ENABLED=false

WORKDIR /app

# Install only the runtime deps we actually use in production (no Playwright, no pytest).
COPY requirements-prod.txt ./
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && pip install -r requirements-prod.txt \
 && apt-get purge -y build-essential \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY app ./app

# Render (and most PaaS) inject $PORT; default to 8000 for local `docker run`.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
