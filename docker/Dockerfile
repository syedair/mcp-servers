FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Install uv for package management
RUN pip install uv

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Environment variables
ENV CAPITAL_MCP_DEBUG=0
ENV MCP_PORT=8080

# Expose the port for the MCP server (dynamically based on MCP_PORT)
EXPOSE $MCP_PORT

# Health check removed - Docker will monitor process health instead

# Run the MCP server using uvx with streamable HTTP transport
# Port can be overridden with MCP_PORT environment variable in docker-compose
# Note: FastMCP servers don't support --host parameter, they bind to 0.0.0.0 by default in streamable-http mode
CMD ["sh", "-c", "uvx capital-com-mcp-server --streamable-http --port ${MCP_PORT:-8080}"]