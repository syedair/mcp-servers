# MCP Servers Collection

This repository contains a collection of [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) servers that can be used with [Amazon Q](https://aws.amazon.com/q/), [Claude Desktop](https://claude.ai/desktop), and other LLMs that support the MCP protocol.

## Available MCP Servers

- [Capital.com MCP Server](src/capital_com_mcp_server/README.md): Exposes the Capital.com trading API as MCP tools for trading operations
  - Search for markets (e.g., EURUSD, AAPL)
  - Get account information and positions
  - Create and manage trading positions
  - Access watchlists

- [eToro MCP Server](src/etoro_mcp_server/README.md): Exposes the eToro trading API as MCP tools for trading operations
  - Search for instruments by name, symbol, or category
  - Get account information (balance, equity, margin)
  - Get and manage open trading positions
  - Create positions with leverage, stop loss, and take profit
  - Get real-time bid/ask prices for instruments
  - Access detailed instrument metadata (trading hours, spreads, limits)

## What is MCP?

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) is an open protocol that standardizes how applications provide context to LLMs. MCP enables communication between the system and locally running MCP servers that provide additional tools and resources to extend LLM capabilities.

## Prerequisites

Make sure you have `uv` installed on your system:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Using with Amazon Q

1. Create an `mcp.json` configuration file in your Amazon Q configuration directory (`~/.aws/amazonq/mcp.json`):
   ```json
   {
     "mcpServers": {
       "capital-com-mcp-server": {
         "command": "uvx",
         "args": ["capital-com-mcp-server"],
         "env": {
           "CAPITAL_BASE_URL": "https://demo-api-capital.backend-capital.com",
           "CAPITAL_API_KEY": "your_api_key_here",
           "CAPITAL_PASSWORD": "your_password_here",
           "CAPITAL_IDENTIFIER": "your_email@example.com",
           "FASTMCP_LOG_LEVEL": "ERROR"
         }
       },
       "etoro-mcp-server": {
         "command": "uvx",
         "args": ["etoro-mcp-server"],
         "env": {
           "ETORO_API_KEY": "your_public_app_key_here",
           "ETORO_USER_KEY": "your_user_key_here",
           "ETORO_ACCOUNT_TYPE": "demo",
           "FASTMCP_LOG_LEVEL": "ERROR"
         }
       }
     }
   }
   ```

2. Run Amazon Q with:
   ```bash
   q chat
   ```

3. Amazon Q will automatically start the MCP server and connect to it.

## Using with Claude Desktop

1. In Claude Desktop, go to Settings > Developer section and click on "Edit Config"

2. This will open the configuration file. Add the following to the JSON:
   ```json
   {
     "mcpServers": {
       "capital-com-mcp-server": {
         "command": "uvx",
         "args": ["capital-com-mcp-server"],
         "env": {
           "CAPITAL_BASE_URL": "https://demo-api-capital.backend-capital.com",
           "CAPITAL_API_KEY": "your_api_key_here",
           "CAPITAL_PASSWORD": "your_password_here",
           "CAPITAL_IDENTIFIER": "your_email@example.com",
           "FASTMCP_LOG_LEVEL": "ERROR"
         }
       },
       "etoro-mcp-server": {
         "command": "uvx",
         "args": ["etoro-mcp-server"],
         "env": {
           "ETORO_API_KEY": "your_public_app_key_here",
           "ETORO_USER_KEY": "your_user_key_here",
           "ETORO_ACCOUNT_TYPE": "demo",
           "FASTMCP_LOG_LEVEL": "ERROR"
         }
       }
     }
   }
   ```

3. Save the file and restart Claude Desktop.

## Example Conversations

### Capital.com

```
You: Search for Apple stock on Capital.com

AI: I'll search for Apple stock on Capital.com for you.

[Uses capital-com-mcp-server___search_markets tool]

I found Apple Inc. (AAPL) on Capital.com. Here are the details:
- Epic: AAPL
- Market name: Apple Inc.
- Current bid price: $184.25
- Current ask price: $184.30
- Market status: OPEN

Would you like me to get more information about this stock or perform any trading operations?
```

### eToro

```
You: Search for Apple stock on eToro

AI: I'll search for Apple stock on eToro for you.

[Uses search_instruments tool with search_term="Apple"]

I found Apple Inc. on eToro. Here are the details:
- Instrument ID: 1001
- Name: Apple Inc.
- Symbol: AAPL
- Category: Stocks
- Current price: $184.25
- Market status: OPEN

Note: The instrument ID (1001) is what you'll need for trading operations.
```

```
You: Buy $1000 worth of Bitcoin with 2x leverage and set a stop loss at $60,000

AI: I'll create a Bitcoin position with your specified parameters.

[Uses search_instruments to find Bitcoin instrument ID, then create_position]

Successfully created a BUY position for Bitcoin:
- Position ID: pos_abc123
- Instrument ID: 2045 (Bitcoin)
- Amount: $1,000
- Leverage: 2x
- Stop loss: $60,000
- Status: OPEN
- Current P&L: $0.00

The position is now active and being monitored.
```

## Repository Structure

Each MCP server is organized as a separate Python package under the `src/` directory:

```
mcp-servers/
├── README.md
└── src/
    ├── capital_com_mcp_server/
    │   ├── README.md
    │   ├── pyproject.toml
    │   ├── capital_com_mcp_server/
    │   │   ├── __init__.py
    │   │   ├── capital_mcp_server.py
    │   │   └── capital_client.py
    │   └── ...
    └── etoro_mcp_server/
        ├── README.md
        ├── pyproject.toml
        ├── etoro_mcp_server/
        │   ├── __init__.py
        │   ├── etoro_mcp_server.py
        │   └── etoro_client.py
        └── ...
```

## Development

To add a new MCP server to this collection:

1. Create a new directory under `src/` with your server name
2. Add the necessary files for your MCP server implementation
3. Include a `pyproject.toml` and `setup.py` in the server directory
4. Add a README.md with usage instructions

## Publishing

Each MCP server can be published to PyPI independently:

```bash
cd src/your_mcp_server
uv build
uv pip publish
```

## GitHub Actions

This repository uses GitHub Actions to automatically build and publish packages to PyPI when a new release is created. The workflow is configured to use a matrix strategy, allowing each package to be built and published independently.

To add a new package to the publishing workflow, update the matrix in `.github/workflows/python-publish.yml`:

```yaml
strategy:
  matrix:
    package: [capital_com_mcp_server, etoro_mcp_server]
```

## Resources

- [MCP Documentation](https://modelcontextprotocol.io/introduction)
- [Amazon Q Documentation](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/what-is.html)
- [Claude Desktop Documentation](https://docs.anthropic.com/claude/)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
