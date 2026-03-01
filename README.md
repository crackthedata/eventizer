# Eventizer: Locally Deployed Event Aggregator

**Version:** 0.2.0 (See [CHANGELOG.md](CHANGELOG.md) for details)
Eventizer is a containerized Python application that crawls and scrapes event information from various websites. It uses **Playwright** for robust browser automation and integrates with a **Local LLM (Ollama)** to extract structured event data from unstructured HTML.

## Features
- **Headless Browsing**: Uses Playwright (Chromium) to handle modern, dynamic websites.
- **Smart Extraction**:
    - **Tier 1**: Extracts standard JSON-LD and Microdata (Schema.org) using `extruct`.
    - **Tier 2**: Fallback to Local LLM extraction for unstructured sites.
- **Scheduling**: configurable scrape intervals (default: 24 hours).
- **Event Filtering**: Optional filtering of past events to keep data relevant.
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
    "https://another-example--site.com"
  ],
  "schedule_interval_hours": 24,
  "filter_past_events": true,
  "llm_config": {
    "enabled": true,
    "api_base": "http://host.docker.internal:11434/v1",
    "model": "llama3",
    "api_key": "ollama"
  },
  "crawling_config": {
    "max_depth": 2,
    "max_pages_per_site": 20
  }
}
```

### 3. Build & Run
First, create your configuration file:
1. Copy `config_example.json` to `config.json`.
2. Edit `config.json` with your real target sites and configuration settings.

**Important:** The Docker image does **not** contain `config.json` by default. You must provide it at runtime via a volume mount.

Remove any existing `eventizer` container before starting a new one, then build the image:
```bash
docker rm -f eventizer; docker build -t eventizer .
```

Run the scraper (Mounting config and data is **REQUIRED**):

**PowerShell:**
```powershell
docker run -d --name eventizer `
  -v "${PWD}/data:/app/data" `
  -v "${PWD}/config.json:/app/config.json" `
  eventizer
```

**Bash:**
```bash
docker run -d --name eventizer \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/config.json:/app/config.json" \
  eventizer
```

### 4. Application Logs
To verify the scraper is running and see what it's doing:

```bash
docker logs -f eventizer
```
Press `Ctrl+C` to stop following the logs (this will not stop the container).

## Troubleshooting / Frequently Encountered Errors

### Container Name Conflict
If the `docker run` command fails stating the container "eventizer" already exists, remove it before running again:
```bash
docker rm -f eventizer
```

### Ollama Connection Issues
If the scraper cannot reach Ollama, verify that Ollama is listening on `0.0.0.0` rather than `127.0.0.1` and that you configured the API base in `config.json` correctly (usually `http://host.docker.internal:11434/v1` for Docker Desktop on Windows/Mac).

## Configuration & Security
- **`config.json`**: This file contains your target sites and potential API keys. It is ignored by git (`.gitignore`) to prevent accidental commits.
- **`config_example.json`**: Use this as a template to create your own `config.json`.

## Detailed Architecture
- `src/main.py`: Entry point, handles scheduling and async execution.
- `src/scraper.py`: Core logic. Uses `playwright` to navigate and `extruct` + `openai` (for Ollama) to parse data.
- `Dockerfile`: Python 3.11-slim base, installing Playwright dependencies and browsers.

## Future enhancements
1. Prompt tuning for different kinds of events or events in different industries.
2. Implement a prompt library and traceable experiments.
3. Experiment with different event @types to improve tagging.
4. Try different local LLMs to evaluate how they differ.
5. Utilize multi-hop reasoning or few-shot learning to improve event extraction accuracy.