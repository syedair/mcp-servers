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
    Client for interacting with eToro's Public API.

    API Reference: https://api-portal.etoro.com/
    Base URL: https://public-api.etoro.com
    Auth: x-api-key + x-user-key + x-request-id headers
    """

    def __init__(self, base_url=None, api_key=None, user_key=None, account_type=None):
        """Initialize the eToro client with credentials from environment variables"""
        load_dotenv()

        # Get credentials from parameters or environment variables
        self.base_url = base_url or os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com")
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
        """Generate a unique UUID for x-request-id header"""
        return str(uuid.uuid4())

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        headers = {
            "Content-Type": "application/json",
            "x-request-id": self._generate_request_id()
        }

        if self.api_key:
            headers["x-api-key"] = self.api_key

        if self.user_key:
            headers["x-user-key"] = self.user_key

        return headers

    def _build_url(self, path: str) -> str:
        """
        Build full API URL from a path.

        Args:
            path: Full API path (e.g., "/api/v1/market-data/search")

        Returns:
            str: Full URL
        """
        return f"{self.base_url}{path}"

    def _get_trading_execution_path(self, resource: str) -> str:
        """
        Build trading execution endpoint path based on account type.

        Demo:  /api/v1/trading/execution/demo/{resource}
        Real:  /api/v1/trading/execution/{resource}
        """
        if self.account_type == "demo":
            return f"/api/v1/trading/execution/demo/{resource}"
        return f"/api/v1/trading/execution/{resource}"

    def _get_trading_info_path(self, resource: str) -> str:
        """
        Build trading info endpoint path based on account type.

        Demo:  /api/v1/trading/info/demo/{resource}
        Real:  /api/v1/trading/info/{resource}
        """
        if self.account_type == "demo":
            return f"/api/v1/trading/info/demo/{resource}"
        return f"/api/v1/trading/info/{resource}"

    def _make_request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """
        Make an authenticated API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: Full API path (e.g., "/api/v1/market-data/search")
            **kwargs: Additional request parameters

        Returns:
            Dict[str, Any]: Response data or error dictionary
        """
        url = self._build_url(path)
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
                    return {"success": True}
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return {"error": f"API request failed: {response.status_code}", "details": response.text}

        except Exception as e:
            logger.error(f"Error making request: {type(e).__name__}", exc_info=True)
            return {"error": f"Request error: {str(e)}"}

    def validate_credentials(self) -> bool:
        """
        Validate API credentials by checking keys are present and making
        a lightweight market data call.

        Returns:
            bool: True if credentials are valid, False otherwise
        """
        if not self.api_key or not self.user_key:
            logger.error("Missing API credentials (ETORO_API_KEY and/or ETORO_USER_KEY not set)")
            return False

        try:
            # Use a lightweight market data endpoint for validation
            result = self._make_request("GET", "/api/v1/market-data/search", params={"pageSize": 1})

            if "error" in result:
                logger.error(f"Credential validation failed: {result['error']}")
                return False

            logger.info("API credentials validated successfully")
            return True

        except Exception as e:
            logger.error(f"Error validating credentials: {type(e).__name__}", exc_info=True)
            return False

    # =====================
    # Portfolio & Account
    # =====================

    def get_portfolio(self) -> Dict[str, Any]:
        """
        Get comprehensive portfolio information including positions, orders, and account status.

        Endpoint:
          Demo: GET /api/v1/trading/info/demo/portfolio
          Real: GET /api/v1/trading/info/portfolio

        Returns:
            Dict[str, Any]: Portfolio data with clientPortfolio containing
                positions, credit, orders, mirrors, bonusCredit
        """
        try:
            path = self._get_trading_info_path("portfolio")
            logger.debug("Getting portfolio")
            result = self._make_request("GET", path)

            if "error" in result:
                logger.error(f"Failed to get portfolio: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting portfolio: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting portfolio: {str(e)}"}

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information (balance, credit) from portfolio endpoint.

        Returns:
            Dict[str, Any]: Account info extracted from portfolio
        """
        try:
            result = self.get_portfolio()

            if "error" in result:
                return result

            # Extract account info from portfolio response
            portfolio = result.get("clientPortfolio", result)
            account_info = {
                "credit": portfolio.get("credit"),
                "bonusCredit": portfolio.get("bonusCredit"),
                "account_type": self.account_type,
            }

            return account_info

        except Exception as e:
            logger.error(f"Error getting account info: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting account info: {str(e)}"}

    def get_positions(self) -> Dict[str, Any]:
        """
        Get all open trading positions from portfolio endpoint.

        Returns:
            Dict[str, Any]: Positions data
        """
        try:
            result = self.get_portfolio()

            if "error" in result:
                return result

            # Extract positions from portfolio response
            portfolio = result.get("clientPortfolio", result)
            positions = portfolio.get("positions", [])

            return {"positions": positions}

        except Exception as e:
            logger.error(f"Error getting positions: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting positions: {str(e)}"}

    def get_pnl(self) -> Dict[str, Any]:
        """
        Get account PnL and portfolio details.

        Endpoint:
          Demo: GET /api/v1/trading/info/demo/pnl
          Real: GET /api/v1/trading/info/pnl

        Returns:
            Dict[str, Any]: PnL and portfolio details
        """
        try:
            path = self._get_trading_info_path("pnl")
            logger.debug("Getting PnL")
            result = self._make_request("GET", path)

            if "error" in result:
                logger.error(f"Failed to get PnL: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting PnL: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting PnL: {str(e)}"}

    # =====================
    # Market Data
    # =====================

    def search_instruments(self, search_term: str = None, page_size: int = 10, page_number: int = 1) -> Dict[str, Any]:
        """
        Search for tradeable instruments.

        Endpoint: GET /api/v1/market-data/search

        Args:
            search_term: Search text (e.g., "Apple", "BTC", "AAPL")
            page_size: Number of results per page
            page_number: Page number for pagination

        Returns:
            Dict[str, Any]: Search results with items array containing instrument details
        """
        try:
            params = {}

            if search_term:
                params["searchText"] = search_term

            if page_size:
                params["pageSize"] = page_size

            if page_number:
                params["pageNumber"] = page_number

            logger.debug(f"Searching instruments with params: {params}")
            result = self._make_request("GET", "/api/v1/market-data/search", params=params)

            if "error" in result:
                logger.error(f"Failed to search instruments: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error searching instruments: {type(e).__name__}", exc_info=True)
            return {"error": f"Error searching instruments: {str(e)}"}

    def get_instrument_by_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Resolve a ticker symbol to an eToro instrument ID.

        Endpoint: GET /api/v1/market-data/search?internalSymbolFull={symbol}

        Args:
            symbol: Ticker symbol (e.g., "AAPL", "BTC", "EURUSD")

        Returns:
            Dict[str, Any]: Instrument details with instrumentId
        """
        try:
            params = {"internalSymbolFull": symbol}

            logger.debug(f"Resolving symbol: {symbol}")
            result = self._make_request("GET", "/api/v1/market-data/search", params=params)

            if "error" in result:
                logger.error(f"Failed to resolve symbol: {result['error']}")
                return result

            # Find exact match
            items = result.get("items", [])
            for item in items:
                if item.get("internalSymbolFull", "").upper() == symbol.upper():
                    return item

            # Return first result if no exact match
            if items:
                return items[0]

            return {"error": f"Instrument not found for symbol: {symbol}"}

        except Exception as e:
            logger.error(f"Error resolving symbol: {type(e).__name__}", exc_info=True)
            return {"error": f"Error resolving symbol: {str(e)}"}

    def get_instrument_metadata(self, instrument_ids: Union[int, List[int]]) -> Dict[str, Any]:
        """
        Get metadata for instruments including display names, exchange IDs, and classification.

        Endpoint: GET /api/v1/market-data/instruments?instrumentIds={ids}

        Args:
            instrument_ids: Single instrument ID or list of instrument IDs

        Returns:
            Dict[str, Any]: Instrument metadata with instrumentDisplayDatas array
        """
        try:
            if isinstance(instrument_ids, int):
                id_list = [instrument_ids]
            elif isinstance(instrument_ids, list):
                id_list = instrument_ids
            else:
                return {"error": "instrument_ids must be an integer or list of integers"}

            for inst_id in id_list:
                if not isinstance(inst_id, int) or inst_id <= 0:
                    return {"error": "All instrument IDs must be positive integers"}

            params = {"instrumentIds": ",".join(str(i) for i in id_list)}

            logger.debug(f"Getting metadata for instruments: {params}")
            result = self._make_request("GET", "/api/v1/market-data/instruments", params=params)

            if "error" in result:
                logger.error(f"Failed to get instrument metadata: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting instrument metadata: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting instrument metadata: {str(e)}"}

    def get_current_rates(self, instrument_ids: Union[int, List[int]]) -> Dict[str, Any]:
        """
        Get current real-time bid/ask prices for instruments.

        Endpoint: GET /api/v1/market-data/instruments/rates?instrumentIds={ids}

        Args:
            instrument_ids: Single instrument ID or list of instrument IDs (max 100)

        Returns:
            Dict[str, Any]: Current rates with bid/ask prices
        """
        try:
            if isinstance(instrument_ids, int):
                id_list = [instrument_ids]
            elif isinstance(instrument_ids, list):
                id_list = instrument_ids
            else:
                return {"error": "instrument_ids must be an integer or list of integers"}

            for inst_id in id_list:
                if not isinstance(inst_id, int) or inst_id <= 0:
                    return {"error": "All instrument IDs must be positive integers"}

            if len(id_list) > 100:
                return {"error": "Maximum 100 instrument IDs per request"}

            ids_param = ",".join(str(i) for i in id_list)

            logger.debug(f"Getting current rates for instruments: {ids_param}")
            result = self._make_request("GET", "/api/v1/market-data/instruments/rates", params={"instrumentIds": ids_param})

            if "error" in result:
                logger.error(f"Failed to get current rates: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting current rates: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting current rates: {str(e)}"}

    # =====================
    # Trading Execution
    # =====================

    def create_position(
        self,
        instrument_id: int,
        is_buy: bool,
        amount: float,
        leverage: int = 1,
        stop_loss_rate: Optional[float] = None,
        take_profit_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a new trading position (market order by amount).

        Endpoint:
          Demo: POST /api/v1/trading/execution/demo/market-open-orders/by-amount
          Real: POST /api/v1/trading/execution/market-open-orders/by-amount

        Args:
            instrument_id: Instrument ID (integer)
            is_buy: True for long (BUY), False for short (SELL)
            amount: Investment amount in account currency
            leverage: Leverage multiplier (e.g., 1, 2, 5, 10, 20)
            stop_loss_rate: Stop loss price level (optional)
            take_profit_rate: Take profit price level (optional)

        Returns:
            Dict[str, Any]: Order result with orderForOpen and token
        """
        try:
            if not isinstance(instrument_id, int) or instrument_id <= 0:
                return {"error": "instrument_id must be a positive integer"}

            if amount <= 0:
                return {"error": "amount must be greater than 0"}

            if leverage < 1:
                return {"error": "leverage must be at least 1"}

            payload = {
                "InstrumentID": instrument_id,
                "IsBuy": is_buy,
                "Amount": amount,
                "Leverage": leverage
            }

            if stop_loss_rate is not None:
                payload["StopLossRate"] = stop_loss_rate

            if take_profit_rate is not None:
                payload["TakeProfitRate"] = take_profit_rate

            path = self._get_trading_execution_path("market-open-orders/by-amount")
            logger.info(f"Creating position: {payload}")
            result = self._make_request("POST", path, json=payload)

            if "error" in result:
                logger.error(f"Failed to create position: {result['error']}")
            else:
                logger.info(f"Position created successfully: {result}")

            return result

        except Exception as e:
            logger.error(f"Error creating position: {type(e).__name__}", exc_info=True)
            return {"error": f"Error creating position: {str(e)}"}

    def create_position_by_units(
        self,
        instrument_id: int,
        is_buy: bool,
        units: float,
        leverage: int = 1,
        stop_loss_rate: Optional[float] = None,
        take_profit_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a new trading position by specifying units.

        Endpoint:
          Demo: POST /api/v1/trading/execution/demo/market-open-orders/by-units
          Real: POST /api/v1/trading/execution/market-open-orders/by-units

        Args:
            instrument_id: Instrument ID (integer)
            is_buy: True for long (BUY), False for short (SELL)
            units: Number of units to trade
            leverage: Leverage multiplier
            stop_loss_rate: Stop loss price level (optional)
            take_profit_rate: Take profit price level (optional)

        Returns:
            Dict[str, Any]: Order result with orderForOpen and token
        """
        try:
            if not isinstance(instrument_id, int) or instrument_id <= 0:
                return {"error": "instrument_id must be a positive integer"}

            if units <= 0:
                return {"error": "units must be greater than 0"}

            if leverage < 1:
                return {"error": "leverage must be at least 1"}

            payload = {
                "InstrumentID": instrument_id,
                "IsBuy": is_buy,
                "Units": units,
                "Leverage": leverage
            }

            if stop_loss_rate is not None:
                payload["StopLossRate"] = stop_loss_rate

            if take_profit_rate is not None:
                payload["TakeProfitRate"] = take_profit_rate

            path = self._get_trading_execution_path("market-open-orders/by-units")
            logger.info(f"Creating position by units: {payload}")
            result = self._make_request("POST", path, json=payload)

            if "error" in result:
                logger.error(f"Failed to create position: {result['error']}")
            else:
                logger.info(f"Position created successfully: {result}")

            return result

        except Exception as e:
            logger.error(f"Error creating position: {type(e).__name__}", exc_info=True)
            return {"error": f"Error creating position: {str(e)}"}

    def close_position(self, position_id: str, instrument_id: int, units_to_deduct: Optional[float] = None) -> Dict[str, Any]:
        """
        Close an open trading position (full or partial).

        Endpoint:
          Demo: POST /api/v1/trading/execution/demo/market-close-orders/positions/{positionId}
          Real: POST /api/v1/trading/execution/market-close-orders/positions/{positionId}

        Args:
            position_id: Position ID to close
            instrument_id: Instrument ID of the position
            units_to_deduct: Units to close (null = close entire position)

        Returns:
            Dict[str, Any]: Order result with orderForClose and token
        """
        try:
            if not position_id:
                return {"error": "position_id cannot be empty"}

            if not isinstance(instrument_id, int) or instrument_id <= 0:
                return {"error": "instrument_id must be a positive integer"}

            payload = {
                "InstrumentId": instrument_id,
                "UnitsToDeduct": units_to_deduct
            }

            path = self._get_trading_execution_path(f"market-close-orders/positions/{position_id}")
            logger.info(f"Closing position: {position_id}")
            result = self._make_request("POST", path, json=payload)

            if "error" in result:
                logger.error(f"Failed to close position: {result['error']}")
            else:
                logger.info(f"Position closed successfully")

            return result

        except Exception as e:
            logger.error(f"Error closing position: {type(e).__name__}", exc_info=True)
            return {"error": f"Error closing position: {str(e)}"}

    def get_order_info(self, order_id: str) -> Dict[str, Any]:
        """
        Get order information and position details.

        Endpoint:
          Demo: GET /api/v1/trading/info/demo/orders/{orderId}
          Real: GET /api/v1/trading/info/orders/{orderId}

        Args:
            order_id: Order ID to look up

        Returns:
            Dict[str, Any]: Order details with position information
        """
        try:
            if not order_id:
                return {"error": "order_id cannot be empty"}

            path = self._get_trading_info_path(f"orders/{order_id}")
            logger.debug(f"Getting order info: {order_id}")
            result = self._make_request("GET", path)

            if "error" in result:
                logger.error(f"Failed to get order info: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting order info: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting order info: {str(e)}"}
