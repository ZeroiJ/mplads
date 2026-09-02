FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY app.py .

# The repo must be mounted or available at /mplads (or set MPLADS_REPO).
# Example:
#   docker run -e MPLADS_REPO=/mplads -v /path/to/mplads:/mplads mplads-backend

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
