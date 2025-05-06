# Capital.com MCP Server

This is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server that exposes the [Capital.com](https://capital.com/) trading API as tools that can be used by [Amazon Q](https://aws.amazon.com/q/) and other LLMs that support the MCP protocol.

## What is MCP?

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) is an open protocol that standardizes how applications provide context to LLMs. MCP enables communication between the system and locally running MCP servers that provide additional tools and resources to extend LLM capabilities.

## Setup

### Using uv (recommended package manager)

1. Install [uv](https://github.com/astral-sh/uv) if you don't have it already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install the package:

```bash
uv pip install capital-com-mcp-server
```

3. Configure your environment variables with your Capital.com credentials:

```bash
export CAPITAL_BASE_URL=https://demo-api-capital.backend-capital.com
export CAPITAL_API_KEY=your_api_key_here
export CAPITAL_PASSWORD=your_password_here
export CAPITAL_IDENTIFIER=your_email@example.com
```

## Available Tools

The following tools are exposed by the MCP server:

- `authenticate`: Authenticate with Capital.com API
- `get_account_info`: Get account information
- `search_markets`: Search for markets (e.g., EURUSD, AAPL)
- `get_prices`: Get prices for a specific instrument
- `get_positions`: Get all open positions
- `create_position`: Create a new trading position
- `close_position`: Close an open position
- `get_watchlists`: Get all watchlists

## Resources

- [Capital.com API Documentation](https://open-api.capital.com/)
- [MCP Documentation](https://modelcontextprotocol.io/introduction)
- [Amazon Q Documentation](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/what-is.html)
