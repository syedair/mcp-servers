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
    """
)

# Initialize client and credentials validation state
client = EtoroClient(
    base_url=os.environ.get("ETORO_BASE_URL", "https://public-api.etoro.com"),
    api_key=os.environ.get("ETORO_API_KEY", ""),
    user_key=os.environ.get("ETORO_USER_KEY", ""),
    account_type=os.environ.get("ETORO_ACCOUNT_TYPE", "demo")
)
credentials_valid = False


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
    global credentials_valid, client

    logger.info(f"Invoking search_instruments tool: search_term={search_term}")

    try:
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    global credentials_valid, client

    logger.info(f"Invoking resolve_symbol tool: symbol={symbol}")

    try:
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    instrument_ids: str = Field(description="Comma-separated instrument IDs (e.g., '1001' or '1001,2045')")
) -> Dict[str, Any]:
    """Get metadata for instruments including display names, exchange IDs, and classification.

    Returns:
        Instrument metadata with instrumentDisplayDatas array
    """
    global credentials_valid, client

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
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    instrument_ids: str = Field(description="Comma-separated instrument IDs (e.g., '1001' or '1001,2045,3078'). Max 100.")
) -> Dict[str, Any]:
    """Get current real-time bid/ask prices for instruments.

    Returns:
        Current rates with bid/ask prices for each instrument
    """
    global credentials_valid, client

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
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    global credentials_valid, client

    logger.info("Invoking get_account_info tool")

    try:
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    global credentials_valid, client

    logger.info("Invoking get_portfolio tool")

    try:
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    global credentials_valid, client

    logger.info("Invoking get_positions tool")

    try:
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    global credentials_valid, client

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
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    global credentials_valid, client

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
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    position_id: str = Field(description="Position ID to close (from get_positions)"),
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
    global credentials_valid, client

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
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

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
    order_id: str = Field(description="Order ID to look up (from create_position response)")
) -> Dict[str, Any]:
    """Get order information and position details for a specific order.

    Use this to track order execution status and find which positions were created
    from a specific order. The response includes PositionID values.

    Returns:
        Order details with execution status and position information
    """
    global credentials_valid, client

    logger.info(f"Invoking get_order_info tool: order_id={order_id}")

    if not order_id or len(order_id.strip()) == 0:
        validation_error = "order_id cannot be empty"
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

        result = client.get_order_info(order_id)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error getting order info: {str(e)}"
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

    # Validate credentials on startup
    try:
        global credentials_valid
        credentials_valid = client.validate_credentials()
        if credentials_valid:
            logger.info("Successfully validated eToro API credentials on startup")
        else:
            logger.warning("Failed to validate eToro API credentials on startup")
    except Exception as e:
        logger.error(f"Error during startup credential validation: {type(e).__name__}", exc_info=True)

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
