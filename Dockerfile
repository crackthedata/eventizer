FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=2.0.1
RUN pip install "poetry==$POETRY_VERSION"

# Set up work directory
WORKDIR /app

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create a virtual environment inside the container
RUN poetry config virtualenvs.create false

# Install dependencies (including playwright)
RUN poetry install --no-root --no-interaction --no-ansi

# Install Playwright browsers (Chromium is usually sufficient for general scraping)
RUN playwright install --with-deps chromium

# Copy source code and config
COPY src/ ./src/

# Create data directory
RUN mkdir -p data

# Command to run (using python directly as per previous setup)
CMD ["python", "src/main.py"]
