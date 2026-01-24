# Eventizer: Martial Arts Event Aggregator

Eventizer is a containerized Python application designed to crawl and scrape martial arts event information from various websites. It uses **Playwright** for robust browser automation and integrates with a **Local LLM (Ollama)** to extract structured event data from unstructured HTML.

## Features
- **Headless Browsing**: Uses Playwright (Chromium) to handle modern, dynamic websites.
- **Smart Extraction**:
    - **Tier 1**: Extracts standard JSON-LD and Microdata (Schema.org) using `extruct`.
    - **Tier 2**: Fallback to Local LLM extraction for unstructured sites.
- **Scheduling**: configurable scrape intervals (default: 24 hours).
- **Dockerized**: Easy to deploy and run in a lightweight container.

## Prerequisites
- **Container Engine**: Such as Docker Desktop, Rancher Desktop, or Podman that is installed and running.
- **Ollama**: Installed on your host machine for local LLM support.

## Setup & Usage

### 1. Configure Ollama (Host Machine)
By default, Ollama only listens to `localhost`. To allow the Docker container to access it, you must configure it to listen on all interfaces.

**PowerShell:**
```powershell
# Stop Ollama first if it's running
$env:OLLAMA_HOST = "0.0.0.0"
ollama serve
```

**Verify Installation:**
Ensure you have the model configured in `config.json` (default `llama3`):
```bash
ollama pull llama3
```

### 2. Configure Scraper
Edit `config.json` to add target websites or change settings:
```json
{
  "sites": [
    "https://example.com",
    "https://another-tournament-site.com"
  ],
  "schedule_interval_hours": 24,
  "llm_config": {
    "enabled": true,
    "api_base": "http://host.docker.internal:11434/v1",
    "model": "llama3",
    "api_key": "ollama"
  }
}
```

### 3. Build & Run
Build the Docker image:
```bash
docker build -t eventizer .
```

Run the scraper:
```bash
docker run eventizer
```

Run the scraper (allocating a volume to save data locally):
**PowerShell:**
```powershell
docker run -v ${PWD}/data:/app/data eventizer
```

**Bash:**
```bash
docker run -v $(pwd)/data:/app/data eventizer
```

The extracted events will be saved to `data/events.json` in your current directory.

## Detailed Architecture
- `src/main.py`: Entry point, handles scheduling and async execution.
- `src/scraper.py`: Core logic. Uses `playwright` to navigate and `extruct` + `openai` (for Ollama) to parse data.
- `Dockerfile`: Python 3.11-slim base, installing Playwright dependencies and browsers.
