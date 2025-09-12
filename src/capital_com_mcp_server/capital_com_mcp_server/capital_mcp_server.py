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
    guaranteed_stop: Optional[bool] = Field(default=None, description="Must be true if a guaranteed stop is required (cannot be used with trailing_stop or hedging mode)"),
    trailing_stop: Optional[bool] = Field(default=None, description="Must be true if a trailing stop is required (requires stop_distance, cannot be used with guaranteed_stop)"),
    stop_level: Optional[float] = Field(default=None, description="Price level when a stop loss will be triggered"),
    stop_distance: Optional[float] = Field(default=None, description="Distance between current and stop loss triggering price (required if trailing_stop is true)"),
    stop_amount: Optional[float] = Field(default=None, description="Loss amount when a stop loss will be triggered"),
    profit_level: Optional[float] = Field(default=None, description="Price level when a take profit will be triggered"),
    profit_distance: Optional[float] = Field(default=None, description="Distance between current and take profit triggering price"),
    profit_amount: Optional[float] = Field(default=None, description="Profit amount when a take profit will be triggered"),
) -> Dict[str, Any]:
    """Create a new trading position with comprehensive stop/profit options including trailing stops.

    This tool creates a new trading position with full Capital.com API support including trailing stops,
    guaranteed stops, and multiple stop/profit configuration options.

    IMPORTANT WORKFLOW:
    1. This tool returns a 'dealReference' (order reference) upon successful creation
    2. To get the 'dealId' needed for close_position and update_position, call get_positions 
       after creation and find the position with matching details (epic, size, direction)
    3. The dealId from get_positions is what you need for managing the position

    STOP LOSS OPTIONS (mutually exclusive):
    - guaranteed_stop: Cannot be used with trailing_stop or in hedging mode
    - trailing_stop: Requires stop_distance, cannot be used with guaranteed_stop

    STOP LOSS LEVELS (choose one):
    - stop_level: Specific price level for stop loss
    - stop_distance: Distance from current price (required for trailing stops)
    - stop_amount: Specific loss amount

    TAKE PROFIT LEVELS (choose one):
    - profit_level: Specific price level for take profit
    - profit_distance: Distance from current price
    - profit_amount: Specific profit amount

    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument
        direction: Trade direction (BUY or SELL)
        size: Position size
        guaranteed_stop: Guaranteed stop loss (premium feature, cannot be used with trailing_stop)
        trailing_stop: Trailing stop loss that follows price (requires stop_distance)
        stop_level: Specific stop loss price level
        stop_distance: Stop loss distance from current price (points)
        stop_amount: Stop loss amount in account currency
        profit_level: Specific take profit price level
        profit_distance: Take profit distance from current price (points)
        profit_amount: Take profit amount in account currency

    Returns:
        Dict[str, Any]: Position creation result with dealReference and metadata about active features.
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
        result = client.create_position(
            epic, direction, size, guaranteed_stop, trailing_stop, 
            stop_level, stop_distance, stop_amount, 
            profit_level, profit_distance, profit_amount
        )
        
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
    guaranteed_stop: Optional[bool] = Field(default=None, description="Must be true if a guaranteed stop is required (cannot be used with trailing_stop or hedging mode)"),
    trailing_stop: Optional[bool] = Field(default=None, description="Must be true if a trailing stop is required (requires stop_distance, cannot be used with guaranteed_stop)"),
    stop_level: Optional[float] = Field(default=None, description="Price level when a stop loss will be triggered"),
    stop_distance: Optional[float] = Field(default=None, description="Distance between current and stop loss triggering price (required if trailing_stop is true)"),
    stop_amount: Optional[float] = Field(default=None, description="Loss amount when a stop loss will be triggered"),
    profit_level: Optional[float] = Field(default=None, description="Price level when a take profit will be triggered"),
    profit_distance: Optional[float] = Field(default=None, description="Distance between current and take profit triggering price"),
    profit_amount: Optional[float] = Field(default=None, description="Profit amount when a take profit will be triggered"),
) -> Dict[str, Any]:
    """Update an existing trading position with comprehensive stop/profit options.

    This tool updates an existing position with new stop loss and/or take profit settings,
    including support for guaranteed stops, trailing stops, and various trigger methods.
    
    IMPORTANT: Use the dealId from get_positions, not the dealReference from create_position.
    The dealId is found in the position.position.dealId field when calling get_positions.

    Parameter rules:
    - guaranteed_stop and trailing_stop are mutually exclusive
    - trailing_stop requires stop_distance to be set
    - guaranteed_stop requires at least one of: stop_level, stop_distance, or stop_amount
    - At least one parameter must be provided

    Args:
        ctx: MCP context
        deal_id: The deal ID of the position to update (from get_positions, not dealReference from create_position)
        guaranteed_stop: Must be true if a guaranteed stop is required (cannot be used with trailing_stop or hedging mode)
        trailing_stop: Must be true if a trailing stop is required (requires stop_distance, cannot be used with guaranteed_stop)
        stop_level: Price level when a stop loss will be triggered
        stop_distance: Distance between current and stop loss triggering price (required if trailing_stop is true)
        stop_amount: Loss amount when a stop loss will be triggered
        profit_level: Price level when a take profit will be triggered
        profit_distance: Distance between current and take profit triggering price
        profit_amount: Profit amount when a take profit will be triggered

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
    
    # Check if at least one parameter is provided
    all_params = [guaranteed_stop, trailing_stop, stop_level, stop_distance, stop_amount, 
                 profit_level, profit_distance, profit_amount]
    if all(param is None for param in all_params):
        validation_error = "At least one parameter must be provided"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    # Validate parameter combinations
    if guaranteed_stop and trailing_stop:
        validation_error = "Cannot set both guaranteed_stop and trailing_stop - they are mutually exclusive"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    if trailing_stop and not stop_distance:
        validation_error = "stop_distance is required when trailing_stop is true"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    if guaranteed_stop and not (stop_level or stop_distance or stop_amount):
        validation_error = "When guaranteed_stop is true, must set stop_level, stop_distance, or stop_amount"
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
        result = client.update_position(
            deal_id=deal_id,
            guaranteed_stop=guaranteed_stop,
            trailing_stop=trailing_stop,
            stop_level=stop_level,
            stop_distance=stop_distance,
            stop_amount=stop_amount,
            profit_level=profit_level,
            profit_distance=profit_distance,
            profit_amount=profit_amount
        )
        
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

