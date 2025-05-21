FROM python:3.13-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    IS_RUNNING_IN_DOCKER=true

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml README.md ./app/
COPY src/app ./app

# Install the application dependencies.
WORKDIR /app
RUN uv venv /app/.venv && uv sync --no-cache --no-dev --no-default-groups

# Create non-root user.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port.
EXPOSE 80

# Health check.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application.
CMD ["/app/.venv/bin/fastapi", "run", "main.py", "--port", "80"]
