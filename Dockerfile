FROM python:3.11-slim AS builder

# Install build deps
WORKDIR /tmp
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd -r app && useradd -r -g app app \
    && mkdir -p /app/chapters /app/backend \
    && chown -R app:app /app

WORKDIR /app

# Copy installed deps from builder
COPY --from=builder /root/.local /app/.local
ENV PATH=/app/.local/bin:$PATH

# Copy app files (minimal)
COPY --chown=app:app backend/backend_rag.py .
COPY --chown=app:app backend/chapters ./chapters/
COPY --chown=app:app backend/requirements.txt .

# Runtime deps only (smaller image)
RUN pip install --no-cache-dir --user 'requests<3' 'gradio<6'

EXPOSE 8000 7860

# Healthcheck for FastAPI
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER app

CMD ["python", "backend_rag.py"]

