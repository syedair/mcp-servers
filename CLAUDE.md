# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

This repository contains a collection of **MCP (Model Context Protocol) servers** that expose financial trading platform APIs as tools for LLMs. Two independent Python packages are included:

- **capital-com-mcp-server** (`src/capital_com_mcp_server/`) — 26+ tools for the Capital.com trading API
- **etoro-mcp-server** (`src/etoro_mcp_server/`) — 8+ core tools for the eToro trading API

## Repository Structure

```
src/
  capital_com_mcp_server/   # Capital.com MCP server package (v0.3.2)
  etoro_mcp_server/         # eToro MCP server package (v0.3.0)
docker/                     # Docker deployment configs
.github/workflows/          # CI/CD automation (PyPI publish, Docker build, Claude review)
```

## Development Commands

### Running Servers Locally

```bash
# Capital.com server
cd src/capital_com_mcp_server
uv run capital-com-mcp-server
uv run capital-com-mcp-server --debug
uv run capital-com-mcp-server --streamable-http --port 8080

# eToro server
cd src/etoro_mcp_server
uv run etoro-mcp-server
uv run etoro-mcp-server --debug
uv run etoro-mcp-server --sse --port 8080
uv run etoro-mcp-server --streamable-http --port 8080
```

### Testing

Only the eToro server has a test suite:

```bash
cd src/etoro_mcp_server
uv run pytest
```

### Building Packages

```bash
cd src/capital_com_mcp_server && uv build
cd src/etoro_mcp_server && uv build
```

### Docker

```bash
# Production
docker-compose -f docker/docker-compose.yml up -d

# Development (with local build)
docker-compose -f docker/docker-compose.dev.yml up -d

# Logs
docker-compose -f docker/docker-compose.yml logs -f
```

## Environment Variables

### Capital.com Server

| Variable | Required | Description |
|---|---|---|
| `CAPITAL_BASE_URL` | Yes | API endpoint (`https://api-capital.backend.capitalinterface.com` for live, or demo URL) |
| `CAPITAL_API_KEY` | Yes | Capital.com API key |
| `CAPITAL_PASSWORD` | Yes | Account password |
| `CAPITAL_IDENTIFIER` | Yes | Account email/identifier |
| `CAPITAL_MCP_DEBUG` | No | Enable debug logging |
| `FASTMCP_LOG_LEVEL` | No | FastMCP log level |

### eToro Server

| Variable | Required | Description |
|---|---|---|
| `ETORO_API_KEY` | Yes | Public app key (`x-api-key` header) |
| `ETORO_USER_KEY` | Yes | User-specific key (`x-user-key` header) |
| `ETORO_ACCOUNT_TYPE` | Yes | `demo` or `real` |
| `ETORO_BASE_URL` | No | Override base URL |
| `ETORO_MCP_DEBUG` | No | Enable debug logging |
| `FASTMCP_LOG_LEVEL` | No | FastMCP log level |

## Key Dependencies

Both packages share these core dependencies:

- **fastmcp** — Framework for building MCP servers in Python
- **requests** — HTTP client for trading API calls
- **pydantic** — Data validation and modeling
- **python-dotenv** — Environment variable management (eToro)

Requires **Python >= 3.10**. The `uv` package manager is used for dependency management and builds.

## Architecture

Each server follows the same pattern:

```
MCP Tool Definitions (fastmcp)    ←  e.g. capital_mcp_server.py
         ↓
API Client Layer                  ←  e.g. capital_client.py
         ↓
Trading REST API                  ←  Capital.com / eToro
```

- `*_mcp_server.py` — Defines MCP tools, handles argument parsing, formats responses
- `*_client.py` — Handles authentication, session management, and raw API calls

## CI/CD

GitHub Actions workflows handle:

- **python-publish.yml** — Publishes both packages to PyPI on release (matrix build)
- **docker-build.yml** — Builds multi-arch Docker images and pushes to GHCR
- **claude.yml** — Claude PR assistant
- **claude-code-review.yml** — Automated code review on PRs

## Notes

- The Capital.com server has no test suite; the eToro server has pytest tests under `src/etoro_mcp_server/tests/`
- Each package is independently versioned and publishable to PyPI
- Both servers support three transport modes: `stdio` (default), `SSE`, and `streamable-http`
- Docker images are published to GitHub Container Registry (GHCR)
