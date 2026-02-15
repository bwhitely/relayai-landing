FROM python:3.12-slim

# Run as non-root user
RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

# Switch to non-root user
USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