# Session Management Tools
@mcp.tool()
async def get_session_info(ctx: Context) -> Dict[str, Any]:
    """Get current session information including active financial account.
    
    This tool retrieves information about the current session including the active financial account.
    
    Returns:
        Dict[str, Any]: Session information
    """
    global authenticated, client
    
    logger.info("Invoking get_session_info tool")
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_session_info()
        return result
    
    except Exception as e:
        error_msg = f"Error getting session info: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def change_financial_account(
    ctx: Context,
    account_id: str = Field(description="The financial account ID to switch to")
) -> Dict[str, Any]:
    """Switch to a different financial account.
    
    This tool allows switching between different financial accounts associated with your Capital.com account.
    
    Args:
        ctx: MCP context
        account_id: The financial account ID to switch to
        
    Returns:
        Dict[str, Any]: Result of account change operation
    """
    global authenticated, client
    
    logger.info(f"Invoking change_financial_account tool for account: {account_id}")
    
    if not account_id or len(account_id.strip()) == 0:
        validation_error = "Account ID cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.change_financial_account(account_id)
        return result
    
    except Exception as e:
        error_msg = f"Error changing financial account: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

# Account Management Tools
@mcp.tool()
async def get_accounts(ctx: Context) -> Dict[str, Any]:
    """Get list of all financial accounts.
    
    This tool retrieves all financial accounts associated with your Capital.com account.
    
    Returns:
        Dict[str, Any]: List of financial accounts
    """
    global authenticated, client
    
    logger.info("Invoking get_accounts tool")
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_accounts()
        return result
    
    except Exception as e:
        error_msg = f"Error getting accounts: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def get_account_preferences(ctx: Context) -> Dict[str, Any]:
    """Get account preferences including leverage settings and hedging mode.
    
    This tool retrieves account preferences such as leverage settings for different instruments and hedging mode.
    
    Returns:
        Dict[str, Any]: Account preferences
    """
    global authenticated, client
    
    logger.info("Invoking get_account_preferences tool")
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_account_preferences()
        return result
    
    except Exception as e:
        error_msg = f"Error getting account preferences: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def update_account_preferences(
    ctx: Context,
    hedging_mode: Optional[bool] = Field(default=None, description="Enable/disable hedging mode (allows multiple positions in same instrument)"),
    currencies_leverage: Optional[int] = Field(default=None, description="Leverage for CURRENCIES (FOREX) instruments (e.g., 30 for 30:1)"),
    cryptocurrencies_leverage: Optional[int] = Field(default=None, description="Leverage for CRYPTOCURRENCIES instruments"),
    commodities_leverage: Optional[int] = Field(default=None, description="Leverage for COMMODITIES instruments"),
    shares_leverage: Optional[int] = Field(default=None, description="Leverage for SHARES/stocks instruments"),
    indices_leverage: Optional[int] = Field(default=None, description="Leverage for INDICES instruments"),
    preferences_json: Optional[str] = Field(default=None, description="Advanced: Raw JSON string for custom preferences (overrides individual parameters)")
) -> Dict[str, Any]:
    """Update account preferences including leverage settings and hedging mode.
    
    This tool updates account preferences such as leverage settings and hedging mode.
    You can either use individual parameters for common settings or provide raw JSON for advanced use.
    
    Args:
        ctx: MCP context
        hedging_mode: Enable/disable hedging mode
        currencies_leverage: Leverage for CURRENCIES (FOREX) (e.g., 30 for 30:1)
        cryptocurrencies_leverage: Leverage for CRYPTOCURRENCIES
        commodities_leverage: Leverage for COMMODITIES
        shares_leverage: Leverage for SHARES/stocks
        indices_leverage: Leverage for INDICES
        preferences_json: Raw JSON for custom preferences (advanced)
        
    Returns:
        Dict[str, Any]: Result of preferences update
    """
    global authenticated, client
    
    logger.info("Invoking update_account_preferences tool")
    
    try:
        # Build preferences dict from parameters
        preferences_dict = {}
        
        # Use raw JSON if provided (advanced option)
        if preferences_json:
            try:
                preferences_dict = json.loads(preferences_json)
                logger.info(f"Using raw JSON preferences: {preferences_dict}")
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON format in preferences_json: {str(e)}"
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        else:
            # Build from individual parameters
            if hedging_mode is not None:
                preferences_dict["hedgingMode"] = hedging_mode
            
            # Build leverages object if any leverage is specified (using correct API parameter names)
            leverages = {}
            if currencies_leverage is not None:
                leverages["CURRENCIES"] = currencies_leverage
            if cryptocurrencies_leverage is not None:
                leverages["CRYPTOCURRENCIES"] = cryptocurrencies_leverage
            if commodities_leverage is not None:
                leverages["COMMODITIES"] = commodities_leverage
            if shares_leverage is not None:
                leverages["SHARES"] = shares_leverage
            if indices_leverage is not None:
                leverages["INDICES"] = indices_leverage
            
            if leverages:
                preferences_dict["leverages"] = leverages
        
        if not preferences_dict:
            validation_error = "At least one preference parameter must be provided"
            logger.error(validation_error)
            await ctx.error(validation_error)
            return {"error": validation_error}
        
        logger.info(f"Updating preferences with: {preferences_dict}")
        
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.update_account_preferences(preferences_dict)
        return result
    
    except Exception as e:
        error_msg = f"Error updating account preferences: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def top_up_demo_account(
    ctx: Context,
    amount: float = Field(description="Amount to add to demo account balance")
) -> Dict[str, Any]:
    """Top up demo account balance.
    
    This tool adds funds to your demo trading account for testing purposes.
    
    Args:
        ctx: MCP context
        amount: Amount to add to demo account balance
        
    Returns:
        Dict[str, Any]: Result of top-up operation
    """
    global authenticated, client
    
    logger.info(f"Invoking top_up_demo_account tool with amount: {amount}")
    
    if amount <= 0:
        validation_error = "Amount must be greater than 0"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.top_up_demo_account(amount)
        return result
    
    except Exception as e:
        error_msg = f"Error topping up demo account: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

