FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml README.md .
RUN mkdir agents services shared workers

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Copy application code
COPY alembic.ini .
COPY shared/ shared/
COPY agents/ agents/
COPY services/chatbot/ services/chatbot/

# Expose port
EXPOSE 8501

# Add a non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run the service
CMD ["streamlit", "run", "services/chatbot/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
