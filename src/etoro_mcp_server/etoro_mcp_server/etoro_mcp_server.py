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

    ## Best Practices

    - Authentication happens automatically using environment variables (x-api-key, x-user-key)
    - Use search_instruments to find available instruments and their IDs (instrument IDs are integers)
    - Check account information before creating positions
    - Consider using stop loss and take profit levels when creating positions (optional but recommended)
    - Monitor open positions regularly

    ## Key Differences from Other Trading APIs

    - **Instrument IDs are integers** (e.g., 1001, 2045), not string symbols
    - **Static API keys** - no session tokens or re-authentication needed
    - **Direct position management** - position_id is used directly (no dealReference/dealId conversion)
    - **Account types**: Demo accounts use /api/demo/v1 endpoints, real accounts use /api/v1

    ## Position Management Workflow

    1. **Search Instruments**: Use `search_instruments` to find instruments and get their integer IDs
    2. **Create Position**: Use `create_position` with the instrument_id (integer)
    3. **Manage Position**: The returned position_id can be used directly with `close_position` and `update_position`

    **Example Workflow**:
    ```
    1. instruments = search_instruments(search_term="Apple")
       → Returns: [{"instrumentId": 1001, "name": "Apple Inc.", ...}]

    2. position = create_position(instrument_id=1001, direction="BUY", amount=100)
       → Returns: {"position_id": "abc123", "status": "open", ...}

    3. close_position(position_id="abc123") or update_position(position_id="abc123", ...)
    ```

    ## Tool Selection Guide

    - Use `get_account_info` when: You need to check account balance, equity, or margin
    - Use `search_instruments` when: You need to find instruments to trade and get their integer IDs
    - Use `get_instrument_metadata` when: You need detailed info about spreads, trading hours, min/max trade amounts
    - Use `get_current_rates` when: You need real-time bid/ask prices for specific instruments
    - Use `get_positions` when: You need to check all open positions
    - Use `create_position` when: You want to open a new position with leverage, stop loss, take profit
    - Use `update_position` when: You want to modify stop loss or take profit levels on existing positions
    - Use `close_position` when: You want to close an existing position
    """
)

# Initialize client and credentials validation state
client = EtoroClient(
    base_url=os.environ.get("ETORO_BASE_URL", "https://api.etoro.com"),
    api_key=os.environ.get("ETORO_API_KEY", ""),
    user_key=os.environ.get("ETORO_USER_KEY", ""),
    account_type=os.environ.get("ETORO_ACCOUNT_TYPE", "demo")
)
credentials_valid = False


# Priority 1: Core Trading Tools (8 tools)

@mcp.tool()
async def search_instruments(
    ctx: Context,
    search_term: Optional[str] = Field(default=None, description="Search query (e.g., 'Apple', 'Bitcoin', 'EUR/USD')"),
    category: Optional[str] = Field(default=None, description="Filter by category: 'stocks', 'crypto', 'currencies', 'commodities', 'indices'"),
    limit: int = Field(default=10, description="Maximum number of results to return")
) -> Dict[str, Any]:
    """Search for tradeable instruments on eToro.

    This tool searches for instruments and returns their details including the integer instrument ID
    needed for trading operations.

    Args:
        ctx: MCP context
        search_term: Search query (optional)
        category: Filter by instrument category (optional)
        limit: Maximum number of results

    Returns:
        Dict[str, Any]: Search results with instrument IDs and details
    """
    global credentials_valid, client

    logger.info(f"Invoking search_instruments tool: search_term={search_term}, category={category}")

    try:
        # Validate credentials if not already validated
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

        result = client.search_instruments(search_term, category, limit)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error searching instruments: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_account_info(ctx: Context) -> Dict[str, Any]:
    """Get account information from eToro.

    This tool retrieves account information including balance, equity, margin, and available funds.

    Returns:
        Dict[str, Any]: Account information
    """
    global credentials_valid, client

    logger.info("Invoking get_account_info tool")

    try:
        # Validate credentials if not already validated
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
async def get_positions(ctx: Context) -> Dict[str, Any]:
    """Get all open trading positions.

    This tool retrieves all currently open positions with their details including position_id,
    instrument, direction, amount, leverage, and profit/loss.

    Returns:
        Dict[str, Any]: Open positions
    """
    global credentials_valid, client

    logger.info("Invoking get_positions tool")

    try:
        # Validate credentials if not already validated
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


@mcp.tool()
async def create_position(
    ctx: Context,
    instrument_id: int = Field(description="Instrument ID (integer, e.g., 1001). Get from search_instruments."),
    direction: str = Field(description="Trade direction: 'BUY' or 'SELL'"),
    amount: float = Field(description="Investment amount in account currency"),
    leverage: int = Field(default=1, description="Leverage multiplier (1, 2, 5, 10, 20, etc.)"),
    stop_loss: Optional[float] = Field(default=None, description="Stop loss price level (optional)"),
    take_profit: Optional[float] = Field(default=None, description="Take profit price level (optional)")
) -> Dict[str, Any]:
    """Create a new trading position on eToro.

    This tool creates a new position with optional stop loss and take profit levels.

    IMPORTANT: instrument_id must be a positive integer. Use search_instruments to get instrument IDs.

    Args:
        ctx: MCP context
        instrument_id: Integer instrument ID (from search_instruments)
        direction: Trade direction ('BUY' or 'SELL')
        amount: Investment amount
        leverage: Leverage multiplier
        stop_loss: Stop loss price level (optional)
        take_profit: Take profit price level (optional)

    Returns:
        Dict[str, Any]: Position creation result with position_id
    """
    global credentials_valid, client

    logger.info(f"Invoking create_position tool: instrument_id={instrument_id}, direction={direction}, amount={amount}")

    # Validate inputs
    if not isinstance(instrument_id, int) or instrument_id <= 0:
        validation_error = "instrument_id must be a positive integer"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}

    if direction not in ["BUY", "SELL"]:
        validation_error = "direction must be 'BUY' or 'SELL'"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}

    if amount <= 0:
        validation_error = "amount must be greater than 0"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}

    if leverage < 1:
        validation_error = "leverage must be at least 1"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        # Validate credentials if not already validated
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

        result = client.create_position(instrument_id, direction, amount, leverage, stop_loss, take_profit)

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
    position_id: str = Field(description="Position ID to close (from get_positions)")
) -> Dict[str, Any]:
    """Close an open trading position.

    This tool closes an existing position by its position_id.

    Args:
        ctx: MCP context
        position_id: Position ID to close (from get_positions)

    Returns:
        Dict[str, Any]: Position closure result
    """
    global credentials_valid, client

    logger.info(f"Invoking close_position tool: position_id={position_id}")

    # Validate inputs
    if not position_id or len(position_id.strip()) == 0:
        validation_error = "position_id cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        # Validate credentials if not already validated
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

        result = client.close_position(position_id)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error closing position: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def update_position(
    ctx: Context,
    position_id: str = Field(description="Position ID to update (from get_positions)"),
    stop_loss: Optional[float] = Field(default=None, description="New stop loss price level (optional)"),
    take_profit: Optional[float] = Field(default=None, description="New take profit price level (optional)")
) -> Dict[str, Any]:
    """Update stop loss and/or take profit for an existing position.

    This tool updates the risk management parameters of an open position.

    Args:
        ctx: MCP context
        position_id: Position ID to update
        stop_loss: New stop loss price level (optional)
        take_profit: New take profit price level (optional)

    Returns:
        Dict[str, Any]: Position update result
    """
    global credentials_valid, client

    logger.info(f"Invoking update_position tool: position_id={position_id}")

    # Validate inputs
    if not position_id or len(position_id.strip()) == 0:
        validation_error = "position_id cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}

    if stop_loss is None and take_profit is None:
        validation_error = "At least one parameter (stop_loss or take_profit) must be provided"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        # Validate credentials if not already validated
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

        result = client.update_position(position_id, stop_loss, take_profit)

        if "error" in result:
            await ctx.error(result["error"])

        return result

    except Exception as e:
        error_msg = f"Error updating position: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


@mcp.tool()
async def get_instrument_metadata(
    ctx: Context,
    instrument_id: int = Field(description="Instrument ID (integer). Get from search_instruments.")
) -> Dict[str, Any]:
    """Get detailed metadata for a specific instrument.

    This tool retrieves comprehensive information about an instrument including spread,
    trading hours, minimum/maximum trade amounts, and other trading parameters.

    Args:
        ctx: MCP context
        instrument_id: Integer instrument ID

    Returns:
        Dict[str, Any]: Instrument metadata
    """
    global credentials_valid, client

    logger.info(f"Invoking get_instrument_metadata tool: instrument_id={instrument_id}")

    # Validate inputs
    if not isinstance(instrument_id, int) or instrument_id <= 0:
        validation_error = "instrument_id must be a positive integer"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        # Validate credentials if not already validated
        if not credentials_valid:
            error_msg = "API credentials not validated. Please check your eToro API keys."
            await ctx.error(error_msg)
            return {"error": error_msg}

        result = client.get_instrument_metadata(instrument_id)

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
    instrument_ids: str = Field(description="Comma-separated instrument IDs (e.g., '1001' or '1001,2045,3078')")
) -> Dict[str, Any]:
    """Get current real-time bid/ask prices for instruments.

    This tool retrieves the latest market prices for one or more instruments.

    Args:
        ctx: MCP context
        instrument_ids: Comma-separated instrument IDs (integers as string)

    Returns:
        Dict[str, Any]: Current rates with bid/ask prices
    """
    global credentials_valid, client

    logger.info(f"Invoking get_current_rates tool: instrument_ids={instrument_ids}")

    # Validate and parse instrument IDs
    try:
        id_list = [int(id_str.strip()) for id_str in instrument_ids.split(",")]

        # Validate all IDs are positive
        for inst_id in id_list:
            if inst_id <= 0:
                validation_error = "All instrument IDs must be positive integers"
                logger.error(validation_error)
                await ctx.error(validation_error)
                return {"error": validation_error}

    except ValueError:
        validation_error = "instrument_ids must be comma-separated integers (e.g., '1001,2045')"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}

    try:
        # Validate credentials if not already validated
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