# Market Navigation Tools
@mcp.tool()
async def get_market_navigation(ctx: Context) -> Dict[str, Any]:
    """Get asset group names for market navigation.
    
    This tool retrieves the hierarchical structure of asset groups available for trading.
    
    Returns:
        Dict[str, Any]: Market navigation structure
    """
    global authenticated, client
    
    logger.info("Invoking get_market_navigation tool")
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_market_navigation()
        return result
    
    except Exception as e:
        error_msg = f"Error getting market navigation: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def get_market_navigation_node(
    ctx: Context,
    node_id: str = Field(description="The node ID to get assets for")
) -> Dict[str, Any]:
    """Get assets under a specific market navigation node.
    
    This tool retrieves all assets/instruments under a specific node in the market navigation hierarchy.
    
    Args:
        ctx: MCP context
        node_id: The node ID to get assets for
        
    Returns:
        Dict[str, Any]: Assets under the specified node
    """
    global authenticated, client
    
    logger.info(f"Invoking get_market_navigation_node tool for node: {node_id}")
    
    if not node_id or len(node_id.strip()) == 0:
        validation_error = "Node ID cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_market_navigation_node(node_id)
        return result
    
    except Exception as e:
        error_msg = f"Error getting market navigation node: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def get_watchlist_contents(
    ctx: Context,
    watchlist_id: str = Field(description="The watchlist ID to get contents for")
) -> Dict[str, Any]:
    """Get contents of a specific watchlist.
    
    This tool retrieves all instruments in a specific watchlist.
    
    Args:
        ctx: MCP context
        watchlist_id: The watchlist ID to get contents for
        
    Returns:
        Dict[str, Any]: Contents of the watchlist
    """
    global authenticated, client
    
    logger.info(f"Invoking get_watchlist_contents tool for watchlist: {watchlist_id}")
    
    if not watchlist_id or len(watchlist_id.strip()) == 0:
        validation_error = "Watchlist ID cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_watchlist_contents(watchlist_id)
        return result
    
    except Exception as e:
        error_msg = f"Error getting watchlist contents: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

