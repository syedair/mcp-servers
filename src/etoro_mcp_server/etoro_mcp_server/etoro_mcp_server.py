#!/usr/bin/env python3
"""
eToro MCP Server - Exposes eToro API as MCP tools using FastMCP
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, Any, List, Optional, Union

# Import the eToro client
try:
    from .etoro_client import EtoroClient
except ImportError:
    from etoro_client import EtoroClient

# Import FastMCP
from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

# Configure logging
logger = logging.getLogger("etoro_mcp_server")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Check for debug mode
if os.environ.get("ETORO_MCP_DEBUG", "0") == "1":
    logger.setLevel(logging.DEBUG)
    logger.debug("Debug logging enabled")

# Initialize FastMCP
mcp = FastMCP(
    name="etoro-mcp-server",
    instructions="""
    # eToro MCP Server

    This server provides tools to interact with the eToro trading API.
    API Reference: https://api-portal.etoro.com/

    ## Best Practices

    - Authentication uses static API keys (x-api-key, x-user-key) from environment variables
    - Use search_instruments or resolve_symbol to find instruments and their integer IDs
    - Check account information before creating positions
    - Consider using stop loss and take profit levels when creating positions
    - Monitor open positions regularly via get_portfolio or get_positions

    ## Key API Details

    - **Base URL**: https://public-api.etoro.com
    - **Instrument IDs are integers** (e.g., 1001, 2045), not string symbols
    - **Static API keys** - no session tokens or re-authentication needed
    - **Account types**: Demo uses /demo/ in trading paths, real omits it
    - **Market data endpoints** are shared between demo and real accounts

    ## Position Management Workflow

    1. **Find Instrument**: Use `search_instruments` or `resolve_symbol` to get the integer instrument ID
    2. **Check Rates**: Use `get_current_rates` to see current bid/ask prices
    3. **Create Position**: Use `create_position` with instrument_id, is_buy (true/false), and amount
    4. **Monitor**: Use `get_positions` or `get_portfolio` to see open positions and their position IDs
    5. **Close Position**: Use `close_position` with position_id and instrument_id

    **Example Workflow**:
    ```
    1. instrument = resolve_symbol(symbol="AAPL")
       → Returns: {"instrumentId": 1001, "displayname": "Apple Inc.", ...}

    2. rates = get_current_rates(instrument_ids="1001")
       → Returns: bid/ask prices

    3. order = create_position(instrument_id=1001, is_buy=true, amount=1000)
       → Returns: {"orderForOpen": {"orderID": "abc123", ...}, "token": "..."}

    4. positions = get_positions()
       → Returns: {"positions": [{"positionID": 12345, "instrumentID": 1001, ...}]}

    5. close_position(position_id="12345", instrument_id=1001)
    ```

    ## Tool Selection Guide

    - Use `get_account_info` when: You need to check account balance (credit)
    - Use `get_portfolio` when: You need full portfolio overview (positions, orders, balance)
    - Use `get_positions` when: You only need open positions
    - Use `search_instruments` when: You need to find instruments by name or keyword
    - Use `resolve_symbol` when: You know the exact ticker symbol (e.g., "AAPL", "BTC")
    - Use `get_instrument_metadata` when: You need display names, exchange IDs, classification
    - Use `get_current_rates` when: You need real-time bid/ask prices
    - Use `create_position` when: You want to open a new position (by cash amount)
    - Use `create_position_by_units` when: You want to open a position by unit count
    - Use `close_position` when: You want to close an existing position (full or partial)
    - Use `get_order_info` when: You need to check order execution status and resulting positions
    - Use `get_historical_candles` when: You need OHLCV price history (charts, technical analysis)
    - Use `get_closing_prices` when: You need closing prices for all instruments
    - Use `get_instrument_types` when: You need available asset classes (stocks, ETFs, crypto, etc.)
    - Use `get_pnl` when: You need account PnL and portfolio performance details
    - Use `place_limit_order` when: You want to open a position at a specific target price (not market price)
    - Use `cancel_order` when: You need to cancel a pending limit, open, or close order
    - Use `get_watchlists` when: You need to see all your watchlists
    - Use `create_watchlist` when: You want to create a new watchlist
    - Use `delete_watchlist` when: You want to remove a watchlist permanently
    - Use `add_watchlist_items` when: You want to add instruments to a watchlist
    - Use `remove_watchlist_items` when: You want to remove instruments from a watchlist
    - Use `rename_watchlist` when: You want to change a watchlist's name
    - Use `get_user_profile` when: You need profile data for an eToro user
    - Use `get_user_performance` when: You need gain/performance metrics for a user
    - Use `get_user_trade_info` when: You need trading statistics for a user over a period
    - Use `search_users` when: You want to discover traders by performance, risk, or popularity
    - Use `get_user_feed` when: You want to read a user's social feed posts
    - Use `get_instrument_feed` when: You want to read discussion posts about an instrument
    - Use `create_post` when: You want to create a new discussion post
    - Use `create_comment` when: You want to comment on an existing post

    ## Limit Order Workflow

    1. **Find Instrument**: Use `resolve_symbol` to get instrument ID
    2. **Check Rates**: Use `get_current_rates` to see current price
    3. **Place Order**: Use `place_limit_order` with a target rate (trigger price)
    4. **Monitor**: Use `get_portfolio` to see pending orders
    5. **Cancel**: Use `cancel_order` with order_type="limit" if you want to cancel

    ## Watchlist Workflow

    1. `get_watchlists` → see existing watchlists
    2. `create_watchlist(name="My Stocks")` → create new
    3. `add_watchlist_items(watchlist_id="...", instrument_ids="1001,2045")` → add instruments
    4. `remove_watchlist_items(...)` → remove instruments
    5. `rename_watchlist(...)` → rename
    6. `delete_watchlist(...)` → delete

    ## Social / Copy-Trading Research Workflow

    1. `search_users` → discover traders by gain, risk score, period
    2. `get_user_profile(username)` → view trader's profile
    3. `get_user_performance(username)` → check historical gains
    4. `get_user_trade_info(username, period)` → analyze trading stats
    5. `get_user_feed(user_id)` → read their posts and insights
    6. `get_instrument_feed(market_id)` → read discussions about an instrument
    """
)

# Initialize client and credentials validation state
client = EtoroClient(
    base_url=os.environ.get("ETORO_BASE_URL", "https://public-api.etoro.com"),
    api_key=os.environ.get("ETORO_API_KEY", ""),
    user_key=os.environ.get("ETORO_USER_KEY", ""),
    account_type=os.environ.get("ETORO_ACCOUNT_TYPE", "demo")
)
def check_credentials() -> str | None:
    """Check that API keys are configured. Returns error message or None."""
    if not client.api_key or not client.user_key:
        return "Missing credentials. Set ETORO_API_KEY and ETORO_USER_KEY environment variables."
    return None


# =====================
# Market Data Tools
# =====================

@mcp.tool()
async def search_instruments(
    ctx: Context,
    search_term: Optional[str] = Field(default=None, description="Search text (e.g., 'Apple', 'Bitcoin', 'EUR')"),
    page_size: int = Field(default=10, description="Number of results per page"),
    page_number: int = Field(default=1, description="Page number for pagination")
) -> Dict[str, Any]:
    """Search for tradeable instruments on eToro.

    Returns matching instruments with their integer IDs needed for trading.
    Use this to discover instruments by name or keyword.

    Returns:
        Search results with items array containing instrumentId, displayname, symbol, etc.
    """

    logger.info(f"Invoking search_instruments tool: search_term={search_term}")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.search_instruments(search_term, page_size, page_number)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error searching instruments: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def resolve_symbol(
    ctx: Context,
    symbol: str = Field(description="Ticker symbol to resolve (e.g., 'AAPL', 'BTC', 'EURUSD')")
) -> Dict[str, Any]:
    """Resolve a ticker symbol to an eToro instrument ID.

    Use this when you know the exact ticker symbol and need the numeric instrument ID.
    More precise than search_instruments for known symbols.

    Returns:
        Instrument details including instrumentId, displayname, internalSymbolFull
    """

    logger.info(f"Invoking resolve_symbol tool: symbol={symbol}")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_instrument_by_symbol(symbol)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error resolving symbol: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_instrument_metadata(
    ctx: Context,
    instrument_ids: Union[str, int] = Field(description="Comma-separated instrument IDs (e.g., '1001' or '1001,2045')")
) -> Dict[str, Any]:
    """Get metadata for instruments including display names, exchange IDs, and classification.

    Returns:
        Instrument metadata with instrumentDisplayDatas array
    """
    instrument_ids = str(instrument_ids)

    logger.info(f"Invoking get_instrument_metadata tool: instrument_ids={instrument_ids}")

    # Parse instrument IDs
    try:
        id_list = [int(id_str.strip()) for id_str in instrument_ids.split(",")]
        for inst_id in id_list:
            if inst_id <= 0:
                validation_error = "All instrument IDs must be positive integers"
                await ctx.error(validation_error)
                return {"error": validation_error}
    except ValueError:
        validation_error = "instrument_ids must be comma-separated integers (e.g., '1001,2045')"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_instrument_metadata(id_list)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting instrument metadata: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_current_rates(
    ctx: Context,
    instrument_ids: Union[str, int] = Field(description="Comma-separated instrument IDs (e.g., '1001' or '1001,2045,3078'). Max 100.")
) -> Dict[str, Any]:
    """Get current real-time bid/ask prices for instruments.

    Returns:
        Current rates with bid/ask prices for each instrument
    """
    instrument_ids = str(instrument_ids)

    logger.info(f"Invoking get_current_rates tool: instrument_ids={instrument_ids}")

    # Parse instrument IDs
    try:
        id_list = [int(id_str.strip()) for id_str in instrument_ids.split(",")]
        for inst_id in id_list:
            if inst_id <= 0:
                validation_error = "All instrument IDs must be positive integers"
                await ctx.error(validation_error)
                return {"error": validation_error}
    except ValueError:
        validation_error = "instrument_ids must be comma-separated integers (e.g., '1001,2045')"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_current_rates(id_list)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting current rates: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


# =====================
# Portfolio & Account Tools
# =====================

@mcp.tool()
async def get_account_info(ctx: Context) -> Dict[str, Any]:
    """Get account information including balance (credit) and account type.

    Returns:
        Account info with credit, bonusCredit, and account_type
    """

    logger.info("Invoking get_account_info tool")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_account_info()

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting account info: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_portfolio(ctx: Context) -> Dict[str, Any]:
    """Get comprehensive portfolio information including positions, orders, and account status.

    Returns the full portfolio overview with active positions, pending orders,
    mirror trading details, and account balances.

    Returns:
        Portfolio data with clientPortfolio containing positions, credit, orders, mirrors
    """

    logger.info("Invoking get_portfolio tool")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_portfolio()

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting portfolio: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_positions(ctx: Context) -> Dict[str, Any]:
    """Get all open trading positions.

    Returns only the positions from the portfolio, with their details
    including positionID, instrumentID, direction, amount, and profit/loss.

    Returns:
        Positions data with positions array
    """

    logger.info("Invoking get_positions tool")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_positions()

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting positions: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


# =====================
# Trading Execution Tools
# =====================

@mcp.tool()
async def create_position(
    ctx: Context,
    instrument_id: int = Field(description="Instrument ID (integer). Get from search_instruments or resolve_symbol."),
    is_buy: bool = Field(description="True for long/BUY position, False for short/SELL position"),
    amount: float = Field(description="Investment amount in account currency (e.g., 1000 for $1000)"),
    leverage: int = Field(default=1, description="Leverage multiplier (1, 2, 5, 10, 20, etc.)"),
    stop_loss_rate: Optional[float] = Field(default=None, description="Stop loss price level (optional)"),
    take_profit_rate: Optional[float] = Field(default=None, description="Take profit price level (optional)")
) -> Dict[str, Any]:
    """Create a new trading position by specifying the cash amount to invest.

    Opens a market order at the current price. Use get_current_rates first to check prices.

    IMPORTANT:
    - instrument_id must be a positive integer from search_instruments or resolve_symbol
    - is_buy=True for BUY/long, is_buy=False for SELL/short
    - The response contains an orderID which can be used with get_order_info to track execution

    Returns:
        Order result with orderForOpen (containing orderID, instrumentID, amount, etc.) and token
    """

    logger.info(f"Invoking create_position tool: instrument_id={instrument_id}, is_buy={is_buy}, amount={amount}")

    # Validate inputs
    if not isinstance(instrument_id, int) or instrument_id <= 0:
        validation_error = "instrument_id must be a positive integer"
        await ctx.error(validation_error)
        return {"error": validation_error}

    if amount <= 0:
        validation_error = "amount must be greater than 0"
        await ctx.error(validation_error)
        return {"error": validation_error}

    if leverage < 1:
        validation_error = "leverage must be at least 1"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.create_position(instrument_id, is_buy, amount, leverage, stop_loss_rate, take_profit_rate)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error creating position: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def create_position_by_units(
    ctx: Context,
    instrument_id: int = Field(description="Instrument ID (integer). Get from search_instruments or resolve_symbol."),
    is_buy: bool = Field(description="True for long/BUY position, False for short/SELL position"),
    units: float = Field(description="Number of units to trade (e.g., 1.5 BTC, 10 shares)"),
    leverage: int = Field(default=1, description="Leverage multiplier (1, 2, 5, 10, 20, etc.)"),
    stop_loss_rate: Optional[float] = Field(default=None, description="Stop loss price level (optional)"),
    take_profit_rate: Optional[float] = Field(default=None, description="Take profit price level (optional)")
) -> Dict[str, Any]:
    """Create a new trading position by specifying the number of units.

    Use this when you need exact volume control (e.g., buy exactly 1.5 BTC or 10 shares).
    For dollar-amount investing, use create_position instead.

    Returns:
        Order result with orderForOpen (containing orderID, instrumentID, units, etc.) and token
    """

    logger.info(f"Invoking create_position_by_units tool: instrument_id={instrument_id}, is_buy={is_buy}, units={units}")

    # Validate inputs
    if not isinstance(instrument_id, int) or instrument_id <= 0:
        validation_error = "instrument_id must be a positive integer"
        await ctx.error(validation_error)
        return {"error": validation_error}

    if units <= 0:
        validation_error = "units must be greater than 0"
        await ctx.error(validation_error)
        return {"error": validation_error}

    if leverage < 1:
        validation_error = "leverage must be at least 1"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.create_position_by_units(instrument_id, is_buy, units, leverage, stop_loss_rate, take_profit_rate)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error creating position: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def close_position(
    ctx: Context,
    position_id: Union[str, int] = Field(description="Position ID to close (from get_positions)"),
    instrument_id: int = Field(description="Instrument ID of the position (from get_positions)"),
    units_to_deduct: Optional[float] = Field(default=None, description="Units to close. Omit or null to close entire position. Provide a value for partial close.")
) -> Dict[str, Any]:
    """Close an open trading position (full or partial).

    To close the entire position, omit units_to_deduct (or set to null).
    To partially close, specify the number of units to deduct.

    IMPORTANT: Both position_id AND instrument_id are required. Get them from get_positions.

    Returns:
        Order result with orderForClose and token
    """
    position_id = str(position_id)

    logger.info(f"Invoking close_position tool: position_id={position_id}, instrument_id={instrument_id}")

    # Validate inputs
    if not position_id or len(position_id.strip()) == 0:
        validation_error = "position_id cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    if not isinstance(instrument_id, int) or instrument_id <= 0:
        validation_error = "instrument_id must be a positive integer"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.close_position(position_id, instrument_id, units_to_deduct)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error closing position: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_order_info(
    ctx: Context,
    order_id: Union[str, int] = Field(description="Order ID to look up (from create_position response)")
) -> Dict[str, Any]:
    """Get order information and position details for a specific order.

    Use this to track order execution status and find which positions were created
    from a specific order. The response includes PositionID values.

    Returns:
        Order details with execution status and position information
    """
    order_id = str(order_id)

    logger.info(f"Invoking get_order_info tool: order_id={order_id}")

    if not order_id or len(order_id.strip()) == 0:
        validation_error = "order_id cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_order_info(order_id)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting order info: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


# =====================
# Additional Market Data Tools
# =====================

@mcp.tool()
async def get_historical_candles(
    ctx: Context,
    instrument_id: int = Field(description="Instrument ID (integer). Get from search_instruments or resolve_symbol."),
    interval: str = Field(default="OneDay", description="Candle interval: OneMinute, FiveMinutes, TenMinutes, FifteenMinutes, ThirtyMinutes, OneHour, FourHours, OneDay, OneWeek"),
    candles_count: int = Field(default=100, description="Number of candles to retrieve (1-1000)"),
    direction: str = Field(default="desc", description="Sort order: 'asc' (oldest first) or 'desc' (newest first)")
) -> Dict[str, Any]:
    """Get historical OHLCV candle data for an instrument.

    Use for charting, technical analysis, and price history.

    Returns:
        Candle data with interval and candles array containing open, high, low, close, volume
    """
    logger.info(f"Invoking get_historical_candles tool: instrument_id={instrument_id}, interval={interval}")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_historical_candles(instrument_id, interval, candles_count, direction)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting historical candles: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_closing_prices(ctx: Context) -> Dict[str, Any]:
    """Get historical closing prices for all instruments.

    Returns:
        Closing prices data for all available instruments
    """
    logger.info("Invoking get_closing_prices tool")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_closing_prices()

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting closing prices: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_instrument_types(ctx: Context) -> Dict[str, Any]:
    """Get available instrument types (asset classes) such as stocks, ETFs, commodities, crypto, etc.

    Returns:
        Available instrument types/asset classes
    """
    logger.info("Invoking get_instrument_types tool")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_instrument_types()

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting instrument types: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


# =====================
# PnL Tool
# =====================

@mcp.tool()
async def get_pnl(ctx: Context) -> Dict[str, Any]:
    """Get account PnL (profit and loss) and portfolio performance details.

    Returns:
        PnL data including realized/unrealized gains and portfolio metrics
    """
    logger.info("Invoking get_pnl tool")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_pnl()

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting PnL: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


# =====================
# Limit Order & Cancel Tools
# =====================

@mcp.tool()
async def place_limit_order(
    ctx: Context,
    instrument_id: int = Field(description="Instrument ID (integer). Get from search_instruments or resolve_symbol."),
    is_buy: bool = Field(description="True for long/BUY, False for short/SELL"),
    leverage: int = Field(description="Leverage multiplier (1, 2, 5, 10, 20, etc.)"),
    rate: float = Field(description="Trigger price at which the market order will be sent"),
    amount: Optional[float] = Field(default=None, description="Trade amount in USD. Provide either amount or amount_in_units, not both."),
    amount_in_units: Optional[float] = Field(default=None, description="Number of units. Provide either amount or amount_in_units, not both."),
    stop_loss_rate: Optional[float] = Field(default=None, description="Stop loss price level (optional)"),
    take_profit_rate: Optional[float] = Field(default=None, description="Take profit price level (optional)"),
    is_tsl_enabled: bool = Field(default=False, description="Enable trailing stop loss"),
    is_no_stop_loss: bool = Field(default=False, description="Disable stop loss for this order"),
    is_no_take_profit: bool = Field(default=False, description="Disable take profit for this order")
) -> Dict[str, Any]:
    """Place a Market-if-touched (limit) order to open a position when a target price is reached.

    Unlike create_position (market order), this order waits until the instrument reaches
    the specified rate before executing.

    IMPORTANT: Provide either 'amount' (cash) or 'amount_in_units' (units), not both.

    Returns:
        Order result with confirmation token
    """
    logger.info(f"Invoking place_limit_order tool: instrument_id={instrument_id}, rate={rate}")

    if amount is not None and amount_in_units is not None:
        validation_error = "Provide either 'amount' or 'amount_in_units', not both"
        await ctx.error(validation_error)
        return {"error": validation_error}

    if amount is None and amount_in_units is None:
        validation_error = "Must provide either 'amount' or 'amount_in_units'"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.place_limit_order(
            instrument_id=instrument_id,
            is_buy=is_buy,
            leverage=leverage,
            rate=rate,
            amount=amount,
            amount_in_units=amount_in_units,
            stop_loss_rate=stop_loss_rate,
            take_profit_rate=take_profit_rate,
            is_tsl_enabled=is_tsl_enabled,
            is_no_stop_loss=is_no_stop_loss,
            is_no_take_profit=is_no_take_profit,
        )

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error placing limit order: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def cancel_order(
    ctx: Context,
    order_id: Union[str, int] = Field(description="Order ID to cancel"),
    order_type: str = Field(description="Type of order to cancel: 'limit' (market-if-touched), 'open' (market open order), or 'close' (market close order)")
) -> Dict[str, Any]:
    """Cancel a pending order before it is executed.

    Supports cancelling three types of orders:
    - 'limit': Cancel a Market-if-touched (limit) order
    - 'open': Cancel a pending market order for opening a position
    - 'close': Cancel a pending market order for closing a position

    Returns:
        Cancellation result
    """
    order_id = str(order_id)

    logger.info(f"Invoking cancel_order tool: order_id={order_id}, order_type={order_type}")

    if order_type not in ("limit", "open", "close"):
        validation_error = "order_type must be 'limit', 'open', or 'close'"
        await ctx.error(validation_error)
        return {"error": validation_error}

    if not order_id or not order_id.strip():
        validation_error = "order_id cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        if order_type == "limit":
            result = client.cancel_limit_order(order_id)
        elif order_type == "open":
            result = client.cancel_open_order(order_id)
        else:
            result = client.cancel_close_order(order_id)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error cancelling order: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


# =====================
# Watchlist Tools
# =====================

@mcp.tool()
async def get_watchlists(ctx: Context) -> Dict[str, Any]:
    """Get all watchlists for the authenticated user.

    Returns:
        Watchlists with their IDs, names, and items
    """
    logger.info("Invoking get_watchlists tool")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_watchlists()

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting watchlists: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def create_watchlist(
    ctx: Context,
    name: str = Field(description="Name for the new watchlist (max 100 characters)")
) -> Dict[str, Any]:
    """Create a new watchlist.

    Returns:
        Created watchlist with its ID, name, and metadata
    """
    logger.info(f"Invoking create_watchlist tool: name={name}")

    if not name or not name.strip():
        validation_error = "name cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.create_watchlist(name)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error creating watchlist: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def delete_watchlist(
    ctx: Context,
    watchlist_id: Union[str, int] = Field(description="Watchlist ID to delete (from get_watchlists)")
) -> Dict[str, Any]:
    """Delete a watchlist and all its items permanently.

    Returns:
        Deletion confirmation
    """
    watchlist_id = str(watchlist_id)

    logger.info(f"Invoking delete_watchlist tool: watchlist_id={watchlist_id}")

    if not watchlist_id or not watchlist_id.strip():
        validation_error = "watchlist_id cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.delete_watchlist(watchlist_id)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error deleting watchlist: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def add_watchlist_items(
    ctx: Context,
    watchlist_id: Union[str, int] = Field(description="Watchlist ID (from get_watchlists or create_watchlist)"),
    instrument_ids: Union[str, int] = Field(description="Comma-separated instrument IDs to add (e.g., '1001,2045')")
) -> Dict[str, Any]:
    """Add instruments to an existing watchlist.

    Returns:
        Updated watchlist data
    """
    watchlist_id = str(watchlist_id)
    instrument_ids = str(instrument_ids)

    logger.info(f"Invoking add_watchlist_items tool: watchlist_id={watchlist_id}, instrument_ids={instrument_ids}")

    try:
        id_list = [int(id_str.strip()) for id_str in instrument_ids.split(",")]
        for inst_id in id_list:
            if inst_id <= 0:
                validation_error = "All instrument IDs must be positive integers"
                await ctx.error(validation_error)
                return {"error": validation_error}
    except ValueError:
        validation_error = "instrument_ids must be comma-separated integers (e.g., '1001,2045')"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.add_watchlist_items(watchlist_id, id_list)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error adding watchlist items: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def remove_watchlist_items(
    ctx: Context,
    watchlist_id: Union[str, int] = Field(description="Watchlist ID (from get_watchlists)"),
    instrument_ids: Union[str, int] = Field(description="Comma-separated instrument IDs to remove (e.g., '1001,2045')")
) -> Dict[str, Any]:
    """Remove instruments from a watchlist.

    Returns:
        Updated watchlist data
    """
    watchlist_id = str(watchlist_id)
    instrument_ids = str(instrument_ids)

    logger.info(f"Invoking remove_watchlist_items tool: watchlist_id={watchlist_id}, instrument_ids={instrument_ids}")

    try:
        id_list = [int(id_str.strip()) for id_str in instrument_ids.split(",")]
        for inst_id in id_list:
            if inst_id <= 0:
                validation_error = "All instrument IDs must be positive integers"
                await ctx.error(validation_error)
                return {"error": validation_error}
    except ValueError:
        validation_error = "instrument_ids must be comma-separated integers (e.g., '1001,2045')"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.remove_watchlist_items(watchlist_id, id_list)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error removing watchlist items: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def rename_watchlist(
    ctx: Context,
    watchlist_id: Union[str, int] = Field(description="Watchlist ID to rename (from get_watchlists)"),
    new_name: str = Field(description="New name for the watchlist (max 100 characters)")
) -> Dict[str, Any]:
    """Rename an existing watchlist.

    Returns:
        Rename confirmation
    """
    watchlist_id = str(watchlist_id)

    logger.info(f"Invoking rename_watchlist tool: watchlist_id={watchlist_id}, new_name={new_name}")

    if not new_name or not new_name.strip():
        validation_error = "new_name cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.rename_watchlist(watchlist_id, new_name)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error renaming watchlist: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


# =====================
# Users Info Tools
# =====================

@mcp.tool()
async def get_user_profile(
    ctx: Context,
    username: str = Field(description="eToro username to look up")
) -> Dict[str, Any]:
    """Get comprehensive profile data for an eToro user.

    Returns profile information including account status, verification levels,
    biographical data, and metadata.

    Returns:
        User profile data
    """
    logger.info(f"Invoking get_user_profile tool: username={username}")

    if not username or not username.strip():
        validation_error = "username cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_user_profile(username)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting user profile: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_user_performance(
    ctx: Context,
    username: str = Field(description="eToro username to get performance for")
) -> Dict[str, Any]:
    """Get historical performance metrics and gain data for a user.

    Returns monthly and yearly performance including gain percentages,
    risk-adjusted returns, and trading statistics.

    Returns:
        User performance/gain data
    """
    logger.info(f"Invoking get_user_performance tool: username={username}")

    if not username or not username.strip():
        validation_error = "username cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_user_performance(username)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting user performance: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_user_trade_info(
    ctx: Context,
    username: str = Field(description="eToro username"),
    period: str = Field(default="CurrMonth", description="Time period: CurrMonth, CurrQuarter, CurrYear, LastYear, LastTwoYears, OneMonthAgo, TwoMonthsAgo, ThreeMonthsAgo, SixMonthsAgo, OneYearAgo")
) -> Dict[str, Any]:
    """Get trading statistics for a specific user over a given time period.

    Returns:
        Trade info with statistics for the specified period
    """
    logger.info(f"Invoking get_user_trade_info tool: username={username}, period={period}")

    if not username or not username.strip():
        validation_error = "username cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    valid_periods = [
        "CurrMonth", "CurrQuarter", "CurrYear", "LastYear",
        "LastTwoYears", "OneMonthAgo", "TwoMonthsAgo",
        "ThreeMonthsAgo", "SixMonthsAgo", "OneYearAgo"
    ]
    if period not in valid_periods:
        validation_error = f"period must be one of: {', '.join(valid_periods)}"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_user_trade_info(username, period)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting user trade info: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def search_users(
    ctx: Context,
    period: str = Field(default="CurrMonth", description="Time period for metrics: CurrMonth, CurrQuarter, CurrYear, LastYear, LastTwoYears, OneMonthAgo, TwoMonthsAgo, ThreeMonthsAgo, SixMonthsAgo, OneYearAgo"),
    gain_min: Optional[int] = Field(default=None, description="Minimum gain percentage filter"),
    gain_max: Optional[int] = Field(default=None, description="Maximum gain percentage filter"),
    risk_score_min: Optional[int] = Field(default=None, description="Minimum daily risk score filter"),
    risk_score_max: Optional[int] = Field(default=None, description="Maximum daily risk score filter"),
    popular_investor: Optional[bool] = Field(default=None, description="Filter for Popular Investors only"),
    page_size: int = Field(default=10, description="Results per page"),
    page: int = Field(default=1, description="Page number")
) -> Dict[str, Any]:
    """Search and discover eToro users/traders with performance and risk filters.

    Use this for copy-trading research to find traders by gain, risk profile, and popularity.

    Returns:
        Search results with user profiles matching the filters
    """
    logger.info(f"Invoking search_users tool: period={period}, page={page}")

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.search_users(
            period=period,
            gain_min=gain_min,
            gain_max=gain_max,
            risk_score_min=risk_score_min,
            risk_score_max=risk_score_max,
            popular_investor=popular_investor,
            page_size=page_size,
            page=page,
        )

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error searching users: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


# =====================
# Feed Tools
# =====================

@mcp.tool()
async def get_user_feed(
    ctx: Context,
    user_id: Union[str, int] = Field(description="User ID to get feed for"),
    take: int = Field(default=20, description="Number of posts to retrieve (1-100)"),
    offset: int = Field(default=0, description="Number of posts to skip for pagination")
) -> Dict[str, Any]:
    """Get social feed posts for a specific eToro user.

    Returns the user's discussions, analyses, and other posted content.

    Returns:
        Feed posts with content, comments, and engagement metrics
    """
    user_id = str(user_id)

    logger.info(f"Invoking get_user_feed tool: user_id={user_id}")

    if not user_id or not user_id.strip():
        validation_error = "user_id cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_user_feed(user_id, take, offset)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting user feed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_instrument_feed(
    ctx: Context,
    market_id: Union[str, int] = Field(description="Instrument/market ID to get feed for"),
    take: int = Field(default=20, description="Number of posts to retrieve (1-100)"),
    offset: int = Field(default=0, description="Number of posts to skip for pagination")
) -> Dict[str, Any]:
    """Get social feed posts about a specific financial instrument.

    Returns discussions, analyses, and content related to the instrument.

    Returns:
        Feed posts with content, comments, and engagement metrics
    """
    market_id = str(market_id)

    logger.info(f"Invoking get_instrument_feed tool: market_id={market_id}")

    if not market_id or not market_id.strip():
        validation_error = "market_id cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.get_instrument_feed(market_id, take, offset)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting instrument feed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def create_post(
    ctx: Context,
    owner: int = Field(description="User ID of the post owner"),
    message: str = Field(description="Text content of the discussion post"),
    tags: Optional[str] = Field(default=None, description="Optional JSON string of tags object for tagging instruments/markets"),
    mentions: Optional[str] = Field(default=None, description="Optional JSON string of mentions object for referencing users")
) -> Dict[str, Any]:
    """Create a new discussion post in the eToro social feed.

    Returns:
        Created post with metadata and timestamps
    """
    logger.info(f"Invoking create_post tool: owner={owner}")

    if not message or not message.strip():
        validation_error = "message cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    tags_dict = None
    mentions_dict = None

    if tags:
        try:
            tags_dict = json.loads(tags)
        except json.JSONDecodeError:
            validation_error = "tags must be a valid JSON string"
            await ctx.error(validation_error)
            return {"error": validation_error}

    if mentions:
        try:
            mentions_dict = json.loads(mentions)
        except json.JSONDecodeError:
            validation_error = "mentions must be a valid JSON string"
            await ctx.error(validation_error)
            return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.create_post(owner, message, tags_dict, mentions_dict)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error creating post: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def create_comment(
    ctx: Context,
    post_id: Union[str, int] = Field(description="Post ID to comment on"),
    owner: int = Field(description="User ID of the comment author"),
    message: str = Field(description="Text content of the comment")
) -> Dict[str, Any]:
    """Create a comment on an existing discussion post.

    Returns:
        Created comment with metadata
    """
    post_id = str(post_id)

    logger.info(f"Invoking create_comment tool: post_id={post_id}, owner={owner}")

    if not post_id or not post_id.strip():
        validation_error = "post_id cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    if not message or not message.strip():
        validation_error = "message cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        cred_error = check_credentials()
        if cred_error:
            await ctx.error(cred_error)
            return {"error": cred_error}

        result = client.create_comment(post_id, owner, message)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error creating comment: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


# Main entry point

def main():
    """Run the MCP server with CLI argument support."""
    parser = argparse.ArgumentParser(
        description='eToro Model Context Protocol (MCP) server'
    )
    parser.add_argument('--sse', action='store_true', help='Use SSE transport')
    parser.add_argument('--streamable-http', action='store_true', help='Use streamable HTTP transport')
    parser.add_argument('--port', type=int, default=8080, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--log-dir', type=str, help='Directory to store log files')

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        os.environ["ETORO_MCP_DEBUG"] = "1"
        logger.setLevel(logging.DEBUG)

    # Set custom log directory if provided
    if args.log_dir:
        log_dir = os.path.abspath(args.log_dir)
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "etoro_mcp_server.log")

        # Reconfigure logging
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

    # Log startup information
    logger.info('Starting eToro MCP Server')

    # Run server with appropriate transport
    if args.streamable_http:
        logger.info(f'Using streamable HTTP transport on port {args.port}')
        mcp.run(transport='streamable-http', port=args.port)
    elif args.sse:
        logger.info(f'Using SSE transport on port {args.port}')
        mcp.settings.port = args.port
        mcp.run(transport='sse')
    else:
        logger.info('Using standard stdio transport')
        mcp.run()


if __name__ == "__main__":
    main()
