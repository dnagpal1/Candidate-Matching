FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    gnupg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
# For headless browser automation
RUN pip install --no-cache-dir playwright && \
    playwright install --with-deps chromium

# Copy requirements and install them separately for better caching
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy the application code
COPY . .

# Expose port
EXPOSE 8000

# Set environment variable
ENV PYTHONPATH=/app

# Use a separate entrypoint script for better flexibility
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 