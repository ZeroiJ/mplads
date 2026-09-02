# Build context = repo ROOT (run: docker build -t mplads-backend -f backend/Dockerfile .)
FROM python:3.11-slim

WORKDIR /app

# Install runtime deps first (layer caching).
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Backend app + the detection package. Raw CSVs are uploaded at runtime; no
# precomputed master / real_sweep is required.
COPY backend/app.py /app/app.py
COPY src/ /app/src/

# Render injects this env var; default 8000 for local runs.
ENV PORT=8000
ENV MPLADS_REPO=/app

EXPOSE ${PORT}
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]