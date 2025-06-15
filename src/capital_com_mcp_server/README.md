# Capital.com MCP Server

This is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server that exposes the [Capital.com](https://capital.com/) trading API as tools that can be used by [Amazon Q](https://aws.amazon.com/q/), [Claude Desktop](https://claude.ai/desktop), and other LLMs that support the MCP protocol.

## Available Tools

The following tools are exposed by the MCP server:

### Core Trading Tools
- `get_account_info`: Get account information and balance
- `search_markets`: Search for markets/instruments (supports both search terms and epic codes)
- `get_prices`: Get current prices with configurable time resolution (MINUTE, HOUR, DAY, etc.)
- `get_historical_prices`: Get historical price data with custom time ranges and resolution
- `get_positions`: Get all open trading positions
- `create_position`: Create a new trading position (buy/sell) with comprehensive stop/profit options including trailing stops
- `close_position`: Close an open position by deal ID
- `update_position`: Comprehensively update positions with guaranteed stops, trailing stops, and multiple trigger options
- `get_watchlists`: Get all saved watchlists

### Session & Account Management
- `get_session_info`: Get current session information including active financial account
- `change_financial_account`: Switch between different financial accounts
- `get_accounts`: Get list of all financial accounts
- `get_account_preferences`: Get account preferences including leverage settings and hedging mode
- `update_account_preferences`: Update account preferences such as leverage settings (user-friendly parameters, no JSON required)
- `top_up_demo_account`: Add funds to demo trading account for testing

### Market Navigation & Discovery
- `get_market_navigation`: Get hierarchical structure of asset groups available for trading
- `get_market_navigation_node`: Get all assets/instruments under a specific navigation node
- `get_watchlist_contents`: Get contents of a specific watchlist

### Working Orders Management
- `create_working_order`: Create stop or limit orders that execute when market reaches specified level (returns dealReference for tracking)
- `get_working_orders`: Get all pending working orders (note: newly created orders may not appear immediately)
- `update_working_order`: Update parameters of existing working orders (requires working order ID from get_working_orders, not dealReference)
- `delete_working_order`: Cancel and remove working orders (requires working order ID from get_working_orders, not dealReference)

### History & Reporting
- `get_activity_history`: Get trading activity history with lastPeriod support (max 24h), deal ID filtering, and FIQL filtering (date ranges documented but currently limited)
- `get_transaction_history`: Get financial transaction history with full date range support and transaction type filtering (all parameters optional per API spec)
- `confirm_deal`: Confirm position status after creation and get dealId for management

### Market Information
- `get_client_sentiment`: Get client sentiment data showing long vs short position percentages for markets

### Utilities
- `ping_api`: Test connection to the Capital.com API
- `get_server_time`: Get current server time from Capital.com API

## ✨ Key Features

- **Complete API Coverage**: Full access to all Capital.com REST API endpoints (26+ tools)
- **Automatic Authentication**: Handles login and session token refresh automatically
- **Advanced Trading**: Create positions with trailing stops, comprehensive position updates (guaranteed stops, trailing stops), working orders (stop/limit), manage portfolios
- **Account Management**: Switch accounts, update leverage settings, manage preferences
- **Market Discovery**: Navigate asset hierarchies, explore watchlists, search instruments
- **Smart Historical Data**: Trading activity (lastPeriod up to 24h) and transaction history (full date range support) with real-world tested functionality
- **Enhanced Search**: Search markets by name or use specific epic codes (e.g., "Apple" or "AAPL")
- **Multiple Time Resolutions**: MINUTE, HOUR, DAY, WEEK for price data
- **Position Confirmation**: Verify trades and get deal IDs for position management
- **Robust Error Handling**: Built-in retry logic for expired sessions
- **No Manual Auth**: No separate authentication tool needed - handled behind the scenes
- **API-Compliant Formatting**: Automatic timezone handling and proper date format conversion
- **User-Friendly Preferences**: Update leverage settings with simple parameters (no JSON required)

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
You: Buy 10 shares of Apple stock with a trailing stop 5 points below the current price

AI: I'll create a buy position for Apple stock with a trailing stop.

[Uses create_position with trailing_stop=true, stop_distance=5]

Successfully created a BUY position for Apple Inc. (AAPL):
- Deal Reference: o_17a6e937-6947-4825-92f1-9c690df802a9
- Size: 10 shares
- Trailing stop: Active (5 points distance)
- Position status: CREATED
- Note: Use get_positions() to find dealId for position management
```

### Creating Working Orders

```
You: Set a stop order to buy Tesla at $240 with a stop loss at $230

AI: I'll create a stop order for Tesla with your specified levels.

[Uses create_working_order tool]

Successfully created a STOP order for Tesla (TSLA):
- Deal Reference: o_17a6e937-6947-4825-92f1-9c690df802a9
- Direction: BUY
- Level: $240.00
- Stop loss: $230.00
- Note: Order created successfully. Use get_working_orders() to find the working order ID for management operations.
```

### Managing Account Preferences

```
You: Check my current leverage settings and change FOREX leverage to 50:1

AI: Let me check your account preferences and update the FOREX leverage.

[Uses get_account_preferences and update_account_preferences tools]

Current account preferences:
- Hedging mode: Enabled
- CURRENCIES leverage: 30:1
- SHARES leverage: 5:1

[Uses update_account_preferences with currencies_leverage=50]

Successfully updated CURRENCIES (FOREX) leverage to 50:1.

Available leverage categories:
- currencies_leverage: For FOREX/currency pairs
- cryptocurrencies_leverage: For crypto instruments
- shares_leverage: For stocks/equities
- commodities_leverage: For commodities trading
- indices_leverage: For market indices
```

### Checking Market Sentiment

```
You: What's the client sentiment for Silver and Bitcoin?

AI: I'll check the client sentiment for Silver and Bitcoin on Capital.com.

[Uses get_client_sentiment with market_ids="SILVER,BTCUSD"]

Client sentiment data:
- SILVER: 91.85% long, 8.15% short (Strongly bullish sentiment)
- BTCUSD: 62.97% long, 37.03% short (Moderately bullish sentiment)

This suggests most traders are bullish on both assets, with Silver showing particularly strong bullish sentiment.
```

### History and Transaction Queries

```
You: Show me my trading activity from the last 24 hours with detailed information

AI: I'll get your detailed trading activity from the last 24 hours.

[Uses get_activity_history with last_period=86400, detailed=true]

Trading activity (last 24 hours):
- Position opened: AAPL BUY 10 shares at $184.30
- Stop loss updated: TSLA position, new SL at $240.00
- Working order filled: NVDA LIMIT order executed at $520.00

Total activities: 3
```

```
You: Get my transaction history for the last week, filter for deposits only

AI: I'll retrieve your deposit transactions from the last week.

[Uses get_transaction_history with from_date="2024-06-07T00:00:00", to_date="2024-06-14T23:59:59", transaction_type="DEPOSIT"]

Deposit transactions (last 7 days):
- 2024-06-10: $1,000.00 deposit via bank transfer
- 2024-06-08: $500.00 deposit via credit card

Total deposits: $1,500.00
```

### Advanced Position Creation with Trailing Stops

```
You: Create a Bitcoin position with trailing stop protection

AI: I'll create a Bitcoin position with trailing stop for risk management.

[Uses create_position with epic="BTCUSD", direction="BUY", size=0.1, trailing_stop=true, stop_distance=500]

Successfully created Bitcoin position:
- Epic: BTCUSD
- Direction: BUY
- Size: 0.1 BTC
- Trailing stop: Active (500 points distance)
- Features: Stop will automatically follow price movements upward

Available position creation options:
- trailing_stop: Automatic stop that follows favorable price movements
- guaranteed_stop: Premium guaranteed stop loss (cannot be used with trailing stops)
- stop_level/distance/amount: Multiple ways to set stop loss
- profit_level/distance/amount: Multiple ways to set take profit
```

### Comprehensive Position Updates

```
You: Update my Apple position to add a trailing stop that's 10 points below the current price

AI: I'll update your Apple position to add a trailing stop for better risk management.

[Uses get_positions to find the dealId, then update_position with trailing_stop=true, stop_distance=10]

Successfully updated Apple position:
- Deal ID: DIAAAAE9DSMA
- Added trailing stop: 10 points distance
- The stop will automatically follow favorable price movements upward
- Previous static stop has been replaced with trailing stop

Position update options available:
- guaranteed_stop: Premium guaranteed stop (cannot combine with trailing_stop)
- trailing_stop: Automatic stop that follows price (requires stop_distance)
- stop_level/distance/amount: Set stop loss in different ways
- profit_level/distance/amount: Set take profit in different ways
- All parameters are optional - update only what you need
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
