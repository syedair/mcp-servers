# Capital.com MCP Server

This is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server that exposes the [Capital.com](https://capital.com/) trading API as tools that can be used by [Amazon Q](https://aws.amazon.com/q/), [Claude Desktop](https://claude.ai/desktop), and other LLMs that support the MCP protocol.

## Available Tools

The following tools are exposed by the MCP server:

- `get_account_info`: Get account information and balance
- `search_markets`: Search for markets/instruments (supports both search terms and epic codes)
- `get_prices`: Get current prices with configurable time resolution (MINUTE, HOUR, DAY, etc.)
- `get_historical_prices`: Get historical price data with custom time ranges and resolution
- `get_positions`: Get all open trading positions
- `create_position`: Create a new trading position (buy/sell) with optional stop loss and take profit
- `close_position`: Close an open position by deal ID
- `update_position`: Update position stop loss or take profit levels
- `get_watchlists`: Get all saved watchlists

## ✨ Key Features

- **Automatic Authentication**: Handles login and session token refresh automatically
- **Enhanced Search**: Search markets by name or use specific epic codes (e.g., "Apple" or "AAPL")
- **Multiple Time Resolutions**: MINUTE, HOUR, DAY, WEEK for price data
- **Robust Error Handling**: Built-in retry logic for expired sessions
- **No Manual Auth**: No separate authentication tool needed - handled behind the scenes

## Configuration

### Required Environment Variables

The MCP server requires the following environment variables:

- `CAPITAL_BASE_URL`: The Capital.com API base URL (e.g., `https://demo-api-capital.backend-capital.com`)
- `CAPITAL_API_KEY`: Your Capital.com API key
- `CAPITAL_PASSWORD`: Your Capital.com password
- `CAPITAL_IDENTIFIER`: Your Capital.com email/identifier

### Optional Environment Variables

- `CAPITAL_MCP_DEBUG`: Set to `1` to enable debug logging
- `FASTMCP_LOG_LEVEL`: Set to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` to control logging level

## Installation & Setup

### Install via pip

```bash
pip install capital-com-mcp-server
```

### Running Manually

```bash
# Run with stdio transport (default)
capital-com-mcp-server

# Run with debug logging
capital-com-mcp-server --debug

# Get help with all options
capital-com-mcp-server --help
```

## Example Usage

### Searching for Markets

```
You: Search for Apple stock on Capital.com

AI: I'll search for Apple stock on Capital.com for you.

[Uses search_markets tool]

I found Apple Inc. (AAPL) on Capital.com. Here are the details:
- Epic: AAPL
- Market name: Apple Inc.
- Current bid price: $184.25
- Current ask price: $184.30
- Market status: OPEN
```

### Getting Historical Price Data

```
You: Show me Tesla's daily price data for the last week

AI: I'll get Tesla's daily price data for you.

[Uses get_prices with epic="TSLA" and resolution="DAY"]

Tesla (TSLA) daily prices:
- Day 1: Open $248.50, Close $252.30, High $254.80, Low $247.90
- Day 2: Open $252.30, Close $249.75, High $253.20, Low $248.40
- Volume and price trends show recent volatility
```

### Getting Account Information

```
You: What's my account balance on Capital.com?

AI: Let me check your Capital.com account information.

[Uses get_account_info tool]

Your Capital.com account information:
- Account ID: ABC123456
- Account type: Demo
- Currency: USD
- Balance: $10,000.00
- Available funds: $9,500.00
- Margin used: $500.00
```

### Creating a Position

```
You: Buy 10 shares of Apple stock

AI: I'll create a buy position for Apple stock on Capital.com.

[Uses create_position tool]

Successfully created a BUY position for Apple Inc. (AAPL):
- Deal ID: DEF789012
- Size: 10 shares
- Opening price: $184.30
- Position status: OPEN
```

## Prerequisites for using with LLMs

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
       }
     }
   }
   ```


## Resources

- [Capital.com API Documentation](https://open-api.capital.com/)
- [MCP Documentation](https://modelcontextprotocol.io/introduction)
