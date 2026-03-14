FROM python:3.11-slim AS builder

WORKDIR /tmp
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

RUN groupadd -r app && useradd -r -g app app \
    && mkdir -p /app/chapters \
    && chown -R app:app /app

WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY --chown=app:app backend_rag.py .
COPY --chown=app:app chapters ./chapters/
COPY --chown=app:app requirements.txt .

RUN pip install --no-cache-dir 'requests<3' 'gradio<5'  # runtime small deps as root

EXPOSE 8000 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER app

CMD ["python", "backend_rag.py"]
