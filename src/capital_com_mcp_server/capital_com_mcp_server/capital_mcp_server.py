#!/usr/bin/env python3
"""
Capital.com MCP Server - Exposes Capital.com API as MCP tools using FastMCP
"""

import argparse
import json
import logging
import os
import sys
import re
import requests
from typing import Dict, Any, List, Optional, Union
import pathlib

# Import the Capital.com client
try:
    from .capital_client import CapitalClient
except ImportError:
    from capital_client import CapitalClient

# Import FastMCP
from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

# Configure logging
logger = logging.getLogger("capital_mcp_server")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Check for debug mode
if os.environ.get("CAPITAL_MCP_DEBUG", "0") == "1":
    logger.setLevel(logging.DEBUG)
    logger.debug("Debug logging enabled")

# Initialize FastMCP
mcp = FastMCP(
    name="capital-com-mcp-server",
    description="Capital.com MCP Server for trading operations",
    instructions="""
    # Capital.com MCP Server

    This server provides tools to interact with the Capital.com trading API.

    ## Best Practices

    - Authentication happens automatically using environment variables
    - Use search_markets to find available markets and epics
    - Check account information before creating positions
    - Consider using stop loss and take profit levels when creating positions (optional but recommended)
    - Monitor open positions regularly

    ## Position Management Workflow

    **IMPORTANT**: Position creation and management requires understanding the difference between dealReference and dealId:

    1. **Creating Positions**: `create_position` returns a `dealReference` (order reference starting with 'o_')
    2. **Getting dealId**: After creation, call `get_positions` to find the new position and get its `dealId`
    3. **Managing Positions**: Use the `dealId` (not dealReference) for `close_position` and `update_position`

    **Example Workflow**:
    ```
    1. result = create_position(epic="TSLA", direction="BUY", size=0.1)
       → Returns: {"dealReference": "o_abc123..."}
    
    2. positions = get_positions()
       → Find position with matching epic/size/direction
       → Get the dealId from position.position.dealId
    
    3. close_position(deal_id=dealId) or update_position(deal_id=dealId, ...)
    ```

    ## Tool Selection Guide

    - Use `get_account_info` when: You need to check account balance or details
    - Use `search_markets` when: You need to find available markets to trade and epics
    - Use `get_prices` when: You need current price information for a specific instrument
    - Use `get_historical_prices` when: You need historical price data with custom time resolution
    - Use `get_positions` when: You need to check open positions OR get dealId after creating a position
    - Use `create_position` when: You want to open a new trading position (returns dealReference)
    - Use `update_position` when: You want to modify stop loss or take profit levels (requires dealId from get_positions)
    - Use `close_position` when: You want to close an existing position (requires dealId from get_positions)
    - Use `get_watchlists` when: You want to see saved watchlists
    """
)

# Initialize client and authentication state
client = CapitalClient(
    base_url=os.environ.get("CAPITAL_BASE_URL", "https://demo-api-capital.backend-capital.com"),
    api_key=os.environ.get("CAPITAL_API_KEY", ""),
    identifier=os.environ.get("CAPITAL_IDENTIFIER", ""),
    password=os.environ.get("CAPITAL_PASSWORD", "")
)
authenticated = False

# Helper function to handle authentication and retries