# Working Orders Management Tools
@mcp.tool()
async def create_working_order(
    ctx: Context,
    epic: str = Field(description="The epic identifier for the instrument"),
    direction: str = Field(description="Trade direction (BUY or SELL)"),
    size: float = Field(description="Order size"),
    level: float = Field(description="Price level for the order"),
    order_type: str = Field(default="STOP", description="Order type (STOP or LIMIT)"),
    time_in_force: str = Field(default="GOOD_TILL_CANCELLED", description="Time in force (GOOD_TILL_CANCELLED, GOOD_TILL_DATE)"),
    stop_level: Optional[float] = Field(default=None, description="Stop loss level (optional)"),
    profit_level: Optional[float] = Field(default=None, description="Take profit level (optional)")
) -> Dict[str, Any]:
    """Create a working order (stop or limit order).
    
    This tool creates a working order that will be executed when the market reaches the specified level.
    
    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument
        direction: Trade direction (BUY or SELL)
        size: Order size
        level: Price level for the order
        order_type: Order type (STOP or LIMIT)
        time_in_force: Time in force
        stop_level: Stop loss level (optional)
        profit_level: Take profit level (optional)
        
    Returns:
        Dict[str, Any]: Working order creation result
    """
    global authenticated, client
    
    logger.info(f"Invoking create_working_order tool: {epic}, {direction}, {size}, {level}")
    
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
    
    if level <= 0:
        validation_error = "Level must be greater than 0"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    if order_type not in ["STOP", "LIMIT"]:
        validation_error = "Order type must be either 'STOP' or 'LIMIT'"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.create_working_order(epic, direction, size, level, order_type, time_in_force, stop_level, profit_level)
        return result
    
    except Exception as e:
        error_msg = f"Error creating working order: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def get_working_orders(ctx: Context) -> Dict[str, Any]:
    """Get all working orders (may have visibility issues with newly created orders).
    
    This tool retrieves all pending working orders (stop and limit orders). Based on testing:
    - Orders created with create_working_order may not appear immediately
    - Successfully created orders (with dealReference) sometimes don't show in this list
    - May be due to demo account behavior or API processing delays
    - Essential for finding correct working order IDs for update/delete operations
    
    Returns:
        Dict[str, Any]: List of working orders with metadata about potential visibility issues
    """
    global authenticated, client
    
    logger.info("Invoking get_working_orders tool")
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_working_orders()
        return result
    
    except Exception as e:
        error_msg = f"Error getting working orders: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def update_working_order(
    ctx: Context,
    working_order_id: str = Field(description="The working order ID to update (NOT the dealReference from creation - use get_working_orders to find the correct ID)"),
    level: Optional[float] = Field(default=None, description="New price level (optional)"),
    stop_level: Optional[float] = Field(default=None, description="New stop loss level (optional)"),
    profit_level: Optional[float] = Field(default=None, description="New take profit level (optional)")
) -> Dict[str, Any]:
    """Update a working order (REQUIRES actual working order ID, not dealReference).
    
    This tool updates the parameters of an existing working order. Based on testing:
    - Requires the actual working order ID from get_working_orders(), not the dealReference from creation
    - Currently experiencing 400 errors - may be due to demo account limitations or ID mismatch
    - At least one parameter must be provided for update
    
    IMPORTANT: Use get_working_orders() first to find the correct working order ID for orders
    created with create_working_order(). The dealReference is different from the working order ID.
    
    Args:
        ctx: MCP context
        working_order_id: The working order ID (from get_working_orders, not dealReference from creation)
        level: New price level (optional)
        stop_level: New stop loss level (optional)
        profit_level: New take profit level (optional)
        
    Returns:
        Dict[str, Any]: Working order update result
    """
    global authenticated, client
    
    logger.info(f"Invoking update_working_order tool for order: {working_order_id}")
    
    if not working_order_id or len(working_order_id.strip()) == 0:
        validation_error = "Working order ID cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    if level is None and stop_level is None and profit_level is None:
        validation_error = "At least one parameter (level, stop_level, or profit_level) must be provided"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.update_working_order(working_order_id, level, stop_level, profit_level)
        return result
    
    except Exception as e:
        error_msg = f"Error updating working order: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def delete_working_order(
    ctx: Context,
    working_order_id: str = Field(description="The working order ID to delete (NOT the dealReference from creation - use get_working_orders to find the correct ID)")
) -> Dict[str, Any]:
    """Delete a working order (REQUIRES actual working order ID, not dealReference).
    
    This tool cancels and removes a working order. Based on testing:
    - Requires the actual working order ID from get_working_orders(), not the dealReference from creation
    - Currently experiencing 400 errors - may be due to demo account limitations or ID mismatch
    - Orders may not be visible in get_working_orders() immediately after creation
    
    IMPORTANT: Use get_working_orders() first to find the correct working order ID for orders
    created with create_working_order(). The dealReference is different from the working order ID.
    
    Args:
        ctx: MCP context
        working_order_id: The working order ID (from get_working_orders, not dealReference from creation)
        
    Returns:
        Dict[str, Any]: Working order deletion result with error details if failed
    """
    global authenticated, client
    
    logger.info(f"Invoking delete_working_order tool for order: {working_order_id}")
    
    if not working_order_id or len(working_order_id.strip()) == 0:
        validation_error = "Working order ID cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.delete_working_order(working_order_id)
        return result
    
    except Exception as e:
        error_msg = f"Error deleting working order: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

