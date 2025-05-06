import os
import re
import requests
import json
import logging
import sys
from typing import Dict, List, Optional, Union, Any

# Configure logging
logger = logging.getLogger("capital-client")

class CapitalClient:
    """
    Client for interacting with Capital.com's API
    """
    
    def __init__(self):
        """Initialize the Capital.com client with credentials from environment variables"""
        # Get credentials directly from environment variables
        self.base_url = os.getenv("CAPITAL_BASE_URL")
        self.api_key = os.getenv("CAPITAL_API_KEY")
        self.password = os.getenv("CAPITAL_PASSWORD")
        self.identifier = os.getenv("CAPITAL_IDENTIFIER")
        
        # Check if required environment variables are set
        missing_vars = []
        if not self.base_url:
            missing_vars.append("CAPITAL_BASE_URL")
        if not self.api_key:
            missing_vars.append("CAPITAL_API_KEY")
        if not self.password:
            missing_vars.append("CAPITAL_PASSWORD")
        if not self.identifier:
            missing_vars.append("CAPITAL_IDENTIFIER")
            
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set these environment variables before running the server.")
            print("Example:")
            print("  export CAPITAL_BASE_URL=https://demo-api-capital.backend-capital.com")
            print("  export CAPITAL_API_KEY=your_api_key_here")
            print("  export CAPITAL_PASSWORD=your_password_here")
            print("  export CAPITAL_IDENTIFIER=your_email@example.com  # Email address used for your Capital.com account")
        
        # Session tokens that will be populated after authentication
        self.session_token = os.getenv("CAPITAL_SESSION_TOKEN", "")
        self.security_token = os.getenv("CAPITAL_SECURITY_TOKEN", "")
        self.cst = os.getenv("CAPITAL_CST", "")
        
        self.headers = {
            "X-CAP-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Trading limits for safety
        self.max_position_size = 10.0  # Maximum position size allowed
        self.min_position_size = 0.01  # Minimum position size allowed
        self.max_daily_trades = 20     # Maximum number of trades per day
        self.daily_trade_count = 0     # Counter for trades made today
        
        # Rate limiting
        self.request_count = 0
        self.max_requests_per_minute = 60
    
    def _sanitize_log_data(self, data: Dict) -> Dict:
        """
        Sanitize sensitive data for logging
        
        Args:
            data (Dict): Data to sanitize
            
        Returns:
            Dict: Sanitized data
        """
        if not isinstance(data, dict):
            return data
            
        sanitized = data.copy()
        
        # List of keys to mask in logs
        sensitive_keys = [
            'password', 'api_key', 'apiKey', 'token', 'session', 
            'security', 'cst', 'identifier', 'email'
        ]
        
        for key in sanitized:
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "********"
            elif isinstance(sanitized[key], dict):
                sanitized[key] = self._sanitize_log_data(sanitized[key])
        
        return sanitized
    
    def _validate_input(self, **kwargs) -> Optional[str]:
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
                        if num_value < self.min_position_size:
                            return f"Position size too small, minimum is {self.min_position_size}"
                        if num_value > self.max_position_size:
                            return f"Position size too large, maximum is {self.max_position_size}"
                    
                    # Leverage validation
                    if key == 'leverage' and (num_value <= 0 or num_value > 100):
                        return f"Leverage must be between 1 and 100, got {num_value}"
                    
                    # Max bars validation
                    if key == 'max_bars' and (num_value <= 0 or num_value > 1000):
                        return f"Max bars must be between 1 and 1000, got {num_value}"
                        
                except ValueError:
                    return f"Parameter '{key}' must be a number"
        
        return None
    
    def _check_rate_limit(self) -> bool:
        """
        Check if rate limit has been exceeded
        
        Returns:
            bool: True if request can proceed, False if rate limited
        """
        self.request_count += 1
        
        if self.request_count > self.max_requests_per_minute:
            logger.warning("Rate limit exceeded")
            return False
        
        return True
    
    def authenticate(self) -> bool:
        """
        Authenticate with Capital.com API and store session tokens
        
        Returns:
            bool: True if authentication was successful, False otherwise
        """
        if not self._check_rate_limit():
            return False
            
        endpoint = f"{self.base_url}/api/v1/session"
        payload = {
            "identifier": self.identifier,
            "password": self.password
        }
        
        # Log sanitized authentication attempt
        logger.info("Attempting authentication with Capital.com API")
        
        try:
            response = requests.post(
                endpoint, 
                headers=self.headers, 
                json=payload,
                verify=True  # Explicitly verify SSL certificate
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Store session tokens
            self.cst = response.headers.get("CST")
            self.security_token = response.headers.get("X-SECURITY-TOKEN")
            
            # Update headers with authentication tokens
            self.headers["CST"] = self.cst
            self.headers["X-SECURITY-TOKEN"] = self.security_token
            
            logger.info("Authentication successful")
            return True
        
        except requests.exceptions.RequestException as e:
            # Log sanitized error
            logger.error(f"Authentication failed: {type(e).__name__}")
            return False
    
    def get_account_info(self) -> Dict:
        """
        Get account information
        
        Returns:
            Dict: Account information
        """
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        endpoint = f"{self.base_url}/api/v1/accounts"
        
        logger.info("Retrieving account information")
        
        try:
            response = requests.get(
                endpoint, 
                headers=self.headers,
                verify=True
            )
            response.raise_for_status()
            
            # Log success without sensitive data
            logger.info("Successfully retrieved account information")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get account info: {type(e).__name__}"
            logger.error(error_msg)
            return {"error": "Failed to retrieve account information"}
    
    def get_markets(self, search_term: Optional[str] = None) -> Dict:
        """
        Get available markets, optionally filtered by search term
        
        Args:
            search_term (str, optional): Term to search for
            
        Returns:
            Dict: Available markets
        """
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        # Validate input
        validation_error = self._validate_input(search_term=search_term)
        if validation_error:
            logger.error(f"Input validation error: {validation_error}")
            return {"error": validation_error}
            
        endpoint = f"{self.base_url}/api/v1/markets"
        params = {}
        
        if search_term:
            params["searchTerm"] = search_term
        
        logger.info(f"Searching markets with term: {search_term}")
        
        try:
            response = requests.get(
                endpoint, 
                headers=self.headers, 
                params=params,
                verify=True
            )
            response.raise_for_status()
            
            logger.info(f"Successfully retrieved markets for search term: {search_term}")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get markets: {type(e).__name__}"
            logger.error(error_msg)
            return {"error": "Failed to retrieve markets"}
    
    def get_prices(self, epic: str) -> Dict:
        """
        Get prices for a specific instrument
        
        Args:
            epic (str): The epic identifier for the instrument
            
        Returns:
            Dict: Price information
        """
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        # Validate input
        validation_error = self._validate_input(epic=epic)
        if validation_error:
            logger.error(f"Input validation error: {validation_error}")
            return {"error": validation_error}
            
        endpoint = f"{self.base_url}/api/v1/prices/{epic}"
        
        logger.info(f"Retrieving prices for instrument: {epic}")
        
        try:
            response = requests.get(
                endpoint, 
                headers=self.headers,
                verify=True
            )
            response.raise_for_status()
            
            logger.info(f"Successfully retrieved prices for {epic}")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get prices: {type(e).__name__}"
            logger.error(error_msg)
            return {"error": f"Failed to retrieve prices for {epic}"}
            
    def get_historical_prices(self, epic: str, resolution: str, max_bars: int = 10, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Dict:
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
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        # Validate input
        validation_error = self._validate_input(
            epic=epic, 
            resolution=resolution,
            max_bars=max_bars,
            from_date=from_date,
            to_date=to_date
        )
        if validation_error:
            logger.error(f"Input validation error: {validation_error}")
            return {"error": validation_error}
            
        endpoint = f"{self.base_url}/api/v1/prices/{epic}"
        params = {
            "resolution": resolution,
            "max": max_bars
        }
        
        if from_date:
            params["from"] = from_date
        
        if to_date:
            params["to"] = to_date
        
        logger.info(f"Retrieving historical prices for {epic} with resolution {resolution}")
        
        try:
            response = requests.get(
                endpoint, 
                headers=self.headers, 
                params=params,
                verify=True
            )
            response.raise_for_status()
            
            logger.info(f"Successfully retrieved historical prices for {epic}")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get historical prices: {type(e).__name__}"
            logger.error(error_msg)
            return {"error": f"Failed to retrieve historical prices for {epic}"}
    
    def _check_trading_limits(self) -> Optional[str]:
        """
        Check if trading limits have been exceeded
        
        Returns:
            Optional[str]: Error message if limits exceeded, None otherwise
        """
        if self.daily_trade_count >= self.max_daily_trades:
            return f"Daily trading limit of {self.max_daily_trades} trades has been reached"
        
        return None

    def create_position(self, epic: str, direction: str, size: float, 
                    stop_level: Optional[float] = None, 
                    profit_level: Optional[float] = None,
                    leverage: Optional[float] = None) -> Dict:
        """
        Create a new trading position
        
        Args:
            epic (str): The epic identifier for the instrument
            direction (str): "BUY" or "SELL"
            size (float): Trade size
            stop_level (float, optional): Stop loss level
            profit_level (float, optional): Take profit level
            leverage (float, optional): Leverage ratio (e.g., 20 for 20:1)
            
        Returns:
            Dict: Position creation result
        """
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        # Validate input
        validation_error = self._validate_input(
            epic=epic,
            direction=direction,
            size=size,
            stop_level=stop_level,
            profit_level=profit_level,
            leverage=leverage
        )
        if validation_error:
            logger.error(f"Input validation error: {validation_error}")
            return {"error": validation_error}
        
        # Check trading limits
        limit_error = self._check_trading_limits()
        if limit_error:
            logger.error(f"Trading limit error: {limit_error}")
            return {"error": limit_error}
            
        endpoint = f"{self.base_url}/api/v1/positions"
        
        payload = {
            "epic": epic,
            "direction": direction,
            "size": str(size),
        }
        
        if stop_level:
            payload["stopLevel"] = str(stop_level)
        
        if profit_level:
            payload["profitLevel"] = str(profit_level)
        
        if leverage:
            payload["leverage"] = str(leverage)
        
        logger.info(f"Creating position for {epic}, direction: {direction}, size: {size}")
        
        try:
            response = requests.post(
                endpoint, 
                headers=self.headers, 
                json=payload,
                verify=True
            )
            response.raise_for_status()
            
            # Increment trade counter
            self.daily_trade_count += 1
            
            logger.info(f"Successfully created position for {epic}")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to create position: {type(e).__name__}"
            logger.error(error_msg)
            return {"error": "Failed to create position"}
    
    def get_positions(self) -> Dict:
        """
        Get all open positions
        
        Returns:
            Dict: Open positions
        """
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        endpoint = f"{self.base_url}/api/v1/positions"
        
        logger.info("Retrieving open positions")
        
        try:
            response = requests.get(
                endpoint, 
                headers=self.headers,
                verify=True
            )
            response.raise_for_status()
            
            logger.info("Successfully retrieved open positions")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get positions: {type(e).__name__}"
            logger.error(error_msg)
            return {"error": "Failed to retrieve open positions"}
    
    def close_position(self, deal_id: str) -> Dict:
        """
        Close an open position
        
        Args:
            deal_id (str): The deal ID to close
            
        Returns:
            Dict: Position closure result
        """
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        # Validate input
        validation_error = self._validate_input(deal_id=deal_id)
        if validation_error:
            logger.error(f"Input validation error: {validation_error}")
            return {"error": validation_error}
            
        endpoint = f"{self.base_url}/api/v1/positions/{deal_id}"
        
        logger.info(f"Closing position with deal ID: {deal_id}")
        
        try:
            response = requests.delete(
                endpoint, 
                headers=self.headers,
                verify=True
            )
            response.raise_for_status()
            
            logger.info(f"Successfully closed position with deal ID: {deal_id}")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to close position: {type(e).__name__}"
            logger.error(error_msg)
            return {"error": f"Failed to close position with deal ID: {deal_id}"}

    def update_position(self, deal_id: str, stop_level: Optional[float] = None, profit_level: Optional[float] = None) -> Dict:
        """
        Update an existing position with new stop loss and/or take profit levels
        
        Args:
            deal_id (str): The deal ID of the position to update
            stop_level (float, optional): New stop loss level
            profit_level (float, optional): New take profit level
            
        Returns:
            Dict: Position update result
        """
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        # Validate input
        validation_error = self._validate_input(
            deal_id=deal_id,
            stop_level=stop_level,
            profit_level=profit_level
        )
        if validation_error:
            logger.error(f"Input validation error: {validation_error}")
            return {"error": validation_error}
            
        # Check if at least one parameter is provided
        if stop_level is None and profit_level is None:
            error_msg = "At least one of stop_level or profit_level must be provided"
            logger.error(error_msg)
            return {"error": error_msg}
            
        endpoint = f"{self.base_url}/api/v1/positions/{deal_id}"
        
        payload = {}
        if stop_level is not None:
            payload["stopLevel"] = str(stop_level)
        if profit_level is not None:
            payload["profitLevel"] = str(profit_level)
        
        logger.info(f"Updating position with deal ID: {deal_id}")
        
        try:
            response = requests.put(
                endpoint, 
                headers=self.headers, 
                json=payload,
                verify=True
            )
            response.raise_for_status()
            
            logger.info(f"Successfully updated position with deal ID: {deal_id}")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to update position: {type(e).__name__}"
            logger.error(error_msg)
            return {"error": f"Failed to update position with deal ID: {deal_id}"}

    def get_watchlists(self) -> Dict:
        """
        Get all watchlists
        
        Returns:
            Dict: Watchlists
        """
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        endpoint = f"{self.base_url}/api/v1/watchlists"
        
        logger.info("Retrieving watchlists")
        
        try:
            response = requests.get(
                endpoint, 
                headers=self.headers,
                verify=True
            )
            response.raise_for_status()
            
            logger.info("Successfully retrieved watchlists")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get watchlists: {type(e).__name__}"
            logger.error(error_msg)
            return {"error": "Failed to retrieve watchlists"}

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
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded"}
            
        # Validate input
        validation_error = self._validate_input(
            epic=epic,
            direction=direction,
            size=size,
            leverage=leverage
        )
        if validation_error:
            logger.error(f"Input validation error: {validation_error}")
            return {"error": validation_error}
            
        # Get current price information
        price_info = self.get_prices(epic)
        
        if "error" in price_info:
            return price_info
            
        if not price_info or "prices" not in price_info or not price_info["prices"]:
            error_msg = f"Could not retrieve price information for {epic}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Get the latest price
        latest_price = price_info["prices"][0]
        bid = float(latest_price.get("bid", 0))
        ask = float(latest_price.get("ask", 0))
        
        # Use bid for SELL and ask for BUY
        price = bid if direction == "SELL" else ask
        
        # Calculate margin required (approximate calculation)
        margin = (price * size) / leverage
        
        logger.info(f"Calculated margin for {epic}: {margin:.2f} at leverage {leverage}:1")
        
        return {
            "instrument": epic,
            "direction": direction,
            "size": size,
            "leverage": leverage,
            "price": price,
            "margin_required": margin
        }