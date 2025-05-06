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
from typing import Dict, Any, List, Optional, Union
import pathlib

# Import the Capital.com client
from .capital_client import CapitalClient

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

    - Authenticate before using other tools
    - Use search_markets to find available markets
    - Check account information before creating positions
    - Always specify stop loss and take profit levels when creating positions
    - Monitor open positions regularly

    ## Tool Selection Guide

    - Use `authenticate` when: You need to authenticate with Capital.com API
    - Use `get_account_info` when: You need to check account balance or details
    - Use `search_markets` when: You need to find available markets to trade
    - Use `get_prices` when: You need current price information for a specific instrument
    - Use `get_historical_prices` when: You need historical price data with custom time resolution
    - Use `get_positions` when: You need to check open positions
    - Use `create_position` when: You want to open a new trading position
    - Use `close_position` when: You want to close an existing position
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

@mcp.tool()
async def authenticate(ctx: Context) -> Dict[str, Any]:
    """Authenticate with Capital.com API.
    
    This tool authenticates with the Capital.com API using the credentials
    provided in environment variables.
    
    Returns:
        Dict[str, Any]: Authentication result
    """
    global authenticated, client
    
    logger.info("Invoking authenticate tool")
    
    try:
        result = client.authenticate()
        authenticated = result
        
        if authenticated:
            await ctx.info("Successfully authenticated with Capital.com API")
            return {"success": True, "message": "Authentication successful"}
        else:
            error_msg = "Authentication failed. Please check your credentials."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
    
    except Exception as e:
        error_msg = f"Error during authentication: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error("Authentication failed. Please check your credentials and try again.")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_account_info(ctx: Context) -> Dict[str, Any]:
    """Get account information from Capital.com.
    
    This tool retrieves account information including balance, margin, profit/loss,
    and other account details.
    
    Returns:
        Dict[str, Any]: Account information
    """
    global authenticated, client
    
    logger.info("Invoking get_account_info tool")
    
    # Check if authenticated
    if not authenticated:
        logger.info("Not authenticated yet, attempting authentication")
        auth_result = client.authenticate()
        authenticated = auth_result
        if not authenticated:
            error_msg = "Authentication required before using this tool"
            logger.error(error_msg)
            await ctx.error("Authentication required. Please authenticate first.")
            return {"error": "Authentication required"}
    
    try:
        result = client.get_account_info()
        
        if "error" in result:
            await ctx.error(f"Failed to get account info: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error getting account info: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error("Failed to get account information. Please try again.")
        return {"error": "Failed to get account information"}

@mcp.tool()
async def search_markets(
    ctx: Context,
    query: str = Field(description="Search query (e.g., 'EURUSD', 'Apple', 'Gold')"),
    limit: int = Field(10, description="Maximum number of results to return")
) -> Dict[str, Any]:
    """Search for markets on Capital.com.
    
    This tool searches for markets (instruments) on Capital.com based on a query string.
    
    Args:
        ctx: MCP context
        query: Search query (e.g., 'EURUSD', 'Apple', 'Gold')
        limit: Maximum number of results to return
        
    Returns:
        Dict[str, Any]: Search results
    """
    global authenticated, client
    
    logger.info(f"Invoking search_markets tool with query: {query}")
    
    # Validate inputs
    if not query or len(query.strip()) == 0:
        validation_error = "Search query cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    if limit < 1 or limit > 100:
        validation_error = "Limit must be between 1 and 100"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    # Check if authenticated
    if not authenticated:
        logger.info("Not authenticated yet, attempting authentication")
        auth_result = client.authenticate()
        authenticated = auth_result
        if not authenticated:
            error_msg = "Authentication required before using this tool"
            logger.error(error_msg)
            await ctx.error("Authentication required. Please authenticate first.")
            return {"error": "Authentication required"}
    
    try:
        result = client.search_markets(query, limit)
        
        if "error" in result:
            await ctx.error(f"Failed to search markets: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error searching markets: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(f"Failed to search for '{query}'. Please try again.")
        return {"error": f"Failed to search for '{query}'"}

@mcp.tool()
async def get_prices(
    ctx: Context,
    epic: str = Field(description="The epic identifier for the instrument"),
    resolution: str = Field("MINUTE", description="Time resolution (MINUTE, HOUR_4, DAY, WEEK)"),
    limit: int = Field(10, description="Number of price points to retrieve")
) -> Dict[str, Any]:
    """Get historical prices for an instrument.
    
    This tool retrieves historical price data for a specific instrument.
    
    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument
        resolution: Time resolution (MINUTE, HOUR_4, DAY, WEEK)
        limit: Number of price points to retrieve
        
    Returns:
        Dict[str, Any]: Price data
    """
    global authenticated, client
    
    logger.info(f"Invoking get_prices tool for epic: {epic}")
    
    # Validate inputs
    if not epic or len(epic.strip()) == 0:
        validation_error = "Epic identifier cannot be empty"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    valid_resolutions = ["MINUTE", "MINUTE_5", "MINUTE_15", "MINUTE_30", "HOUR", "HOUR_4", "DAY", "WEEK"]
    if resolution not in valid_resolutions:
        validation_error = f"Invalid resolution. Must be one of: {', '.join(valid_resolutions)}"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    if limit < 1 or limit > 1000:
        validation_error = "Limit must be between 1 and 1000"
        logger.error(validation_error)
        await ctx.error(validation_error)
        return {"error": validation_error}
    
    # Check if authenticated
    if not authenticated:
        logger.info("Not authenticated yet, attempting authentication")
        auth_result = client.authenticate()
        authenticated = auth_result
        if not authenticated:
            error_msg = "Authentication required before using this tool"
            logger.error(error_msg)
            await ctx.error("Authentication required. Please authenticate first.")
            return {"error": "Authentication required"}
    
    try:
        result = client.get_prices(epic, resolution, limit)
        
        if "error" in result:
            await ctx.error(f"Failed to get prices: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error getting prices: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(f"Failed to get prices for '{epic}'. Please try again.")
        return {"error": f"Failed to get prices for '{epic}'"}

@mcp.tool()
async def get_positions(ctx: Context) -> Dict[str, Any]:
    """Get all open positions.
    
    This tool retrieves all currently open trading positions.
    
    Returns:
        Dict[str, Any]: Open positions
    """
    global authenticated, client
    
    logger.info("Invoking get_positions tool")
    
    # Check if authenticated
    if not authenticated:
        logger.info("Not authenticated yet, attempting authentication")
        auth_result = client.authenticate()
        authenticated = auth_result
        if not authenticated:
            error_msg = "Authentication required before using this tool"
            logger.error(error_msg)
            await ctx.error("Authentication required. Please authenticate first.")
            return {"error": "Authentication required"}
    
    try:
        result = client.get_positions()
        
        if "error" in result:
            await ctx.error(f"Failed to get positions: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error getting positions: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error("Failed to get positions. Please try again.")
        return {"error": "Failed to get positions"}

@mcp.tool()
async def create_position(
    ctx: Context,
    epic: str = Field(description="The epic identifier for the instrument"),
    direction: str = Field(description="Trade direction (BUY or SELL)"),
    size: float = Field(description="Position size"),
    stop_level: Optional[float] = Field(None, description="Stop loss level (optional)"),
    profit_level: Optional[float] = Field(None, description="Take profit level (optional)"),
) -> Dict[str, Any]:
    """Create a new trading position.
    
    This tool creates a new trading position for the specified instrument.
    
    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument
        direction: Trade direction (BUY or SELL)
        size: Position size
        stop_level: Stop loss level (optional)
        profit_level: Take profit level (optional)
        
    Returns:
        Dict[str, Any]: Position creation result
    """
    global authenticated, client
    
    logger.info(f"Invoking create_position tool for epic: {epic}")
    
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
            error_msg = "Authentication required before using this tool"
            logger.error(error_msg)
            await ctx.error("Authentication required. Please authenticate first.")
            return {"error": "Authentication required"}
    
    try:
        result = client.create_position(epic, direction, size, stop_level, profit_level)
        
        if "error" in result:
            await ctx.error(f"Failed to create position: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error creating position: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(f"Failed to create position for '{epic}'. Please try again.")
        return {"error": f"Failed to create position for '{epic}'"}

@mcp.tool()
async def close_position(
    ctx: Context,
    deal_id: str = Field(description="The deal ID of the position to close"),
) -> Dict[str, Any]:
    """Close an open trading position.
    
    This tool closes an open trading position by its deal ID.
    
    Args:
        ctx: MCP context
        deal_id: The deal ID of the position to close
        
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
            error_msg = "Authentication required before using this tool"
            logger.error(error_msg)
            await ctx.error("Authentication required. Please authenticate first.")
            return {"error": "Authentication required"}
    
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
    stop_level: Optional[float] = Field(None, description="New stop loss level (optional)"),
    profit_level: Optional[float] = Field(None, description="New take profit level (optional)"),
) -> Dict[str, Any]:
    """Update an existing trading position.

    This tool updates an existing position with new stop loss and/or take profit levels.

    Args:
        ctx: MCP context
        deal_id: The deal ID of the position to update
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
            error_msg = "Authentication required before using this tool"
            logger.error(error_msg)
            await ctx.error("Authentication required. Please authenticate first.")
            return {"error": "Authentication required"}
    
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
            error_msg = "Authentication required before using this tool"
            logger.error(error_msg)
            await ctx.error("Authentication required. Please authenticate first.")
            return {"error": "Authentication required"}
    
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
