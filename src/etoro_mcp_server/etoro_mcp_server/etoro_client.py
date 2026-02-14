import os
import uuid
import requests
import logging
from typing import Dict, List, Optional, Union, Any
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger("etoro-client")


class EtoroClient:
    """
    Client for interacting with eToro's API
    """

    def __init__(self, base_url=None, api_key=None, user_key=None, account_type=None):
        """Initialize the eToro client with credentials from environment variables"""
        load_dotenv()

        # Get credentials from parameters or environment variables
        self.base_url = base_url or os.getenv("ETORO_BASE_URL", "https://api.etoro.com")
        self.api_key = api_key or os.getenv("ETORO_API_KEY")
        self.user_key = user_key or os.getenv("ETORO_USER_KEY")
        self.account_type = account_type or os.getenv("ETORO_ACCOUNT_TYPE", "demo")

        # Validate account type
        if self.account_type not in ["demo", "real"]:
            logger.warning(f"Invalid account_type '{self.account_type}', defaulting to 'demo'")
            self.account_type = "demo"

        # Initialize session
        self.session = requests.Session()

        # Configure logging
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        if os.environ.get("ETORO_MCP_DEBUG", "0") == "1":
            logger.setLevel(logging.DEBUG)

    def _generate_request_id(self) -> str:
        """
        Generate a unique UUID for x-request-id header

        Returns:
            str: UUID string
        """
        return str(uuid.uuid4())

    def _get_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests

        Returns:
            Dict[str, str]: Headers dictionary with API keys and request ID
        """
        headers = {
            "Content-Type": "application/json",
            "x-request-id": self._generate_request_id()
        }

        if self.api_key:
            headers["x-api-key"] = self.api_key

        if self.user_key:
            headers["x-user-key"] = self.user_key

        return headers

    def _get_endpoint_path(self, resource: str) -> str:
        """
        Build endpoint path based on account type (demo vs real)

        Args:
            resource: API resource path (e.g., "instruments/search")

        Returns:
            str: Full endpoint path
        """
        prefix = "/api/demo/v1" if self.account_type == "demo" else "/api/v1"
        # Ensure resource doesn't start with /
        resource = resource.lstrip("/")
        return f"{prefix}/{resource}"

    def _make_request(self, method: str, resource: str, **kwargs) -> Dict[str, Any]:
        """
        Make an authenticated API request

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            resource: API resource path
            **kwargs: Additional request parameters

        Returns:
            Dict[str, Any]: Response data or error dictionary
        """
        url = f"{self.base_url}{self._get_endpoint_path(resource)}"
        headers = self._get_headers()

        logger.debug(f"Making {method} request to {url}")

        try:
            response = self.session.request(method, url, headers=headers, **kwargs)

            # Check for authentication errors
            if response.status_code == 401:
                logger.error("Authentication failed - invalid API keys")
                return {"error": "Authentication failed. Check your eToro API keys."}

            # Check for success
            if response.ok:
                try:
                    return response.json()
                except ValueError:
                    # Response has no content or is not JSON
                    return {"success": True}
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return {"error": f"API request failed: {response.status_code}", "details": response.text}

        except Exception as e:
            logger.error(f"Error making request: {type(e).__name__}", exc_info=True)
            return {"error": f"Request error: {str(e)}"}

    def validate_credentials(self) -> bool:
        """
        Validate API credentials by making a lightweight API call

        Returns:
            bool: True if credentials are valid, False otherwise
        """
        if not self.api_key or not self.user_key:
            logger.error("Missing API credentials")
            return False

        try:
            # Try to get account info as a lightweight test
            result = self.get_account_info()

            if "error" in result:
                logger.error(f"Credential validation failed: {result['error']}")
                return False

            logger.info("API credentials validated successfully")
            return True

        except Exception as e:
            logger.error(f"Error validating credentials: {type(e).__name__}", exc_info=True)
            return False

    # Account & Portfolio Methods
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information including balance, equity, and margin

        Returns:
            Dict[str, Any]: Account information
        """
        try:
            logger.debug("Getting account info")
            result = self._make_request("GET", "account/info")

            if "error" in result:
                logger.error(f"Failed to get account info: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting account info: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting account info: {str(e)}"}

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio summary with allocation and performance

        Returns:
            Dict[str, Any]: Portfolio summary
        """
        try:
            logger.debug("Getting portfolio summary")
            result = self._make_request("GET", "portfolio/summary")

            if "error" in result:
                logger.error(f"Failed to get portfolio summary: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting portfolio summary: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting portfolio summary: {str(e)}"}

    # Market Data Methods
    def search_instruments(self, search_term: str = None, category: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        Search for tradeable instruments

        Args:
            search_term: Search query (e.g., "Apple", "Bitcoin")
            category: Filter by category (e.g., "stocks", "crypto", "currencies")
            limit: Maximum number of results

        Returns:
            Dict[str, Any]: Search results with instrument details
        """
        try:
            params = {}

            if search_term:
                params["q"] = search_term

            if category:
                params["category"] = category

            if limit:
                params["limit"] = limit

            logger.debug(f"Searching instruments with params: {params}")
            result = self._make_request("GET", "instruments/search", params=params)

            if "error" in result:
                logger.error(f"Failed to search instruments: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error searching instruments: {type(e).__name__}", exc_info=True)
            return {"error": f"Error searching instruments: {str(e)}"}

    def get_instrument_metadata(self, instrument_id: int) -> Dict[str, Any]:
        """
        Get detailed metadata for a specific instrument

        Args:
            instrument_id: Instrument ID (integer)

        Returns:
            Dict[str, Any]: Instrument metadata including spread, trading hours, limits
        """
        try:
            # Validate instrument_id
            if not isinstance(instrument_id, int) or instrument_id <= 0:
                return {"error": "instrument_id must be a positive integer"}

            logger.debug(f"Getting metadata for instrument {instrument_id}")
            result = self._make_request("GET", f"instruments/{instrument_id}/metadata")

            if "error" in result:
                logger.error(f"Failed to get instrument metadata: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting instrument metadata: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting instrument metadata: {str(e)}"}

    def get_current_rates(self, instrument_ids: Union[int, List[int]]) -> Dict[str, Any]:
        """
        Get current real-time bid/ask prices for instruments

        Args:
            instrument_ids: Single instrument ID or list of instrument IDs

        Returns:
            Dict[str, Any]: Current rates with bid/ask prices
        """
        try:
            # Convert single ID to list
            if isinstance(instrument_ids, int):
                id_list = [instrument_ids]
            elif isinstance(instrument_ids, list):
                id_list = instrument_ids
            else:
                return {"error": "instrument_ids must be an integer or list of integers"}

            # Validate all IDs are positive integers
            for inst_id in id_list:
                if not isinstance(inst_id, int) or inst_id <= 0:
                    return {"error": "All instrument IDs must be positive integers"}

            # Convert to comma-separated string
            ids_param = ",".join(str(id) for id in id_list)

            logger.debug(f"Getting current rates for instruments: {ids_param}")
            result = self._make_request("GET", "rates/current", params={"instrumentIds": ids_param})

            if "error" in result:
                logger.error(f"Failed to get current rates: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting current rates: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting current rates: {str(e)}"}

    # Position Management Methods
    def get_positions(self) -> Dict[str, Any]:
        """
        Get all open trading positions

        Returns:
            Dict[str, Any]: Open positions
        """
        try:
            logger.debug("Getting positions")
            result = self._make_request("GET", "positions")

            if "error" in result:
                logger.error(f"Failed to get positions: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting positions: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting positions: {str(e)}"}

    def create_position(
        self,
        instrument_id: int,
        direction: str,
        amount: float,
        leverage: int = 1,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a new trading position

        Args:
            instrument_id: Instrument ID (integer)
            direction: Trade direction ("BUY" or "SELL")
            amount: Investment amount in account currency
            leverage: Leverage multiplier (e.g., 1, 2, 5, 10, 20)
            stop_loss: Stop loss price level (optional)
            take_profit: Take profit price level (optional)

        Returns:
            Dict[str, Any]: Position creation result with position_id
        """
        try:
            # Validate inputs
            if not isinstance(instrument_id, int) or instrument_id <= 0:
                return {"error": "instrument_id must be a positive integer"}

            if direction not in ["BUY", "SELL"]:
                return {"error": "direction must be 'BUY' or 'SELL'"}

            if amount <= 0:
                return {"error": "amount must be greater than 0"}

            if leverage < 1:
                return {"error": "leverage must be at least 1"}

            # Build payload
            payload = {
                "instrumentId": instrument_id,
                "direction": direction,
                "amount": amount,
                "leverage": leverage
            }

            if stop_loss is not None:
                payload["stopLoss"] = stop_loss

            if take_profit is not None:
                payload["takeProfit"] = take_profit

            logger.info(f"Creating position: {payload}")
            result = self._make_request("POST", "positions", json=payload)

            if "error" in result:
                logger.error(f"Failed to create position: {result['error']}")
            else:
                logger.info(f"Position created successfully: {result}")

            return result

        except Exception as e:
            logger.error(f"Error creating position: {type(e).__name__}", exc_info=True)
            return {"error": f"Error creating position: {str(e)}"}

    def close_position(self, position_id: str) -> Dict[str, Any]:
        """
        Close an open trading position

        Args:
            position_id: Position ID to close

        Returns:
            Dict[str, Any]: Position closure result
        """
        try:
            if not position_id:
                return {"error": "position_id cannot be empty"}

            logger.info(f"Closing position: {position_id}")
            result = self._make_request("DELETE", f"positions/{position_id}")

            if "error" in result:
                logger.error(f"Failed to close position: {result['error']}")
            else:
                logger.info(f"Position closed successfully")

            return result

        except Exception as e:
            logger.error(f"Error closing position: {type(e).__name__}", exc_info=True)
            return {"error": f"Error closing position: {str(e)}"}

    def update_position(
        self,
        position_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Update stop loss and/or take profit for an existing position

        Args:
            position_id: Position ID to update
            stop_loss: New stop loss price level (optional)
            take_profit: New take profit price level (optional)

        Returns:
            Dict[str, Any]: Position update result
        """
        try:
            if not position_id:
                return {"error": "position_id cannot be empty"}

            if stop_loss is None and take_profit is None:
                return {"error": "At least one parameter (stop_loss or take_profit) must be provided"}

            # Build payload
            payload = {}

            if stop_loss is not None:
                payload["stopLoss"] = stop_loss

            if take_profit is not None:
                payload["takeProfit"] = take_profit

            logger.info(f"Updating position {position_id}: {payload}")
            result = self._make_request("PUT", f"positions/{position_id}", json=payload)

            if "error" in result:
                logger.error(f"Failed to update position: {result['error']}")
            else:
                logger.info(f"Position updated successfully")

            return result

        except Exception as e:
            logger.error(f"Error updating position: {type(e).__name__}", exc_info=True)
            return {"error": f"Error updating position: {str(e)}"}
