import os
import re
import requests
import json
import logging
import sys
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
        stop_level: Optional[float] = None, 
        profit_level: Optional[float] = None,
        leverage: Optional[float] = None,
        guaranteed_stop: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Create a new trading position
        
        Args:
            epic: The epic identifier for the instrument
            direction: Trade direction (BUY or SELL)
            size: Position size
            stop_level: Stop loss level (optional)
            profit_level: Take profit level (optional)
            leverage: Leverage ratio (e.g., 20 for 20:1) (optional)
            guaranteed_stop: Whether to use a guaranteed stop (optional)
            
        Returns:
            Dict[str, Any]: Position creation result
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
            
        try:
            url = f"{self.base_url}/api/v1/positions"
            headers = self._get_auth_headers()
            
            payload = {
                "epic": epic,
                "direction": direction,
                "size": str(size),
            }
            
            if stop_level is not None:
                payload["stopLevel"] = str(stop_level)
                
            if profit_level is not None:
                payload["profitLevel"] = str(profit_level)
                
            if leverage is not None:
                payload["leverage"] = str(leverage)
                
            if guaranteed_stop is not None:
                payload["guaranteedStop"] = guaranteed_stop
            
            logger.debug(f"Creating position with payload: {payload}")
            response = self._make_authenticated_request("POST", url, json=payload)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to create position: {response.status_code} - {response.text}")
                return {"error": f"Failed to create position: {response.status_code}"}
                
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
        stop_level: Optional[float] = None, 
        profit_level: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Update an existing position with new stop loss and/or take profit levels
        
        Args:
            deal_id: The deal ID of the position to update
            stop_level: New stop loss level (optional)
            profit_level: New take profit level (optional)
            
        Returns:
            Dict[str, Any]: Position update result
        """
        if not self.account_id:
            logger.error("Not authenticated")
            return {"error": "Not authenticated"}
            
        if stop_level is None and profit_level is None:
            logger.error("At least one of stop_level or profit_level must be provided")
            return {"error": "At least one of stop_level or profit_level must be provided"}
            
        try:
            url = f"{self.base_url}/api/v1/positions/{deal_id}"
            headers = self._get_auth_headers()
            
            payload = {}
            
            if stop_level is not None:
                payload["stopLevel"] = str(stop_level)
                
            if profit_level is not None:
                payload["profitLevel"] = str(profit_level)
            
            logger.debug(f"Updating position with payload: {payload}")
            response = self._make_authenticated_request("PUT", url, json=payload)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to update position: {response.status_code} - {response.text}")
                return {"error": f"Failed to update position: {response.status_code}"}
                
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