# History Tools
@mcp.tool()
async def get_activity_history(
    ctx: Context,
    from_date: Optional[str] = Field(default=None, description="Start date in format YYYY-MM-DDTHH:MM:SS (e.g., '2024-01-01T00:00:00'). Max 24-hour range if to_date also provided."),
    to_date: Optional[str] = Field(default=None, description="End date in format YYYY-MM-DDTHH:MM:SS. Must be within 24 hours of from_date if both provided."),
    last_period: Optional[int] = Field(default=None, description="Time period in seconds to look back (e.g., 3600 for 1 hour, 86400 for 24 hours). Max 86400 seconds. Not applicable if date range specified."),
    detailed: bool = Field(default=False, description="Whether to include detailed information (adds market names, prices, stop/profit levels)"),
    deal_id: Optional[str] = Field(default=None, description="Filter by specific deal ID to show activities for a particular position"),
    filter_type: Optional[str] = Field(default=None, description="FIQL filter string (e.g., 'type==POSITION' for position activities only). Supports: epic, source, status, type.")
) -> Dict[str, Any]:
    """Get account activity history with flexible time filtering.
    
    This tool retrieves trading activity history. Based on real-world testing:
    - lastPeriod works reliably (max 86400 seconds = 24 hours)
    - Date ranges are documented but may have implementation issues in current API version
    - detailed=true adds comprehensive information including market names and price levels
    - deal_id filtering works for specific position activities
    - FIQL filtering supports various activity types
    
    Args:
        ctx: MCP context
        from_date: Start date (optional, for date range queries)
        to_date: End date (optional, max 24h from from_date)
        last_period: Seconds to look back (max 86400, ignored if date range provided)
        detailed: Include detailed activity information
        deal_id: Filter by specific position/deal ID
        filter_type: FIQL filter for activity types/status
        
    Returns:
        Dict[str, Any]: Account activity history with metadata
    """
    global authenticated, client
    
    logger.info("Invoking get_activity_history tool")
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_activity_history(from_date, to_date, last_period, detailed, deal_id, filter_type)
        return result
    
    except Exception as e:
        error_msg = f"Error getting activity history: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def get_transaction_history(
    ctx: Context,
    from_date: Optional[str] = Field(default=None, description="Start date in format YYYY-MM-DDTHH:MM:SS (e.g., '2024-01-01T00:00:00'). Timezone info will be stripped if provided."),
    to_date: Optional[str] = Field(default=None, description="End date in format YYYY-MM-DDTHH:MM:SS. Timezone info will be stripped if provided."),
    last_period: Optional[int] = Field(default=None, description="Time period in seconds to look back (e.g., 3600 for 1 hour, 86400 for 1 day, 604800 for 7 days). Not applicable if date range specified. API defaults to 600 seconds (10 minutes)."),
    transaction_type: Optional[str] = Field(default=None, description="Filter by transaction type. Options: DEPOSIT, WITHDRAWAL, TRADE, SWAP, TRADE_COMMISSION, INACTIVITY_FEE, BONUS, TRANSFER, CORPORATE_ACTION, CONVERSION, REBATE, etc.")
) -> Dict[str, Any]:
    """Get transaction history with date ranges, lastPeriod, or transaction type filtering.
    
    This tool retrieves the financial transaction history for your account. All parameters are optional
    as per API documentation. If no parameters provided, API returns last 10 minutes of transactions.
    
    IMPORTANT: lastPeriod is not applicable when date range (from/to) is specified.
    
    Args:
        ctx: MCP context
        from_date: Start date (optional, API supports date ranges)
        to_date: End date (optional, API supports date ranges)
        last_period: Time period in seconds (ignored if date range provided)
        transaction_type: Filter by transaction type (DEPOSIT, WITHDRAWAL, etc.)
        
    Returns:
        Dict[str, Any]: Transaction history with metadata
    """
    global authenticated, client
    
    logger.info("Invoking get_transaction_history tool")
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_transaction_history(from_date, to_date, last_period, transaction_type)
        return result
    
    except Exception as e:
        error_msg = f"Error getting transaction history: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

