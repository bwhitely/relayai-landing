FROM python:3.12-slim

# Run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /srv

# Install dependencies first (layer caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY . .

# Install the app package itself
RUN pip install --no-cache-dir -e .

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
