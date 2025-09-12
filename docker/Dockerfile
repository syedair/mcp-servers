FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for package management
RUN pip install uv

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Environment variables
ENV CAPITAL_MCP_DEBUG=0
ENV HOST=0.0.0.0
ENV PORT=8080

# Expose the port for the MCP server
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the MCP server using uvx with streamable HTTP transport
CMD ["uvx", "capital-com-mcp-server", "--streamable-http", "--port", "8080"]