# Position Confirmation Tools
@mcp.tool()
async def confirm_deal(
    ctx: Context,
    deal_reference: str = Field(description="The deal reference from position creation to confirm")
) -> Dict[str, Any]:
    """Confirm the status of a position after creation using dealReference.
    
    This tool confirms whether a position was successfully created and provides the dealId for position management.
    Use this after create_position to verify the position was opened and get the dealId.
    
    Args:
        ctx: MCP context
        deal_reference: The deal reference returned from create_position
        
    Returns:
        Dict[str, Any]: Deal confirmation with status and affected deals (including dealId)
    """
    global authenticated, client
    
    logger.info(f"Invoking confirm_deal tool for reference: {deal_reference}")
    
    if not deal_reference or len(deal_reference.strip()) == 0:
        validation_error = "Deal reference cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.confirm_deal(deal_reference)
        return result
    
    except Exception as e:
        error_msg = f"Error confirming deal: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

# Utility Tools
@mcp.tool()
async def ping_api(ctx: Context) -> Dict[str, Any]:
    """Test connection to the Capital.com API.
    
    This tool tests the connection to the API server and returns the connection status.
    
    Returns:
        Dict[str, Any]: Connection status
    """
    global authenticated, client
    
    logger.info("Invoking ping_api tool")
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.ping()
        return result
    
    except Exception as e:
        error_msg = f"Error pinging API: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

