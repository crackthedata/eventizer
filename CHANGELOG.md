# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-25

### Added
- Initial release of the Eventizer application.
- Headless browsing feature using Playwright for handling dynamic websites.
- Two-tier smart data extraction methodology:
  - Tier 1: Extract standard JSON-LD and Microdata via `extruct`.
  - Tier 2: Fallback to Local LLM extraction (Ollama with llama3) for unstructured HTML.
- Configurable scheduling system for automated scrape intervals.
- Optional event filtering to remove past events from the extracted event listings.
- Dockerized deployment including a standalone Dockerfile.
