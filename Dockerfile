FROM python:3.13-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml README.md ./app/
COPY uv.lock ./app/
COPY src/app ./app

# Install the application dependencies.
WORKDIR /app
RUN uv venv /app/.venv && uv sync --locked --no-cache --no-dev --no-default-groups

# Create non-root user.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port.
EXPOSE 80

# Health check.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD sh -c 'curl -f -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/health || exit 1'

# Run the application.
CMD ["/app/.venv/bin/fastapi", "run", "main.py", "--port", "80"]
