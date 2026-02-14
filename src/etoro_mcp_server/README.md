# eToro MCP Server

This is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server that exposes the [eToro](https://www.etoro.com/) trading API as tools that can be used by [Amazon Q](https://aws.amazon.com/q/), [Claude Desktop](https://claude.ai/desktop), and other LLMs that support the MCP protocol.

## Available Tools

The eToro MCP server provides **8 core trading tools** (Priority 1):

### Core Trading Tools
- `search_instruments`: Search for instruments by name/symbol/category and get their integer IDs
- `get_account_info`: Get account balance, equity, margin, and available funds
- `get_positions`: Get all open trading positions
- `create_position`: Create a new position with leverage, stop loss, and take profit
- `close_position`: Close an open position by position_id
- `update_position`: Modify stop loss and take profit levels on existing positions
- `get_instrument_metadata`: Get detailed instrument info (spread, trading hours, limits)
- `get_current_rates`: Get real-time bid/ask prices for instruments

## ✨ Key Features

- **Simple Authentication**: Static API keys (x-api-key, x-user-key) - no session management needed
- **Integer Instrument IDs**: eToro uses integer IDs (e.g., 1001, 2045) instead of string symbols
- **Direct Position Management**: position_id from creation works directly for updates/closes (no ID conversion required)
- **Leverage Trading**: Create positions with customizable leverage (1x, 2x, 5x, 10x, 20x, etc.)
- **Risk Management**: Set stop loss and take profit levels when creating or updating positions
- **Demo & Real Accounts**: Automatic endpoint routing based on ETORO_ACCOUNT_TYPE environment variable
- **Comprehensive Search**: Find instruments by name, symbol, or category (stocks, crypto, currencies, commodities, indices)
- **Real-time Pricing**: Get current bid/ask rates for one or more instruments
- **Detailed Metadata**: Trading hours, spreads, minimum/maximum trade amounts
- **No Re-authentication**: Static API keys don't expire (unlike session-based APIs)

## Key Differences from Other Trading APIs

### Authentication
- **eToro**: Static API keys with header-based authentication
- **Other APIs**: Often use session tokens that expire and require re-authentication

### Instrument Identification
- **eToro**: Integer instrument IDs (e.g., 1001 for Apple)
- **Other APIs**: String epics/symbols (e.g., "AAPL")

### Account Types
- **eToro**: Different endpoint paths for demo (`/api/demo/v1`) vs real (`/api/v1`) accounts
- **Other APIs**: Usually differentiate by base URL only

### Position Management
- **eToro**: Direct position_id usage (no conversion needed)
- **Other APIs**: Often require converting dealReference → dealId

## Configuration

### Required Environment Variables

The MCP server requires the following environment variables:

- `ETORO_API_KEY`: Your eToro public app key (x-api-key header)
- `ETORO_USER_KEY`: Your eToro user-specific key (x-user-key header)
- `ETORO_ACCOUNT_TYPE`: Account type - either `demo` or `real` (default: `demo`)

### Optional Environment Variables

- `ETORO_BASE_URL`: API base URL override (default: `https://api.etoro.com`)
- `ETORO_MCP_DEBUG`: Set to `1` to enable debug logging
- `FASTMCP_LOG_LEVEL`: Set to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`

## Installation & Setup

### Install via pip

```bash
pip install etoro-mcp-server
```

### Install with uvx (recommended)

```bash
uvx etoro-mcp-server
```

### Running Manually

```bash
# Run with stdio transport (default)
etoro-mcp-server

# Run with SSE transport
etoro-mcp-server --sse --port 8080

# Run with streamable HTTP transport
etoro-mcp-server --streamable-http --port 8080

# Run with debug logging
etoro-mcp-server --debug

# Get help with all options
etoro-mcp-server --help
```

## Example Usage

### Searching for Instruments

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

### Getting Account Information

```
You: What's my eToro account balance?

AI: Let me check your eToro account information.

[Uses get_account_info tool]

Your eToro account information:
- Account type: Demo
- Currency: USD
- Balance: $100,000.00
- Equity: $102,500.00
- Available funds: $95,000.00
- Margin used: $5,000.00
- Profit/Loss: +$2,500.00
```

### Creating a Position

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

### Getting Current Prices

```
You: What's the current price of Tesla and Apple?

AI: I'll get the current prices for Tesla and Apple.

[Uses search_instruments to find IDs, then get_current_rates with instrument_ids="1001,1052"]

Current market prices:
- Apple Inc. (1001): Bid $184.20, Ask $184.30
- Tesla Inc. (1052): Bid $248.40, Ask $248.55

The spread for Apple is $0.10 and for Tesla is $0.15.
```

### Updating a Position

```
You: Update my Bitcoin position to have a take profit at $70,000

AI: I'll update your Bitcoin position with the new take profit level.

[Uses get_positions to find position_id, then update_position]

Successfully updated your Bitcoin position:
- Position ID: pos_abc123
- New take profit: $70,000
- Stop loss: $60,000 (unchanged)
- Current price: $65,250

The position will automatically close if Bitcoin reaches $70,000 or $60,000.
```

### Getting Instrument Metadata

```
You: What are the trading hours and minimum investment for gold?

AI: I'll get the detailed metadata for gold trading.

[Uses search_instruments to find gold ID, then get_instrument_metadata]

Gold (Instrument ID: 3012) trading details:
- Trading hours: Sunday 23:00 - Friday 22:00 UTC
- Minimum trade: $50
- Maximum trade: $50,000
- Spread: 0.45 pips
- Leverage available: Up to 10x
- Market status: Currently OPEN
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

3. Restart Claude Desktop for the changes to take effect.

## Development

### Building from Source

```bash
cd src/etoro_mcp_server
uv build
```

### Testing with MCP Inspector

```bash
# From the repository root
mcp dev src/etoro_mcp_server/etoro_mcp_server/etoro_mcp_server.py

# With dependencies
mcp dev src/etoro_mcp_server/etoro_mcp_server/etoro_mcp_server.py \
  --with requests --with fastmcp --with python-dotenv
```

### Installing Locally

```bash
cd src/etoro_mcp_server
uv pip install -e .
```

## Important Notes

- **Instrument IDs are integers**: Unlike Capital.com or other platforms that use string symbols, eToro uses integer instrument IDs. Always use `search_instruments` first to get the correct ID.
- **Demo vs Real accounts**: Make sure to set `ETORO_ACCOUNT_TYPE` correctly. Demo accounts use different API endpoints (`/api/demo/v1` vs `/api/v1`).
- **Static authentication**: eToro uses static API keys that don't expire, so there's no need for re-authentication logic during operation.
- **Position management**: The `position_id` returned from `create_position` can be used directly for `update_position` and `close_position` - no ID conversion needed.
- **Risk management**: Always consider using stop loss and take profit levels to manage risk, especially when using leverage.

## Roadmap

### Future Enhancements (Priority 2-4)

The following features are planned for future releases:

**Priority 2: Enhanced Trading & Market Data (7 tools)**
- Historical candles/OHLC data
- Pending orders management
- Watchlist management

**Priority 3: Social & Copy Trading (6 tools)**
- Search and discover traders
- Get trader statistics
- Copy trading (mirrors) management

**Priority 4: Portfolio & Analytics (5 tools)**
- Portfolio summary and allocation
- Trading history
- User feed and notifications

## Resources

- [eToro API Documentation](https://www.etoro.com/api-documentation/)
- [MCP Documentation](https://modelcontextprotocol.io/introduction)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or contributions, please visit:
- [GitHub Issues](https://github.com/syedair/mcp-servers/issues)
- [GitHub Repository](https://github.com/syedair/mcp-servers)
