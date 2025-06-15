import os
import re
import requests
import json
import logging
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Dict, List, Optional, Union, Any

# Configure logging
logger = logging.getLogger("capital-client")

class CapitalClient:
    """
    Client for interacting with Capital.com's API
    """
    
    def __init__(self, base_url=None, api_key=None, identifier=None, password=None):
        """Initialize the Capital.com client with credentials from .env file"""
        load_dotenv()
        
        # Get credentials from parameters or environment variables
        self.base_url = base_url or os.getenv("CAPITAL_BASE_URL")
        self.api_key = api_key or os.getenv("CAPITAL_API_KEY")
        self.identifier = identifier or os.getenv("CAPITAL_IDENTIFIER")
        self.password = password or os.getenv("CAPITAL_PASSWORD")
        
        # Initialize session data
        self.cst = None
        self.x_security_token = None
        self.account_id = None
        self.session = requests.Session()
        
        # Session tokens from environment (optional)
        self.session_token = os.getenv("CAPITAL_SESSION_TOKEN", "")
        self.security_token = os.getenv("CAPITAL_SECURITY_TOKEN", "")
        
        self.headers = {
            "X-CAP-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Configure logging
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        if os.environ.get("CAPITAL_MCP_DEBUG", "0") == "1":
            logger.setLevel(logging.DEBUG)
    
    def authenticate(self) -> bool:
        """
        Authenticate with Capital.com API
        
        Returns:
            bool: True if authentication was successful, False otherwise
        """
        if not self.base_url or not self.api_key or not self.identifier or not self.password:
            logger.error("Missing authentication credentials")
            return False
            
        try:
            url = f"{self.base_url}/api/v1/session"
            headers = {
                "X-CAP-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "identifier": self.identifier,
                "password": self.password
            }
            
            logger.debug(f"Authenticating with Capital.com API at {url}")
            response = self.session.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                # Store session tokens
                self.cst = response.headers.get("CST")
                self.x_security_token = response.headers.get("X-SECURITY-TOKEN")
                
                # Update headers with authentication tokens
                self.headers["CST"] = self.cst
                self.headers["X-SECURITY-TOKEN"] = self.x_security_token
                
                # Save tokens to environment variables (optional)
                data = response.json()
                os.environ["CAPITAL_SESSION_TOKEN"] = data.get("session_token", "")
                os.environ["CAPITAL_SECURITY_TOKEN"] = self.x_security_token
                os.environ["CAPITAL_CST"] = self.cst
                
                # Get account ID
                accounts_response = self.session.get(
                    f"{self.base_url}/api/v1/accounts",
                    headers=self._get_auth_headers()
                )
                
                if accounts_response.status_code == 200:
                    accounts_data = accounts_response.json()
                    if "accounts" in accounts_data and len(accounts_data["accounts"]) > 0:
                        self.account_id = accounts_data["accounts"][0]["accountId"]
                        logger.info(f"Successfully authenticated with account ID: {self.account_id}")
                        return True
                    else:
                        logger.error("No accounts found")
                        return False
                else:
                    logger.error(f"Failed to get accounts: {accounts_response.status_code} - {accounts_response.text}")
                    return False
            else:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error during authentication: {type(e).__name__}", exc_info=True)
            return False
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests
        
        Returns:
            Dict[str, str]: Headers dictionary
        """
        headers = {
            "X-CAP-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        if self.cst:
            headers["CST"] = self.cst
            
        if self.x_security_token:
            headers["X-SECURITY-TOKEN"] = self.x_security_token
            
        return headers
    
    def _make_authenticated_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make an authenticated request with automatic re-authentication on token expiry
        
        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters
            
        Returns:
            requests.Response: HTTP response
        """
        if not self.account_id:
            raise Exception("Not authenticated")
        
        # Make the initial request
        headers = self._get_auth_headers()
        response = self.session.request(method, url, headers=headers, **kwargs)
        
        # If 401 error, tokens have expired - re-authenticate and retry
        if response.status_code == 401:
            logger.warning("Session tokens expired, attempting re-authentication")
            
            # Re-authenticate
            auth_result = self.authenticate()
            
            if auth_result:
                logger.info("Re-authentication successful, retrying request")
                # Retry the request with new tokens
                headers = self._get_auth_headers()
                response = self.session.request(method, url, headers=headers, **kwargs)
            else:
                logger.error("Re-authentication failed")
                raise Exception("Re-authentication failed. Please check your Capital.com API credentials.")
        
        return response
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information
        
        Returns:
            Dict[str, Any]: Account information
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
            
        try:
            url = f"{self.base_url}/api/v1/accounts"
            
            logger.debug(f"Getting account info from {url}")
            response = self._make_authenticated_request("GET", url)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get account info: {response.status_code} - {response.text}")
                return {"error": f"Failed to get account info: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error getting account info: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting account info: {str(e)}"}
    
    def search_markets(self, search_term: str = None, epics: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        Search for markets
        
        Args:
            search_term: Search term to find markets (optional)
            epics: Comma-separated epic identifiers, max 50 (optional)
            limit: Maximum number of results to return
            
        Returns:
            Dict[str, Any]: Search results
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
            
        try:
            url = f"{self.base_url}/api/v1/markets"
            params = {}
            
            # If both search_term and epics are provided, search_term takes priority
            if search_term is not None:
                params["searchTerm"] = search_term
            elif epics is not None:
                params["epics"] = epics
            
            logger.debug(f"Searching markets with params {params} from {url}")
            response = self._make_authenticated_request("GET", url, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to search markets: {response.status_code} - {response.text}")
                return {"error": f"Failed to search markets: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error searching markets: {type(e).__name__}", exc_info=True)
            return {"error": f"Error searching markets: {str(e)}"}
    
    def get_prices(self, epic: str, resolution: str = "MINUTE", limit: int = 10) -> Dict[str, Any]:
        """
        Get historical prices for an instrument
        
        Args:
            epic: The epic identifier for the instrument
            resolution: Time resolution (MINUTE, HOUR_4, DAY, WEEK)
            limit: Number of price points to retrieve
            
        Returns:
            Dict[str, Any]: Price data
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
            
        try:
            url = f"{self.base_url}/api/v1/prices/{epic}?resolution={resolution}&limit={limit}"
            
            logger.debug(f"Getting prices for '{epic}' from {url}")
            response = self._make_authenticated_request("GET", url)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get prices: {response.status_code} - {response.text}")
                return {"error": f"Failed to get prices: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error getting prices: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting prices: {str(e)}"}
    
    def get_positions(self) -> Dict[str, Any]:
        """
        Get all open positions
        
        Returns:
            Dict[str, Any]: Open positions
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
            
        try:
            url = f"{self.base_url}/api/v1/positions"
            
            logger.debug(f"Getting positions from {url}")
            response = self._make_authenticated_request("GET", url)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get positions: {response.status_code} - {response.text}")
                return {"error": f"Failed to get positions: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error getting positions: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting positions: {str(e)}"}
    
    def create_position(
        self, 
        epic: str, 
        direction: str, 
        size: float, 
        guaranteed_stop: Optional[bool] = None,
        trailing_stop: Optional[bool] = None,
        stop_level: Optional[float] = None, 
        stop_distance: Optional[float] = None,
        stop_amount: Optional[float] = None,
        profit_level: Optional[float] = None,
        profit_distance: Optional[float] = None,
        profit_amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a new trading position with comprehensive stop/profit options
        
        Args:
            epic: The epic identifier for the instrument
            direction: Trade direction (BUY or SELL)
            size: Position size
            guaranteed_stop: Must be true if a guaranteed stop is required (cannot be used with trailing_stop or hedging mode)
            trailing_stop: Must be true if a trailing stop is required (requires stop_distance, cannot be used with guaranteed_stop)
            stop_level: Price level when a stop loss will be triggered
            stop_distance: Distance between current and stop loss triggering price (required if trailing_stop is true)
            stop_amount: Loss amount when a stop loss will be triggered
            profit_level: Price level when a take profit will be triggered
            profit_distance: Distance between current and take profit triggering price
            profit_amount: Profit amount when a take profit will be triggered
            
        Returns:
            Dict[str, Any]: Position creation result with dealReference
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
        
        # Validate parameter combinations per API rules
        if guaranteed_stop and trailing_stop:
            return {"error": "Cannot set both guaranteedStop and trailingStop - they are mutually exclusive"}
        
        if trailing_stop and not stop_distance:
            return {"error": "stopDistance is required when trailingStop is true"}
        
        if guaranteed_stop and not (stop_level or stop_distance or stop_amount):
            return {"error": "When guaranteedStop is true, must set stopLevel, stopDistance, or stopAmount"}
            
        try:
            url = f"{self.base_url}/api/v1/positions"
            headers = self._get_auth_headers()
            
            payload = {
                "epic": epic,
                "direction": direction,
                "size": size,  # API expects number, not string
            }
            
            # Stop loss parameters
            if guaranteed_stop is not None:
                payload["guaranteedStop"] = guaranteed_stop
                
            if trailing_stop is not None:
                payload["trailingStop"] = trailing_stop
                
            if stop_level is not None:
                payload["stopLevel"] = stop_level
                
            if stop_distance is not None:
                payload["stopDistance"] = stop_distance
                
            if stop_amount is not None:
                payload["stopAmount"] = stop_amount
                
            # Take profit parameters
            if profit_level is not None:
                payload["profitLevel"] = profit_level
                
            if profit_distance is not None:
                payload["profitDistance"] = profit_distance
                
            if profit_amount is not None:
                payload["profitAmount"] = profit_amount
            
            logger.info(f"Creating position with payload: {payload}")
            response = self._make_authenticated_request("POST", url, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Position creation response: {result}")
                
                # Add helpful metadata
                if "dealReference" in result:
                    result["_metadata"] = {
                        "note": "Position created with dealReference (order reference with 'o_' prefix)",
                        "next_steps": "Use get_positions() to find the actual dealId for position management",
                        "trailing_stop_active": trailing_stop if trailing_stop else False,
                        "guaranteed_stop_active": guaranteed_stop if guaranteed_stop else False
                    }
                
                return result
            else:
                error_details = response.text
                logger.error(f"Failed to create position: {response.status_code} - {error_details}")
                return {
                    "error": f"Failed to create position: {response.status_code}",
                    "details": error_details,
                    "attempted_payload": payload
                }
                
        except Exception as e:
            logger.error(f"Error creating position: {type(e).__name__}", exc_info=True)
            return {"error": f"Error creating position: {str(e)}"}
    
    def close_position(self, deal_id: str) -> Dict[str, Any]:
        """
        Close an open trading position
        
        Args:
            deal_id: The deal ID of the position to close
            
        Returns:
            Dict[str, Any]: Position closure result
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
            
        try:
            # First, get the position details to determine the direction and size
            positions = self.get_positions()
            if "error" in positions:
                return positions
                
            position_data = None
            for position in positions.get("positions", []):
                if position.get("position", {}).get("dealId") == deal_id:
                    position_data = position
                    break
                    
            if not position_data:
                logger.error(f"Position with deal ID {deal_id} not found")
                return {"error": f"Position with deal ID {deal_id} not found"}
                
            # Determine the opposite direction for closing
            original_direction = position_data.get("position", {}).get("direction")
            close_direction = "SELL" if original_direction == "BUY" else "BUY"
            
            # Get the size
            size = position_data.get("position", {}).get("size")
            
            # Get the epic
            epic = position_data.get("market", {}).get("epic")
            
            # Close the position
            url = f"{self.base_url}/api/v1/positions"
            headers = self._get_auth_headers()
            
            payload = {
                "dealId": deal_id,
                "epic": epic,
                "direction": close_direction,
                "size": size,
                "orderType": "MARKET"
            }
            
            logger.debug(f"Closing position with payload: {payload}")
            response = self._make_authenticated_request("DELETE", url, json=payload)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to close position: {response.status_code} - {response.text}")
                return {"error": f"Failed to close position: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error closing position: {type(e).__name__}", exc_info=True)
            return {"error": f"Error closing position: {str(e)}"}
    
    def update_position(
        self, 
        deal_id: str, 
        guaranteed_stop: Optional[bool] = None,
        trailing_stop: Optional[bool] = None,
        stop_level: Optional[float] = None, 
        stop_distance: Optional[float] = None,
        stop_amount: Optional[float] = None,
        profit_level: Optional[float] = None,
        profit_distance: Optional[float] = None,
        profit_amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Update an existing position with comprehensive stop/profit options
        
        Args:
            deal_id: The deal ID of the position to update
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
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
        
        # Validate parameter combinations per API rules
        if guaranteed_stop and trailing_stop:
            return {"error": "Cannot set both guaranteedStop and trailingStop - they are mutually exclusive"}
        
        if trailing_stop and not stop_distance:
            return {"error": "stopDistance is required when trailingStop is true"}
        
        if guaranteed_stop and not (stop_level or stop_distance or stop_amount):
            return {"error": "When guaranteedStop is true, must set stopLevel, stopDistance, or stopAmount"}
        
        # Check if at least one parameter is provided
        all_params = [guaranteed_stop, trailing_stop, stop_level, stop_distance, stop_amount, 
                     profit_level, profit_distance, profit_amount]
        if all(param is None for param in all_params):
            logger.error("At least one parameter must be provided")
            return {"error": "At least one parameter must be provided"}
            
        try:
            url = f"{self.base_url}/api/v1/positions/{deal_id}"
            headers = self._get_auth_headers()
            
            payload = {}
            
            # Stop loss parameters
            if guaranteed_stop is not None:
                payload["guaranteedStop"] = guaranteed_stop
                
            if trailing_stop is not None:
                payload["trailingStop"] = trailing_stop
                
            if stop_level is not None:
                payload["stopLevel"] = stop_level
                
            if stop_distance is not None:
                payload["stopDistance"] = stop_distance
                
            if stop_amount is not None:
                payload["stopAmount"] = stop_amount
                
            # Take profit parameters
            if profit_level is not None:
                payload["profitLevel"] = profit_level
                
            if profit_distance is not None:
                payload["profitDistance"] = profit_distance
                
            if profit_amount is not None:
                payload["profitAmount"] = profit_amount
            
            logger.info(f"Updating position {deal_id} with payload: {payload}")
            response = self._make_authenticated_request("PUT", url, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Position update response: {result}")
                
                # Add helpful metadata
                if "dealReference" in result:
                    result["_metadata"] = {
                        "note": "Position updated successfully",
                        "deal_id": deal_id,
                        "trailing_stop_active": trailing_stop if trailing_stop else False,
                        "guaranteed_stop_active": guaranteed_stop if guaranteed_stop else False,
                        "updated_parameters": list(payload.keys())
                    }
                
                return result
            else:
                error_details = response.text
                logger.error(f"Failed to update position: {response.status_code} - {error_details}")
                return {
                    "error": f"Failed to update position: {response.status_code}",
                    "details": error_details,
                    "attempted_payload": payload
                }
                
        except Exception as e:
            logger.error(f"Error updating position: {type(e).__name__}", exc_info=True)
            return {"error": f"Error updating position: {str(e)}"}
    
    def get_watchlists(self) -> Dict[str, Any]:
        """
        Get all watchlists
        
        Returns:
            Dict[str, Any]: Watchlists
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
            
        try:
            url = f"{self.base_url}/api/v1/watchlists"
            logger.debug(f"Getting watchlists from {url}")
            response = self._make_authenticated_request("GET", url)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get watchlists: {response.status_code} - {response.text}")
                return {"error": f"Failed to get watchlists: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error getting watchlists: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting watchlists: {str(e)}"}

    def get_historical_prices(self, epic: str, resolution: str, max_bars: int = 10, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get historical price data for a specific instrument with custom granularity
        
        Args:
            epic (str): The epic identifier for the instrument
            resolution (str): Time resolution (e.g., MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY, WEEK, MONTH)
            max_bars (int, optional): Maximum number of bars to return (default: 10)
            from_date (str, optional): Start date in ISO format (e.g., "2022-02-24T00:00:00")
            to_date (str, optional): End date in ISO format
            
        Returns:
            Dict: Historical price information
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
            
        try:
            url = f"{self.base_url}/api/v1/prices/{epic}"
            params = {
                "resolution": resolution,
                "max": max_bars
            }
            
            if from_date:
                params["from"] = from_date
            
            if to_date:
                params["to"] = to_date
            
            logger.debug(f"Getting historical prices for '{epic}' from {url}")
            response = self._make_authenticated_request("GET", url, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get historical prices: {response.status_code} - {response.text}")
                return {"error": f"Failed to get historical prices: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error getting historical prices: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting historical prices: {str(e)}"}

    def calculate_margin(self, epic: str, direction: str, size: float, leverage: float = 20.0) -> Dict:
        """
        Calculate margin requirements for a potential position
        
        Args:
            epic (str): The epic identifier for the instrument
            direction (str): "BUY" or "SELL"
            size (float): Trade size
            leverage (float): Leverage ratio (e.g., 20 for 20:1)
            
        Returns:
            Dict: Margin calculation result
        """
        # Get current price information
        price_info = self.get_prices(epic)
        
        if not price_info or "prices" not in price_info or not price_info["prices"]:
            return {"error": f"Could not retrieve price information for {epic}"}
        
        # Get the latest price
        latest_price = price_info["prices"][0]
        bid = float(latest_price.get("bid", 0))
        ask = float(latest_price.get("ask", 0))
        
        # Use bid for SELL and ask for BUY
        price = bid if direction == "SELL" else ask
        
        # Calculate margin required (approximate calculation)
        margin = (price * size) / leverage
        
        return {
            "instrument": epic,
            "direction": direction,
            "size": size,
            "leverage": leverage,
            "price": price,
            "margin_required": margin
        }

    # Session Management Methods
    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information including active financial account"""
        try:
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/session")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get session info: {response.status_code} - {response.text}")
                return {"error": f"Failed to get session info: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error getting session info: {str(e)}")
            return {"error": str(e)}

    def change_financial_account(self, account_id: str) -> Dict[str, Any]:
        """Switch to a different financial account"""
        try:
            data = {"accountId": account_id}
            response = self._make_authenticated_request("PUT", f"{self.base_url}/api/v1/session", json=data)
            if response.status_code == 200:
                # Update the X-SECURITY-TOKEN header for subsequent requests
                if 'X-SECURITY-TOKEN' in response.headers:
                    self.x_security_token = response.headers['X-SECURITY-TOKEN']
                return {"success": True, "message": f"Changed to account {account_id}"}
            else:
                logger.error(f"Failed to change account: {response.status_code} - {response.text}")
                return {"error": f"Failed to change account: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error changing account: {str(e)}")
            return {"error": str(e)}

    # Account Management Methods
    def get_accounts(self) -> Dict[str, Any]:
        """Get list of all financial accounts"""
        try:
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/accounts")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get accounts: {response.status_code} - {response.text}")
                return {"error": f"Failed to get accounts: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error getting accounts: {str(e)}")
            return {"error": str(e)}

    def get_account_preferences(self) -> Dict[str, Any]:
        """Get account preferences including leverage settings and hedging mode"""
        try:
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/accounts/preferences")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get account preferences: {response.status_code} - {response.text}")
                return {"error": f"Failed to get account preferences: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error getting account preferences: {str(e)}")
            return {"error": str(e)}

    def update_account_preferences(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Update account preferences including leverage settings and hedging mode"""
        try:
            response = self._make_authenticated_request("PUT", f"{self.base_url}/api/v1/accounts/preferences", json=preferences)
            if response.status_code == 200:
                return {"success": True, "message": "Account preferences updated"}
            else:
                logger.error(f"Failed to update account preferences: {response.status_code} - {response.text}")
                return {"error": f"Failed to update account preferences: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error updating account preferences: {str(e)}")
            return {"error": str(e)}

    def top_up_demo_account(self, amount: float) -> Dict[str, Any]:
        """Top up demo account balance"""
        try:
            data = {"amount": amount}
            response = self._make_authenticated_request("POST", f"{self.base_url}/api/v1/accounts/topUp", json=data)
            if response.status_code == 200:
                return {"success": True, "message": f"Demo account topped up with {amount}"}
            else:
                logger.error(f"Failed to top up demo account: {response.status_code} - {response.text}")
                return {"error": f"Failed to top up demo account: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error topping up demo account: {str(e)}")
            return {"error": str(e)}

    # Market Navigation Methods
    def get_market_navigation(self) -> Dict[str, Any]:
        """Get asset group names for market navigation"""
        try:
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/marketnavigation")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get market navigation: {response.status_code} - {response.text}")
                return {"error": f"Failed to get market navigation: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error getting market navigation: {str(e)}")
            return {"error": str(e)}

    def get_market_navigation_node(self, node_id: str) -> Dict[str, Any]:
        """Get assets under a specific market navigation node"""
        try:
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/marketnavigation/{node_id}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get market navigation node: {response.status_code} - {response.text}")
                return {"error": f"Failed to get market navigation node: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error getting market navigation node: {str(e)}")
            return {"error": str(e)}

    def get_watchlist_contents(self, watchlist_id: str) -> Dict[str, Any]:
        """Get contents of a specific watchlist"""
        try:
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/watchlists/{watchlist_id}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get watchlist contents: {response.status_code} - {response.text}")
                return {"error": f"Failed to get watchlist contents: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error getting watchlist contents: {str(e)}")
            return {"error": str(e)}

    # Working Orders Management Methods
    def create_working_order(self, epic: str, direction: str, size: float, level: float, 
                           order_type: str = "STOP", time_in_force: str = "GOOD_TILL_CANCELLED",
                           stop_level: Optional[float] = None, profit_level: Optional[float] = None) -> Dict[str, Any]:
        """Create a working order (stop or limit order)"""
        try:
            data = {
                "epic": epic,
                "direction": direction,
                "size": size,
                "level": level,
                "type": order_type,
                "timeInForce": time_in_force
            }
            
            if stop_level is not None:
                data["stopLevel"] = stop_level
            if profit_level is not None:
                data["profitLevel"] = profit_level
            
            logger.info(f"Creating working order with data: {data}")
            response = self._make_authenticated_request("POST", f"{self.base_url}/api/v1/workingorders", json=data)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Working order created: {result}")
                
                # Add helpful metadata
                if "dealReference" in result:
                    result["_metadata"] = {
                        "note": "dealReference returned is for order tracking. To manage this order, use get_working_orders() to find the actual working order ID.",
                        "next_steps": "Orders may take time to appear in get_working_orders(). Use the dealReference to track order status.",
                        "management_note": "For update/delete operations, you need the working order ID from get_working_orders(), not this dealReference."
                    }
                
                return result
            else:
                error_details = response.text
                logger.error(f"Failed to create working order: {response.status_code} - {error_details}")
                return {
                    "error": f"Failed to create working order: {response.status_code}",
                    "details": error_details,
                    "attempted_data": data
                }
        except Exception as e:
            logger.error(f"Error creating working order: {str(e)}")
            return {"error": str(e)}

    def get_working_orders(self) -> Dict[str, Any]:
        """Get all working orders"""
        try:
            logger.info("Getting working orders from API")
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/workingorders")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Working orders response: {result}")
                
                # Add metadata for debugging
                result["_metadata"] = {
                    "total_orders": len(result.get("workingOrders", [])),
                    "api_note": "Working orders may not appear immediately after creation",
                    "endpoint_used": "/api/v1/workingorders"
                }
                
                if not result.get("workingOrders"):
                    result["_info"] = "No working orders found. Orders may take time to appear after creation, or this could be normal for accounts with no pending orders."
                
                return result
            else:
                logger.error(f"Failed to get working orders: {response.status_code} - {response.text}")
                return {"error": f"Failed to get working orders: {response.status_code}", "details": response.text}
        except Exception as e:
            logger.error(f"Error getting working orders: {str(e)}")
            return {"error": str(e)}

    def update_working_order(self, working_order_id: str, level: Optional[float] = None,
                           stop_level: Optional[float] = None, profit_level: Optional[float] = None) -> Dict[str, Any]:
        """Update a working order
        
        Note: working_order_id should be the actual working order ID, not the dealReference from creation.
        Use get_working_orders() to find the correct ID for orders created with create_working_order().
        """
        try:
            data = {}
            if level is not None:
                data["level"] = level
            if stop_level is not None:
                data["stopLevel"] = stop_level
            if profit_level is not None:
                data["profitLevel"] = profit_level
            
            if not data:
                return {"error": "At least one parameter (level, stop_level, profit_level) must be provided"}
                
            logger.info(f"Updating working order {working_order_id} with data: {data}")
            response = self._make_authenticated_request("PUT", f"{self.base_url}/api/v1/workingorders/{working_order_id}", json=data)
            
            if response.status_code == 200:
                return {"success": True, "message": f"Working order {working_order_id} updated", "updated_data": data}
            else:
                error_details = response.text
                logger.error(f"Failed to update working order: {response.status_code} - {error_details}")
                return {
                    "error": f"Failed to update working order: {response.status_code}", 
                    "details": error_details,
                    "attempted_id": working_order_id,
                    "attempted_data": data,
                    "note": "Ensure working_order_id is correct. dealReference from creation may not be the same as working order ID."
                }
        except Exception as e:
            logger.error(f"Error updating working order: {str(e)}")
            return {"error": str(e)}

    def delete_working_order(self, working_order_id: str) -> Dict[str, Any]:
        """Delete a working order
        
        Note: working_order_id should be the actual working order ID, not the dealReference from creation.
        Use get_working_orders() to find the correct ID for orders created with create_working_order().
        """
        try:
            logger.info(f"Deleting working order {working_order_id}")
            response = self._make_authenticated_request("DELETE", f"{self.base_url}/api/v1/workingorders/{working_order_id}")
            
            if response.status_code == 200:
                return {"success": True, "message": f"Working order {working_order_id} deleted"}
            else:
                error_details = response.text
                logger.error(f"Failed to delete working order: {response.status_code} - {error_details}")
                return {
                    "error": f"Failed to delete working order: {response.status_code}",
                    "details": error_details,
                    "attempted_id": working_order_id,
                    "note": "Ensure working_order_id is correct. dealReference from creation may not be the same as working order ID."
                }
        except Exception as e:
            logger.error(f"Error deleting working order: {str(e)}")
            return {"error": str(e)}

    # History Methods
    def get_activity_history(self, from_date: Optional[str] = None, to_date: Optional[str] = None, 
                           last_period: Optional[int] = None, detailed: bool = False, 
                           deal_id: Optional[str] = None, filter_type: Optional[str] = None) -> Dict[str, Any]:
        """Get account activity history - supports both date ranges and lastPeriod (max 86400 seconds)"""
        try:
            params = {}
            
            # Format dates if provided (Capital.com expects YYYY-MM-DDTHH:MM:SS format, not ISO with timezone)
            if from_date:
                if from_date.endswith('Z'):
                    from_date = from_date[:-1]  # Remove 'Z' timezone indicator
                if '+' in from_date:
                    from_date = from_date.split('+')[0]  # Remove timezone offset
                params["from"] = from_date
                logger.info(f"Using from_date: {from_date}")
            
            if to_date:
                if to_date.endswith('Z'):
                    to_date = to_date[:-1]  # Remove 'Z' timezone indicator
                if '+' in to_date:
                    to_date = to_date.split('+')[0]  # Remove timezone offset
                params["to"] = to_date
                logger.info(f"Using to_date: {to_date}")
                
            # Validate date range if both provided (max 1 day per API docs)
            if from_date and to_date:
                try:
                    from_dt = datetime.strptime(from_date.split('+')[0].replace('Z', ''), "%Y-%m-%dT%H:%M:%S")
                    to_dt = datetime.strptime(to_date.split('+')[0].replace('Z', ''), "%Y-%m-%dT%H:%M:%S")
                    
                    time_diff = to_dt - from_dt
                    if time_diff.total_seconds() > 86400:  # More than 24 hours
                        logger.warning(f"Date range exceeds 24-hour limit: {time_diff.total_seconds()} seconds")
                        return {"error": "Date range cannot exceed 24 hours (86400 seconds)"}
                except ValueError as e:
                    logger.error(f"Error parsing dates: {e}")
                    return {"error": f"Invalid date format: {e}"}
            
            # lastPeriod support (not applicable if date range specified, max 86400 seconds)
            if last_period and not (from_date or to_date):
                if last_period > 86400:
                    logger.warning(f"lastPeriod too large: {last_period} seconds. API limit is 86400 seconds (24 hours)")
                    return {"error": "lastPeriod cannot exceed 86400 seconds (24 hours)"}
                params["lastPeriod"] = last_period
                logger.info(f"Using lastPeriod of {last_period} seconds")
            elif last_period and (from_date or to_date):
                logger.warning("lastPeriod ignored when date range is specified (per API documentation)")
            
            if detailed:
                params["detailed"] = str(detailed).lower()
            if deal_id:
                params["dealId"] = deal_id
            if filter_type:
                params["filter"] = filter_type
                
            logger.info(f"Getting activity history with params: {params}")
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/history/activity", params=params)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Activity history response: {result}")
                
                # Add metadata about the request
                result["_metadata"] = {
                    "requested_from": from_date,
                    "requested_to": to_date,
                    "last_period_seconds": last_period if not (from_date or to_date) else None,
                    "total_activities": len(result.get("activities", [])),
                    "deal_id_filter": deal_id,
                    "filter_applied": filter_type,
                    "detailed_mode": detailed,
                    "api_note": "Supports both date ranges (max 24h) and lastPeriod (max 86400s)"
                }
                
                if not result.get("activities"):
                    if from_date and to_date:
                        result["_info"] = f"No activities found between {from_date} and {to_date}. This could be normal for accounts with no trading activity in this period."
                    elif last_period:
                        hours = last_period / 3600
                        result["_info"] = f"No activities found in the last {hours:.1f} hours. This could be normal for accounts with no recent trading activity."
                    else:
                        result["_info"] = "No activities found in the default time range (last 10 minutes). This could be normal for accounts with no recent trading activity."
                    
                return result
            else:
                logger.error(f"Failed to get activity history: {response.status_code} - {response.text}")
                return {"error": f"Failed to get activity history: {response.status_code}", "details": response.text}
        except Exception as e:
            logger.error(f"Error getting activity history: {str(e)}")
            return {"error": str(e)}

    def get_transaction_history(self, from_date: Optional[str] = None, to_date: Optional[str] = None,
                              last_period: Optional[int] = None, transaction_type: Optional[str] = None) -> Dict[str, Any]:
        """Get transaction history - supports date ranges, lastPeriod, and transaction type filtering"""
        try:
            params = {}
            
            # Format dates if provided (Capital.com expects YYYY-MM-DDTHH:MM:SS format, not ISO with timezone)
            if from_date:
                if from_date.endswith('Z'):
                    from_date = from_date[:-1]  # Remove 'Z' timezone indicator
                if '+' in from_date:
                    from_date = from_date.split('+')[0]  # Remove timezone offset
                params["from"] = from_date
                logger.info(f"Using from_date: {from_date}")
            
            if to_date:
                if to_date.endswith('Z'):
                    to_date = to_date[:-1]  # Remove 'Z' timezone indicator
                if '+' in to_date:
                    to_date = to_date.split('+')[0]  # Remove timezone offset
                params["to"] = to_date
                logger.info(f"Using to_date: {to_date}")
            
            # Note: lastPeriod is not applicable if a date range has been specified
            if last_period and not (from_date or to_date):
                params["lastPeriod"] = last_period
                logger.info(f"Using lastPeriod of {last_period} seconds")
            elif last_period and (from_date or to_date):
                logger.warning("lastPeriod ignored when date range is specified (per API documentation)")
            
            if transaction_type:
                params["type"] = transaction_type
                logger.info(f"Filtering by transaction type: {transaction_type}")
            
            if not params:
                logger.info("No parameters specified, API will use default 600 seconds (10 minutes)")
                
            logger.info(f"Getting transaction history with params: {params}")
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/history/transactions", params=params)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Transaction history response: {result}")
                
                # Add metadata about the request
                result["_metadata"] = {
                    "requested_from": from_date,
                    "requested_to": to_date,
                    "last_period_seconds": last_period if not (from_date or to_date) else None,
                    "total_transactions": len(result.get("transactions", [])),
                    "transaction_type_filter": transaction_type,
                    "api_note": "API defaults to last 10 minutes if no parameters provided"
                }
                
                if not result.get("transactions"):
                    if from_date and to_date:
                        result["_info"] = f"No transactions found between {from_date} and {to_date}. This could be normal for accounts with no financial activity in this period."
                    elif last_period:
                        if last_period >= 86400:
                            days = last_period / 86400
                            time_desc = f"last {days:.1f} days"
                        elif last_period >= 3600:
                            hours = last_period / 3600
                            time_desc = f"last {hours:.1f} hours"
                        else:
                            time_desc = f"last {last_period} seconds"
                        result["_info"] = f"No transactions found in the {time_desc}. This could be normal for accounts with no recent financial activity."
                    else:
                        result["_info"] = "No transactions found in the default time range (last 10 minutes). This could be normal for accounts with no recent financial activity."
                    
                return result
            else:
                logger.error(f"Failed to get transaction history: {response.status_code} - {response.text}")
                return {"error": f"Failed to get transaction history: {response.status_code}", "details": response.text}
        except Exception as e:
            logger.error(f"Error getting transaction history: {str(e)}")
            return {"error": str(e)}

    # Position Confirmation Methods
    def confirm_deal(self, deal_reference: str) -> Dict[str, Any]:
        """Confirm the status of a position after creation using dealReference"""
        try:
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/confirms/{deal_reference}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to confirm deal: {response.status_code} - {response.text}")
                return {"error": f"Failed to confirm deal: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error confirming deal: {str(e)}")
            return {"error": str(e)}

    # Utility Methods
    def ping(self) -> Dict[str, Any]:
        """Test connection to the API"""
        try:
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/ping")
            if response.status_code == 200:
                return {"status": "ok", "message": "Connection successful"}
            else:
                logger.error(f"Ping failed: {response.status_code} - {response.text}")
                return {"error": f"Ping failed: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error pinging API: {str(e)}")
            return {"error": str(e)}

    def get_server_time(self) -> Dict[str, Any]:
        """Get server time"""
        try:
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/time")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get server time: {response.status_code} - {response.text}")
                return {"error": f"Failed to get server time: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error getting server time: {str(e)}")
            return {"error": str(e)}

    # Market Information Methods
    def get_client_sentiment(self, market_ids: Union[str, List[str]]) -> Dict[str, Any]:
        """Get client sentiment for markets
        
        Args:
            market_ids: Market identifier(s) - can be a single string or list of strings (e.g., "SILVER" or ["SILVER", "NATURALGAS"])
            
        Returns:
            Dict containing client sentiment data with long/short position percentages for each market
        """
        try:
            # Handle both single string and list of market IDs
            if isinstance(market_ids, str):
                market_ids_param = market_ids
            elif isinstance(market_ids, list):
                market_ids_param = ",".join(market_ids)
            else:
                return {"error": "market_ids must be a string or list of strings"}
            
            params = {"marketIds": market_ids_param}
            logger.info(f"Getting client sentiment for markets: {market_ids_param}")
            
            response = self._make_authenticated_request("GET", f"{self.base_url}/api/v1/clientsentiment", params=params)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Client sentiment response: {result}")
                
                # Add metadata for better understanding
                result["_metadata"] = {
                    "requested_markets": market_ids_param,
                    "total_markets": len(result.get("clientSentiments", [])),
                    "api_note": "Percentages show proportion of clients holding long vs short positions"
                }
                
                # Add helpful interpretation for each market
                if "clientSentiments" in result:
                    for sentiment in result["clientSentiments"]:
                        long_pct = sentiment.get("longPositionPercentage", 0)
                        short_pct = sentiment.get("shortPositionPercentage", 0)
                        
                        # Add interpretation
                        if long_pct > 70:
                            sentiment["_interpretation"] = "Strongly bullish sentiment - high proportion of long positions"
                        elif long_pct > 60:
                            sentiment["_interpretation"] = "Moderately bullish sentiment"
                        elif long_pct > 40:
                            sentiment["_interpretation"] = "Mixed sentiment - relatively balanced"
                        elif long_pct > 30:
                            sentiment["_interpretation"] = "Moderately bearish sentiment"
                        else:
                            sentiment["_interpretation"] = "Strongly bearish sentiment - high proportion of short positions"
                
                return result
            else:
                error_details = response.text
                logger.error(f"Failed to get client sentiment: {response.status_code} - {error_details}")
                return {
                    "error": f"Failed to get client sentiment: {response.status_code}",
                    "details": error_details,
                    "requested_markets": market_ids_param
                }
        except Exception as e:
            logger.error(f"Error getting client sentiment: {str(e)}")
            return {"error": str(e)}