@mcp.tool()
async def get_server_time(ctx: Context) -> Dict[str, Any]:
    """Get server time from Capital.com API.
    
    This tool retrieves the current server time from the Capital.com API.
    
    Returns:
        Dict[str, Any]: Server time information
    """
    global authenticated, client
    
    logger.info("Invoking get_server_time tool")
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_server_time()
        return result
    
    except Exception as e:
        error_msg = f"Error getting server time: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}

# Market Information Tools
@mcp.tool()
async def get_client_sentiment(
    ctx: Context,
    market_ids: str = Field(description="Market identifier(s) - single market like 'SILVER' or comma-separated list like 'SILVER,NATURALGAS,BTCUSD'")
) -> Dict[str, Any]:
    """Get client sentiment for markets showing long vs short position percentages.
    
    This tool retrieves client sentiment data from Capital.com showing what percentage
    of clients are holding long vs short positions for specified markets. This data
    can be useful for contrarian trading strategies and market sentiment analysis.
    
    Args:
        ctx: MCP context
        market_ids: Market identifier(s) - single market or comma-separated list
        
    Returns:
        Dict[str, Any]: Client sentiment data with long/short percentages and interpretations
    """
    global authenticated, client
    
    logger.info("Invoking get_client_sentiment tool")
    
    if not market_ids or len(market_ids.strip()) == 0:
        validation_error = "market_ids cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    try:
        if not authenticated:
            logger.info("Not authenticated, attempting initial authentication")
            auth_result = client.authenticate()
            authenticated = auth_result
            if not authenticated:
                error_msg = "Authentication failed. Please check your Capital.com API credentials."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        result = client.get_client_sentiment(market_ids)
        return result
    
    except Exception as e:
        error_msg = f"Error getting client sentiment: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return {"error": str(e)}


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
