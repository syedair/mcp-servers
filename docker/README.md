# Docker Deployment for Capital.com MCP Server

This directory contains Docker configuration files for deploying the Capital.com MCP server.

## Prerequisites

- Docker and Docker Compose installed
- Capital.com API credentials

## Available Images

The Docker images are automatically built and published to GitHub Container Registry (GHCR):

- **Latest**: `ghcr.io/syedhumair/mcp-servers/capital-mcp-server:latest`
- **Versioned**: `ghcr.io/syedhumair/mcp-servers/capital-mcp-server:v1.0.0`

Images are built for multiple architectures: `linux/amd64`, `linux/arm64`

## Quick Start

1. **Copy environment variables**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file** with your Capital.com API credentials:
   ```bash
   # Required Capital.com API credentials
   CAPITAL_BASE_URL=https://demo-api-capital.backend-capital.com  # or live API
   CAPITAL_API_KEY=your_api_key_here
   CAPITAL_PASSWORD=your_password_here  
   CAPITAL_IDENTIFIER=your_email_here
   ```

3. **Run with pre-built image**:
   ```bash
   docker-compose up -d
   ```

   Or for local development with building:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

4. **Check status**:
   ```bash
   docker-compose ps
   docker-compose logs -f capital-mcp-server
   ```

## Configuration

### Environment Variables

- `CAPITAL_BASE_URL`: Capital.com API endpoint
  - Demo: `https://demo-api-capital.backend-capital.com`
  - Live: `https://api-capital.backend-capital.com`
- `CAPITAL_API_KEY`: Your Capital.com API key
- `CAPITAL_PASSWORD`: Your Capital.com account password
- `CAPITAL_IDENTIFIER`: Your Capital.com account email/identifier
- `CAPITAL_MCP_DEBUG`: Enable debug logging (0 or 1)

### Ports

- **8080**: MCP server HTTP port (streamable HTTP transport)

### Volumes

- `./logs`: Server log files
- `./data`: Server data files

## Usage

The server will be available at `http://localhost:8080` and uses the streamable HTTP transport protocol for MCP communication.

## Direct Docker Run

You can also run the container directly without docker-compose:

```bash
docker run -d \
  --name capital-mcp-server \
  -p 8080:8080 \
  -e CAPITAL_BASE_URL=https://demo-api-capital.backend-capital.com \
  -e CAPITAL_API_KEY=your_api_key \
  -e CAPITAL_PASSWORD=your_password \
  -e CAPITAL_IDENTIFIER=your_email \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  ghcr.io/syedhumair/mcp-servers/capital-mcp-server:latest
```

## Portainer Deployment

To deploy in Portainer:

1. Create a new stack in Portainer
2. Copy the contents of `docker-compose.yml`
3. Set up environment variables in Portainer's environment section:
   - `CAPITAL_BASE_URL`
   - `CAPITAL_API_KEY`
   - `CAPITAL_PASSWORD`
   - `CAPITAL_IDENTIFIER`
4. Deploy the stack

## GitHub Container Registry (GHCR)

Images are automatically built and published to GHCR on:
- **Push to main branch**: Tagged as `latest`
- **Release creation**: Tagged with version number
- **Manual trigger**: Available via GitHub Actions

### Pulling Images

Images are public and can be pulled without authentication:

```bash
docker pull ghcr.io/syedhumair/mcp-servers/capital-mcp-server:latest
```

### Available Tags

- `latest`: Latest build from main branch
- `main`: Same as latest
- `v1.0.0`, `v1.1.0`, etc.: Version-specific releases

## Health Monitoring

The container includes a health check that verifies the server is responding on port 8080. Check health status with:

```bash
docker-compose ps
```

## Logs

View real-time logs:
```bash
docker-compose logs -f capital-mcp-server
```

Logs are also persisted to the `./logs` directory with automatic rotation (max 10MB, 5 files).

## Stopping

```bash
docker-compose down
```

## Troubleshooting

1. **Container won't start**: Check your `.env` file has valid Capital.com credentials
2. **Health check failing**: Ensure port 8080 is not blocked by firewall
3. **Authentication errors**: Verify your Capital.com API credentials are correct
4. **For demo trading**: Make sure you're using the demo API URL