@mcp.tool()
async def get_account_info(ctx: Context) -> Dict[str, Any]:
    """Get account information from Capital.com.

    This tool retrieves account information including balance, open positions, and account details.

    Returns:
        Dict[str, Any]: Account information
    """
    global authenticated, client
    
    logger.info("Invoking get_account_info tool")
    
    
    try:
        # Ensure we're authenticated before making any request
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        # Client method now handles re-authentication automatically
        account_info = client.get_account_info()
        return account_info
    
    except Exception as e:
        error_msg = f"Error getting account info: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def search_markets(
    ctx: Context,
    search_term: Optional[str] = Field(default=None, description="Search term (e.g., 'silver', 'Apple', 'Gold')"),
    epics: Optional[str] = Field(default=None, description="Comma-separated epics (e.g., 'SILVER,NATURALGAS', max 50)"),
    limit: int = Field(default=10, description="Maximum number of results to return"),
) -> Dict[str, Any]:
    """Search for markets on Capital.com.

    This tool searches for markets (instruments) on Capital.com. You can search by term or specific epics.
    If both search_term and epics are provided, search_term takes priority.

    Args:
        ctx: MCP context
        search_term: Search term to find markets (optional)
        epics: Comma-separated epic identifiers, max 50 (optional)
        limit: Maximum number of results to return
        
    Returns:
        Dict[str, Any]: Market search results
    """
    global authenticated, client
    
    logger.info(f"Invoking search_markets tool with search_term: {search_term}, epics: {epics}")
    
    
    # Note: If both parameters are None, API will return all available markets
    
    # Validate epics limit if provided
    if epics is not None:
        epic_list = [epic.strip() for epic in epics.split(',') if epic.strip()]
        if len(epic_list) > 50:
            error_msg = "Maximum 50 epics allowed"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
    
    try:
        # Ensure we're authenticated before making any request
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        # Client method now handles re-authentication automatically
        result = client.search_markets(search_term, epics, limit)
        
        # Handle different response formats: epics returns "marketDetails", search returns "markets"
        if "marketDetails" in result:
            # Convert marketDetails format to markets format for consistency
            market_details = result["marketDetails"]
            markets = []
            
            for detail in market_details:
                instrument = detail.get("instrument", {})
                snapshot = detail.get("snapshot", {})
                
                # Convert to markets format
                market = {
                    "instrumentName": instrument.get("name", ""),
                    "epic": instrument.get("epic", ""),
                    "symbol": instrument.get("symbol", ""),
                    "instrumentType": instrument.get("type", ""),
                    "marketStatus": snapshot.get("marketStatus", ""),
                    "lotSize": instrument.get("lotSize", 1),
                    "bid": snapshot.get("bid"),
                    "offer": snapshot.get("offer"),
                    "high": snapshot.get("high"),
                    "low": snapshot.get("low"),
                    "percentageChange": snapshot.get("percentageChange"),
                    "netChange": snapshot.get("netChange"),
                    "updateTime": snapshot.get("updateTime"),
                    "delayTime": snapshot.get("delayTime", 0),
                    "streamingPricesAvailable": instrument.get("streamingPricesAvailable", False),
                    "scalingFactor": snapshot.get("scalingFactor", 1),
                    "marketModes": snapshot.get("marketModes", [])
                }
                
                # Remove None values
                market = {k: v for k, v in market.items() if v is not None}
                markets.append(market)
            
            result = {"markets": markets}
        
        # Limit the number of results if needed
        if "markets" in result and len(result["markets"]) > limit:
            result["markets"] = result["markets"][:limit]
            result["markets_truncated"] = True
            
        return result
    
    except Exception as e:
        error_msg = f"Error searching markets: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def get_prices(
    ctx: Context,
    epic: str = Field(description="The epic identifier for the instrument"),
    resolution: Optional[str] = Field(default=None, description="Time resolution (optional, e.g., MINUTE, HOUR, DAY, WEEK). Defaults to MINUTE if not specified."),
) -> Dict[str, Any]:
    """Get prices for a specific instrument.

    This tool retrieves current price information for a specific instrument.

    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument
        resolution: Time resolution (optional)

    Returns:
        Dict[str, Any]: Price information for the instrument
    """
    global authenticated, client
    
    logger.info(f"Invoking get_prices tool for epic: {epic}")
    
    try:
        # Use client method with proper default handling
        if resolution is not None:
            prices = client.get_prices(epic, resolution)
        else:
            prices = client.get_prices(epic)  # Use client's default resolution
        return prices
    
    except Exception as e:
        error_msg = f"Error getting prices: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def get_historical_prices(
    ctx: Context,
    epic: str = Field(description="The epic identifier for the instrument. You need to get this from the markets api"),
    resolution: str = Field(description="Time resolution: MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY, WEEK"),
    max: Optional[int] = Field(default=None, description="Maximum number of bars to return (default: 10, max: 1000)"),
    from_date: Optional[str] = Field(default=None, description="Start date in ISO format (e.g., '2022-02-24T00:00:00')"),
    to_date: Optional[str] = Field(default=None, description="End date in ISO format"),
) -> Dict[str, Any]:
    """Get historical price data for a specific instrument.

    This tool retrieves historical price data for a specific instrument with custom granularity.

    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument. You need to get this from the markets api
        resolution: Time resolution (MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY, WEEK)
        max: Maximum number of bars to return (default: 10, max: 1000)
        from_date: Start date in ISO format (e.g., "2022-02-24T00:00:00")
        to_date: End date in ISO format (optional)

    Returns:
        Dict[str, Any]: Historical price information for the instrument
    """
    global authenticated, client
    
    logger.info(f"Invoking get_historical_prices tool for epic: {epic}, resolution: {resolution}")
    
    # Check if authenticated
    if not authenticated:
        logger.info("Not authenticated yet, attempting authentication")
        auth_result = client.authenticate()
        authenticated = auth_result
        if not authenticated:
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
    
    try:
        # Set default for max if not provided (API default is 10)
        max_value = max if max is not None else 10
        
        result = client.get_historical_prices(epic, resolution, max_value, from_date, to_date)
        
        if "error" in result:
            error_msg = f"Error getting historical prices: {result['error']}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error getting historical prices: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def get_positions(ctx: Context) -> Dict[str, Any]:
    """Get all open positions.
    
    This tool retrieves all currently open trading positions.
    
    Returns:
        Dict[str, Any]: Open positions
    """
    global authenticated, client
    
    logger.info("Invoking get_positions tool")
    
    try:
        # Ensure we're authenticated before making any request
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        # Client method now handles re-authentication automatically
        positions = client.get_positions()
        return positions
    
    except Exception as e:
        error_msg = f"Error getting positions: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def create_position(
    ctx: Context,
    epic: str = Field(description="The epic identifier for the instrument"),
    direction: str = Field(description="Trade direction (BUY or SELL)"),
    size: float = Field(description="Position size"),
    stop_level: Optional[float] = Field(default=None, description="Stop loss level (optional)"),
    profit_level: Optional[float] = Field(default=None, description="Take profit level (optional)"),
    leverage: Optional[float] = Field(default=None, description="Leverage ratio (e.g., 20 for 20:1) (optional)"),
    guaranteed_stop: Optional[bool] = Field(default=None, description="Whether to use a guaranteed stop (optional)"),
) -> Dict[str, Any]:
    """Create a new trading position.

    This tool creates a new trading position for the specified instrument.
    Returns a 'dealReference' (order reference) upon successful creation.

    IMPORTANT WORKFLOW:
    1. This tool returns a 'dealReference' (order reference) upon successful creation
    2. To get the 'dealId' needed for close_position and update_position, call get_positions 
       after creation and find the position with matching details (epic, size, direction)
    3. The dealId from get_positions is what you need for managing the position

    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument
        direction: Trade direction (BUY or SELL)
        size: Position size
        stop_level: Stop loss level (optional)
        profit_level: Take profit level (optional)
        leverage: Leverage ratio (e.g., 20 for 20:1) (optional)
        guaranteed_stop: Whether to use a guaranteed stop (optional)

    Returns:
        Dict[str, Any]: Position creation result with dealReference (order reference).
                       Use get_positions to obtain the dealId for position management.
    """
    global authenticated, client
    
    logger.info(f"Invoking create_position tool: {epic}, {direction}, {size}")
    
    # Validate inputs
    if not epic or len(epic.strip()) == 0:
        validation_error = "Epic identifier cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    if direction not in ["BUY", "SELL"]:
        validation_error = "Direction must be either 'BUY' or 'SELL'"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    if size <= 0:
        validation_error = "Size must be greater than 0"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    # Check if authenticated
    if not authenticated:
        logger.info("Not authenticated yet, attempting authentication")
        auth_result = client.authenticate()
        authenticated = auth_result
        if not authenticated:
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
    
    try:
        result = client.create_position(epic, direction, size, stop_level, profit_level, leverage, guaranteed_stop)
        
        if "error" in result:
            error_msg = f"Error creating position: {result['error']}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return result
            
        logger.info(f"Successfully created position for {epic}: {result}")
        return result
    
    except Exception as e:
        error_msg = f"Error creating position: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def close_position(
    ctx: Context,
    deal_id: str = Field(description="The deal ID to close"),
) -> Dict[str, Any]:
    """Close an open position.

    This tool closes an open position with the specified deal ID.
    
    IMPORTANT: Use the dealId from get_positions, not the dealReference from create_position.
    The dealId is found in the position.position.dealId field when calling get_positions.

    Args:
        ctx: MCP context
        deal_id: The deal ID to close (from get_positions, not the dealReference from create_position)

    Returns:
        Dict[str, Any]: Position closure result
    """
    global authenticated, client
    
    logger.info(f"Invoking close_position tool for deal_id: {deal_id}")
    
    # Validate inputs
    if not deal_id or len(deal_id.strip()) == 0:
        validation_error = "Deal ID cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    # Check if authenticated
    if not authenticated:
        logger.info("Not authenticated yet, attempting authentication")
        auth_result = client.authenticate()
        authenticated = auth_result
        if not authenticated:
            logger.error(error_msg)
    
    try:
        result = client.close_position(deal_id)
        
        if "error" in result:
            await ctx.error(f"Failed to close position: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error closing position: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(f"Failed to close position with deal ID: {deal_id}. Please try again.")
        return {"error": f"Failed to close position with deal ID: {deal_id}"}

@mcp.tool()
async def update_position(
    ctx: Context,
    deal_id: str = Field(description="The deal ID of the position to update"),
    stop_level: Optional[float] = Field(default=None, description="New stop loss level (optional)"),
    profit_level: Optional[float] = Field(default=None, description="New take profit level (optional)"),
) -> Dict[str, Any]:
    """Update an existing trading position.

    This tool updates an existing position with new stop loss and/or take profit settings.
    
    IMPORTANT: Use the dealId from get_positions, not the dealReference from create_position.
    The dealId is found in the position.position.dealId field when calling get_positions.

    Args:
        ctx: MCP context
        deal_id: The deal ID of the position to update (from get_positions, not dealReference from create_position)
        stop_level: New stop loss level (optional)
        profit_level: New take profit level (optional)

    Returns:
        Dict[str, Any]: Position update result
    """
    global authenticated, client
    
    logger.info(f"Invoking update_position tool for deal_id: {deal_id}")
    
    # Validate inputs
    if not deal_id or len(deal_id.strip()) == 0:
        validation_error = "Deal ID cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    if stop_level is None and profit_level is None:
        validation_error = "At least one of stop_level or profit_level must be provided"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    # Check if authenticated
    if not authenticated:
        logger.info("Not authenticated yet, attempting authentication")
        auth_result = client.authenticate()
        authenticated = auth_result
        if not authenticated:
            logger.error(error_msg)
    
    try:
        result = client.update_position(deal_id, stop_level, profit_level)
        
        if "error" in result:
            await ctx.error(f"Failed to update position: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error updating position: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(f"Failed to update position with deal ID: {deal_id}. Please try again.")
        return {"error": f"Failed to update position with deal ID: {deal_id}"}

@mcp.tool()
async def get_watchlists(ctx: Context) -> Dict[str, Any]:
    """Get all watchlists.
    
    This tool retrieves all watchlists and their contents.
    
    Returns:
        Dict[str, Any]: Watchlists
    """
    global authenticated, client
    
    logger.info("Invoking get_watchlists tool")
    
    # Check if authenticated
    if not authenticated:
        logger.info("Not authenticated yet, attempting authentication")
        auth_result = client.authenticate()
        authenticated = auth_result
        if not authenticated:
            logger.error(error_msg)
    
    try:
        result = client.get_watchlists()
        
        if "error" in result:
            await ctx.error(f"Failed to get watchlists: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error getting watchlists: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error("Failed to get watchlists. Please try again.")
        return {"error": "Failed to get watchlists"}


def main():
    """Run the MCP server with CLI argument support."""
    parser = argparse.ArgumentParser(
        description='Capital.com Model Context Protocol (MCP) server'
    )
    parser.add_argument('--sse', action='store_true', help='Use SSE transport')
    parser.add_argument('--port', type=int, default=8080, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--log-dir', type=str, help='Directory to store log files')

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        os.environ["CAPITAL_MCP_DEBUG"] = "1"
        logger.setLevel(logging.DEBUG)
        
    # Set custom log directory if provided
    if args.log_dir:
        log_dir = os.path.abspath(args.log_dir)
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "capital_mcp_server.log")
        
        # Reconfigure logging
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

    # Log startup information
    logger.info('Starting Capital.com MCP Server')

    # Try to authenticate on startup
    try:
        global authenticated
        authenticated = client.authenticate()
        if authenticated:
            logger.info("Successfully authenticated with Capital.com API on startup")
        else:
            logger.warning("Failed to authenticate with Capital.com API on startup")
    except Exception as e:
        logger.error(f"Error during startup authentication: {type(e).__name__}", exc_info=True)

    # Run server with appropriate transport
    if args.sse:
        logger.info(f'Using SSE transport on port {args.port}')
        mcp.settings.port = args.port
        mcp.run(transport='sse')
    else:
        logger.info('Using standard stdio transport')
        mcp.run()


if __name__ == "__main__":
    main()
