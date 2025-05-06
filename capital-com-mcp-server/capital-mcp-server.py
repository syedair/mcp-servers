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
from capital_client import CapitalClient

# Import FastMCP
from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

# Configure logging with a more secure approach
log_dir = os.path.join(os.path.expanduser("~"), ".capital-mcp", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "capital_mcp_server.log")

logging.basicConfig(
    level=logging.DEBUG if os.getenv('CAPITAL_MCP_DEBUG') else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='a'
)
logger = logging.getLogger("capital-mcp")

# Initialize the Capital.com client
client = CapitalClient()
authenticated = False

# Create the FastMCP server
mcp = FastMCP(
    'capital-com-mcp-server',
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
    """,
    dependencies=[
        'requests',
    ],
)

# Helper function to sanitize error messages
def sanitize_error(error_msg: str) -> str:
    """
    Sanitize error messages to avoid leaking sensitive information
    
    Args:
        error_msg: The original error message
        
    Returns:
        str: Sanitized error message
    """
    # List of patterns to sanitize
    patterns = [
        (r'password[\'"=:]\s*[^\s,;]+', 'password=*****'),
        (r'api[_-]?key[\'"=:]\s*[^\s,;]+', 'api_key=*****'),
        (r'token[\'"=:]\s*[^\s,;]+', 'token=*****'),
        (r'identifier[\'"=:]\s*[^\s,;]+', 'identifier=*****'),
        (r'email[\'"=:]\s*[^\s,;@]+@[^\s,;]+', 'email=*****'),
        (r'host[\'"=:]\s*[^\s,;]+', 'host=*****'),
        (r'path[\'"=:]\s*[^\s,;]+', 'path=*****'),
    ]
    
    result = error_msg
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result

# Helper function to validate input parameters
def validate_input(**kwargs) -> Optional[str]:
    """
    Validate input parameters
    
    Args:
        **kwargs: Parameters to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None otherwise
    """
    for key, value in kwargs.items():
        # Check for None values where required
        if value is None and key not in ['stop_level', 'profit_level', 'from_date', 'to_date', 'leverage']:
            return f"Parameter '{key}' is required"
        
        # Validate string parameters
        if key in ['epic', 'direction', 'deal_id', 'resolution'] and isinstance(value, str):
            # Check for potential injection patterns
            if re.search(r'[<>{}()\[\];]', value):
                return f"Invalid characters in parameter '{key}'"
            
            # Specific validation for direction
            if key == 'direction' and value not in ['BUY', 'SELL']:
                return f"Direction must be 'BUY' or 'SELL', got '{value}'"
            
            # Specific validation for resolution
            if key == 'resolution' and value not in [
                'MINUTE', 'MINUTE_5', 'MINUTE_15', 'MINUTE_30', 
                'HOUR', 'HOUR_4', 'DAY', 'WEEK', 'MONTH'
            ]:
                return f"Invalid resolution: '{value}'"
        
        # Validate numeric parameters
        if key in ['size', 'leverage', 'stop_level', 'profit_level', 'max_bars'] and value is not None:
            try:
                num_value = float(value)
                
                # Size validation
                if key == 'size':
                    if num_value < 0.01:
                        return f"Position size too small, minimum is 0.01"
                    if num_value > 10.0:
                        return f"Position size too large, maximum is 10.0"
                
                # Leverage validation
                if key == 'leverage' and (num_value <= 0 or num_value > 100):
                    return f"Leverage must be between 1 and 100, got {num_value}"
                
                # Max bars validation
                if key == 'max_bars' and (num_value <= 0 or num_value > 1000):
                    return f"Max bars must be between 1 and 1000, got {num_value}"
                    
            except ValueError:
                return f"Parameter '{key}' must be a number"
    
    return None


@mcp.tool()
async def authenticate(ctx: Context) -> Dict[str, bool]:
    """Authenticate with Capital.com API.

    This tool authenticates with the Capital.com API using credentials from the .env file.
    Authentication is required before using other tools.

    Returns:
        Dict[str, bool]: Authentication result with success status
    """
    global authenticated, client
    
    logger.info("Invoking authenticate tool")
    
    try:
        result = client.authenticate()
        authenticated = result
        
        if authenticated:
            logger.info("Successfully authenticated with Capital.com API")
            return {"success": True}
        else:
            logger.warning("Failed to authenticate with Capital.com API")
            await ctx.error("Authentication failed. Please check your credentials.")
            return {"success": False}
    
    except Exception as e:
        error_msg = f"Error during authentication: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error("Authentication failed. Please check your credentials and try again.")
        return {"success": False, "error": "Authentication failed"}


@mcp.tool()
async def get_account_info(ctx: Context) -> Dict[str, Any]:
    """Get account information from Capital.com.

    This tool retrieves account information including balance, open positions, and account details.

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
            await ctx.error(f"Failed to retrieve account information: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error getting account info: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error("Failed to retrieve account information. Please try again.")
        return {"error": "Failed to retrieve account information"}


@mcp.tool()
async def search_markets(
    ctx: Context,
    search_term: str = Field(description="Term to search for (e.g., EURUSD, AAPL)"),
) -> Dict[str, Any]:
    """Search for markets on Capital.com.

    This tool searches for available markets on Capital.com matching the search term.

    Args:
        ctx: MCP context
        search_term: Term to search for (e.g., EURUSD, AAPL)

    Returns:
        Dict[str, Any]: Markets matching the search term
    """
    global authenticated, client
    
    logger.info(f"Invoking search_markets tool with term: {search_term}")
    
    # Validate input
    validation_error = validate_input(search_term=search_term)
    if validation_error:
        logger.error(f"Input validation error: {validation_error}")
        await ctx.error(f"Invalid input: {validation_error}")
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
        result = client.get_markets(search_term)
        
        if "error" in result:
            await ctx.error(f"Failed to search markets: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error searching markets: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error("Failed to search markets. Please try again.")
        return {"error": "Failed to search markets"}


@mcp.tool()
async def get_prices(
    ctx: Context,
    epic: str = Field(description="The epic identifier for the instrument (e.g., CS.D.EURUSD.CFD.IP)"),
) -> Dict[str, Any]:
    """Get prices for a specific instrument.

    This tool retrieves current price information for a specific instrument.

    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument (e.g., CS.D.EURUSD.CFD.IP)

    Returns:
        Dict[str, Any]: Price information for the instrument
    """
    global authenticated, client
    
    logger.info(f"Invoking get_prices tool for epic: {epic}")
    
    # Validate input
    validation_error = validate_input(epic=epic)
    if validation_error:
        logger.error(f"Input validation error: {validation_error}")
        await ctx.error(f"Invalid input: {validation_error}")
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
        result = client.get_prices(epic)
        
        if "error" in result:
            await ctx.error(f"Failed to get prices: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error getting prices: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(f"Failed to get prices for {epic}. Please try again.")
        return {"error": f"Failed to get prices for {epic}"}


@mcp.tool()
async def get_positions(ctx: Context) -> Dict[str, Any]:
    """Get all open positions.

    This tool retrieves all open positions in the account.

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
    direction: str = Field(description="Trade direction (BUY or SELL)", enum=["BUY", "SELL"]),
    size: float = Field(description="Trade size"),
    leverage: float = Field(default=20.0, description="Leverage ratio (e.g., 20 for 20:1)"),
    stop_level: Optional[float] = Field(None, description="Stop loss level (optional)"),
    profit_level: Optional[float] = Field(None, description="Take profit level (optional)"),
) -> Dict[str, Any]:
    """Create a new trading position with specified leverage.

    This tool creates a new trading position with the specified parameters including leverage.
    It calculates and displays the margin required for the position.

    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument
        direction: Trade direction (BUY or SELL)
        size: Trade size
        leverage: Leverage ratio (e.g., 20 for 20:1)
        stop_level: Stop loss level (optional)
        profit_level: Take profit level (optional)

    Returns:
        Dict[str, Any]: Position creation result including margin information
    """
    global authenticated, client
    
    logger.info(f"Invoking create_position tool: {epic}, {direction}, {size}, leverage: {leverage}")
    
    # Validate input
    validation_error = validate_input(
        epic=epic,
        direction=direction,
        size=size,
        leverage=leverage,
        stop_level=stop_level,
        profit_level=profit_level
    )
    if validation_error:
        logger.error(f"Input validation error: {validation_error}")
        await ctx.error(f"Invalid input: {validation_error}")
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
        # Calculate margin using the client method
        margin_info = client.calculate_margin(epic, direction, size, leverage)
        
        if "error" in margin_info:
            error_msg = margin_info["error"]
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
        
        # Log margin information
        logger.info(f"Calculated margin: {margin_info['margin_required']:.2f} at leverage {leverage}:1")
        
        # Create the position with specified parameters
        result = client.create_position(
            epic=epic,
            direction=direction,
            size=size,
            stop_level=stop_level,
            profit_level=profit_level,
            leverage=leverage
        )
        
        if "error" in result:
            await ctx.error(f"Failed to create position: {result['error']}")
            return result
        
        # Add margin information to the result
        result["margin_information"] = margin_info
        
        return result
    
    except Exception as e:
        error_msg = f"Error creating position: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error("Failed to create position. Please try again.")
        return {"error": "Failed to create position"}


@mcp.tool()
async def close_position(
    ctx: Context,
    deal_id: str = Field(description="The deal ID to close"),
) -> Dict[str, Any]:
    """Close an open position.

    This tool closes an open position with the specified deal ID.

    Args:
        ctx: MCP context
        deal_id: The deal ID to close

    Returns:
        Dict[str, Any]: Position closure result
    """
    global authenticated, client
    
    logger.info(f"Invoking close_position tool for deal_id: {deal_id}")
    
    # Validate input
    validation_error = validate_input(deal_id=deal_id)
    if validation_error:
        logger.error(f"Input validation error: {validation_error}")
        await ctx.error(f"Invalid input: {validation_error}")
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
    
    # Validate input
    validation_error = validate_input(
        deal_id=deal_id,
        stop_level=stop_level,
        profit_level=profit_level
    )
    if validation_error:
        logger.error(f"Input validation error: {validation_error}")
        await ctx.error(f"Invalid input: {validation_error}")
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
    
    # Validate inputs
    if stop_level is None and profit_level is None:
        error_msg = "At least one of stop_level or profit_level must be provided"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"error": error_msg}
    
    try:
        # Use the client to update the position
        result = client.update_position(deal_id, stop_level, profit_level)
        
        if "error" in result:
            await ctx.error(f"Failed to update position: {result['error']}")
            return result
            
        logger.info(f"Successfully updated position {deal_id}")
        return result
    
    except Exception as e:
        error_msg = f"Error updating position: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(f"Failed to update position with deal ID: {deal_id}. Please try again.")
        return {"error": f"Failed to update position with deal ID: {deal_id}"}


@mcp.tool()
async def get_historical_prices(
    ctx: Context,
    epic: str = Field(description="The epic identifier for the instrument (e.g., CS.D.EURUSD.CFD.IP)"),
    resolution: str = Field(description="Time resolution (e.g., MINUTE, MINUTE_5, MINUTE_15, HOUR, DAY, WEEK)"),
    max_bars: int = Field(default=10, description="Maximum number of bars to return"),
    from_date: Optional[str] = Field(None, description="Start date in ISO format (e.g., '2022-02-24T00:00:00')"),
    to_date: Optional[str] = Field(None, description="End date in ISO format"),
) -> Dict[str, Any]:
    """Get historical price data for a specific instrument.

    This tool retrieves historical price data for a specific instrument with custom granularity.

    Args:
        ctx: MCP context
        epic: The epic identifier for the instrument (e.g., CS.D.EURUSD.CFD.IP)
        resolution: Time resolution (e.g., MINUTE, MINUTE_5, MINUTE_15, HOUR, DAY, WEEK)
        max_bars: Maximum number of bars to return (default: 10)
        from_date: Start date in ISO format (e.g., "2022-02-24T00:00:00")
        to_date: End date in ISO format (optional)

    Returns:
        Dict[str, Any]: Historical price information for the instrument
    """
    global authenticated, client
    
    logger.info(f"Invoking get_historical_prices tool for epic: {epic}, resolution: {resolution}")
    
    # Validate input
    validation_error = validate_input(
        epic=epic,
        resolution=resolution,
        max_bars=max_bars,
        from_date=from_date,
        to_date=to_date
    )
    if validation_error:
        logger.error(f"Input validation error: {validation_error}")
        await ctx.error(f"Invalid input: {validation_error}")
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
        result = client.get_historical_prices(epic, resolution, max_bars, from_date, to_date)
        
        if "error" in result:
            await ctx.error(f"Failed to get historical prices: {result['error']}")
            return result
            
        return result
    
    except Exception as e:
        error_msg = f"Error getting historical prices: {type(e).__name__}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(f"Failed to get historical prices for {epic}. Please try again.")
        return {"error": f"Failed to get historical prices for {epic}"}


@mcp.tool()
async def get_watchlists(ctx: Context) -> Dict[str, Any]:
    """Get all watchlists.

    This tool retrieves all watchlists in the account.

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