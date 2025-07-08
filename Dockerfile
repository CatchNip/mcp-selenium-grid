FROM python:3.13-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    IS_RUNNING_IN_DOCKER=True

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml config.yaml LICENSE README.md uv.lock ./mcp-selenium-grid/
COPY deployment ./mcp-selenium-grid/deployment
COPY scripts ./mcp-selenium-grid/scripts
COPY src/app ./mcp-selenium-grid/src/app

# Install the application dependencies
WORKDIR /mcp-selenium-grid
RUN uv venv .venv && uv sync --locked --no-cache --no-dev --no-default-groups

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /mcp-selenium-grid
USER appuser

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD sh -c 'curl -f -H "Authorization: Bearer $API_TOKEN" http://localhost:80/health || exit 1'

# Run the application.
CMD ["/mcp-selenium-grid/.venv/bin/fastapi", "run", "src/app/main.py", "--port", "80"]
