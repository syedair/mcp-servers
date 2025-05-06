# Capital.com MCP Server

This is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server that exposes the [Capital.com](https://capital.com/) trading API as tools that can be used by [Amazon Q](https://aws.amazon.com/q/) and other LLMs that support the MCP protocol.

## What is MCP?

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) is an open protocol that standardizes how applications provide context to LLMs. MCP enables communication between the system and locally running MCP servers that provide additional tools and resources to extend LLM capabilities. Learn more in the [MCP documentation](https://modelcontextprotocol.io/introduction).

## Setup

### Using uv (recommended package manager)

1. Install [uv](https://github.com/astral-sh/uv) if you don't have it already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. uv's on-the-fly dependency installation doesn't require creating a virtual environment beforehand, making setup much simpler.

3. Configure your environment variables with your Capital.com credentials:

```bash
export CAPITAL_BASE_URL=https://demo-api-capital.backend-capital.com
export CAPITAL_API_KEY=your_api_key_here
export CAPITAL_PASSWORD=your_password_here
export CAPITAL_IDENTIFIER=your_email@example.com
```

4. You can install this server in [Claude Desktop](https://claude.ai/desktop) and interact with it right away by running:

```bash
mcp install capital-mcp-server.py
```

5. If you are using Amazon Q to use the Capital.com MCP server:

The MCP configuration needs to be added to `~/.aws/amazonq/mcp.json` with the following content:

```json
{
  "mcpServers": {
    "capital-com-mcp-server": {
      "command": "uv",  
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "--with",
        "requests",
        "mcp",
        "run",
        "~/mcp-servers/capital-com-mcp-server/capital-mcp-server.py"
      ],
      "autoApprove": [
        "authenticate",
        "get_account_info",
        "search_markets",
        "get_prices",
        "get_positions",
        "get_watchlists"
      ],
      "disabled": false
    }
  }
}
```

This configuration tells Amazon Q or Claude Desktop to:
- Use uv to run the script with required dependencies installed on-the-fly
- Run the server script at `~/mcp-servers/capital-com-mcp-server/capital-mcp-server.py`
- Auto-approve certain safe read-only tools (authentication, getting account info, searching markets, etc.)
- Enable the server by default

The uv configuration has the advantage of not requiring a pre-configured virtual environment, as it installs dependencies on-demand.

## Using with LLMs

### Amazon Q

To use this MCP server with [Amazon Q CLI](https://aws.amazon.com/q/command-line/):

1. Start a chat with Amazon Q:

```bash
q chat
```

2. You can now use Capital.com tools in your conversation with Amazon Q:

```
I want to check my Capital.com account balance
```

Amazon Q will automatically start the MCP server when needed.

### Claude Desktop

You can use Capital.com tools directly in your conversations with Claude Desktop. Make sure you see the tools are successfully loaded.

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

## Example Invocations

Here are some examples of how to use the tools with Amazon Q:

- "What's my account balance on Capital.com?"
- "Search for TSLA on Capital.com"
- "Show me my open positions on Capital.com"
- "Create a buy position for NVDA with size 0.1"
- "Close my position with deal ID DEAL12345"

## Debugging

If you encounter issues with the MCP server, you can check the log file at:
```
/tmp/capital_mcp_server.log
```

This log file contains information about the server's operation, including any errors that might occur.

You can also run the MCP server with debug logging enabled:
```bash
cd ~/mcp-servers/capital-com-mcp-server
uv run --with mcp[cli] --with requests capital-mcp-server.py --debug
```

### Package Management Troubleshooting

If you're using [uv](https://github.com/astral-sh/uv) and encounter dependency issues:

```bash
# Update all dependencies to their latest compatible versions
uv pip install --upgrade requests fastmcp pydantic

# Check for outdated packages
uv pip list --outdated

# Generate requirements.txt file
uv pip freeze > requirements.txt
```

Or run the server with the SSE transport for easier debugging:
```bash
cd ~/mcp-servers/capital-com-mcp-server
uv run --with mcp[cli] --with requests capital-mcp-server.py --sse --port 8080
```

And run Amazon Q with trace logging enabled:
```bash
export Q_LOG_LEVEL=trace
q chat
```

## Notes

- The server automatically attempts to authenticate when started
- Authentication is also performed automatically before any tool invocation if not already authenticated
- Make sure to keep your API credentials secure
- This server implements basic functionality and may need to be extended for specific use cases

## Resources

- [Capital.com API Documentation](https://open-api.capital.com/)
- [MCP Documentation](https://modelcontextprotocol.io/introduction)
- [Amazon Q Documentation](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/what-is.html)
- [uv Documentation](https://github.com/astral-sh/uv)