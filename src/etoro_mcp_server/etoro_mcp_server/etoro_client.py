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

    def _get_headers(self, include_content_type: bool = True) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        headers = {
            "x-request-id": self._generate_request_id()
        }

        if include_content_type:
            headers["Content-Type"] = "application/json"

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
        # Only include Content-Type header when there is a JSON body
        has_body = "json" in kwargs or "data" in kwargs
        headers = self._get_headers(include_content_type=has_body)

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

    def get_historical_candles(
        self,
        instrument_id: int,
        interval: str = "OneDay",
        candles_count: int = 100,
        direction: str = "desc"
    ) -> Dict[str, Any]:
        """
        Get historical OHLCV candle data for an instrument.

        Endpoint: GET /api/v1/market-data/instruments/{id}/history/candles/{direction}/{interval}/{candlesCount}

        Args:
            instrument_id: Instrument ID
            interval: Candle interval (OneMinute, FiveMinutes, TenMinutes, FifteenMinutes,
                       ThirtyMinutes, OneHour, FourHours, OneDay, OneWeek)
            candles_count: Number of candles to retrieve (max 1000)
            direction: Sort order ("asc" or "desc")

        Returns:
            Dict[str, Any]: Candle data with interval and candles array
        """
        try:
            if not isinstance(instrument_id, int) or instrument_id <= 0:
                return {"error": "instrument_id must be a positive integer"}

            valid_intervals = [
                "OneMinute", "FiveMinutes", "TenMinutes", "FifteenMinutes",
                "ThirtyMinutes", "OneHour", "FourHours", "OneDay", "OneWeek"
            ]
            if interval not in valid_intervals:
                return {"error": f"interval must be one of: {', '.join(valid_intervals)}"}

            if direction not in ("asc", "desc"):
                return {"error": "direction must be 'asc' or 'desc'"}

            if candles_count < 1 or candles_count > 1000:
                return {"error": "candles_count must be between 1 and 1000"}

            path = f"/api/v1/market-data/instruments/{instrument_id}/history/candles/{direction}/{interval}/{candles_count}"
            logger.debug(f"Getting historical candles for instrument {instrument_id}")
            result = self._make_request("GET", path)

            if "error" in result:
                logger.error(f"Failed to get historical candles: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting historical candles: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting historical candles: {str(e)}"}

    def get_closing_prices(self) -> Dict[str, Any]:
        """
        Get historical closing prices for all instruments.

        Endpoint: GET /api/v1/market-data/instruments/closing-prices

        Returns:
            Dict[str, Any]: Closing prices data
        """
        try:
            logger.debug("Getting closing prices")
            result = self._make_request("GET", "/api/v1/market-data/instruments/history/closing-price")

            if "error" in result:
                logger.error(f"Failed to get closing prices: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting closing prices: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting closing prices: {str(e)}"}

    def get_instrument_types(self) -> Dict[str, Any]:
        """
        Get available instrument types (asset classes) like stocks, ETFs, commodities, etc.

        Endpoint: GET /api/v1/market-data/instrument-types

        Returns:
            Dict[str, Any]: Available instrument types
        """
        try:
            logger.debug("Getting instrument types")
            result = self._make_request("GET", "/api/v1/market-data/instrument-types")

            if "error" in result:
                logger.error(f"Failed to get instrument types: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting instrument types: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting instrument types: {str(e)}"}

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
                "AmountInUnits": units,
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

    def place_limit_order(
        self,
        instrument_id: int,
        is_buy: bool,
        leverage: int,
        rate: float,
        amount: Optional[float] = None,
        amount_in_units: Optional[float] = None,
        stop_loss_rate: Optional[float] = None,
        take_profit_rate: Optional[float] = None,
        is_tsl_enabled: bool = False,
        is_no_stop_loss: bool = False,
        is_no_take_profit: bool = False
    ) -> Dict[str, Any]:
        """
        Place a Market-if-touched (limit) order to open a position at a target price.

        Endpoint:
          Demo: POST /api/v1/trading/execution/demo/limit-orders
          Real: POST /api/v1/trading/execution/limit-orders

        Args:
            instrument_id: Instrument ID
            is_buy: True for BUY, False for SELL
            leverage: Leverage multiplier
            rate: Trigger price at which the market order will be sent
            amount: Trade amount in USD (mutually exclusive with amount_in_units)
            amount_in_units: Number of units (mutually exclusive with amount)
            stop_loss_rate: Stop loss price level
            take_profit_rate: Take profit price level
            is_tsl_enabled: Enable trailing stop loss
            is_no_stop_loss: Disable stop loss
            is_no_take_profit: Disable take profit

        Returns:
            Dict[str, Any]: Order result with token
        """
        try:
            if not isinstance(instrument_id, int) or instrument_id <= 0:
                return {"error": "instrument_id must be a positive integer"}

            if amount is not None and amount_in_units is not None:
                return {"error": "Provide either 'amount' or 'amount_in_units', not both"}

            if amount is None and amount_in_units is None:
                return {"error": "Must provide either 'amount' or 'amount_in_units'"}

            if leverage < 1:
                return {"error": "leverage must be at least 1"}

            payload = {
                "InstrumentID": instrument_id,
                "IsBuy": is_buy,
                "Leverage": leverage,
                "Rate": rate,
                "IsTslEnabled": is_tsl_enabled,
                "IsNoStopLoss": is_no_stop_loss,
                "IsNoTakeProfit": is_no_take_profit,
            }

            if amount is not None:
                payload["Amount"] = amount
            if amount_in_units is not None:
                payload["AmountInUnits"] = amount_in_units
            if stop_loss_rate is not None:
                payload["StopLossRate"] = stop_loss_rate
            if take_profit_rate is not None:
                payload["TakeProfitRate"] = take_profit_rate

            path = self._get_trading_execution_path("limit-orders")
            logger.info(f"Placing limit order: {payload}")
            result = self._make_request("POST", path, json=payload)

            if "error" in result:
                logger.error(f"Failed to place limit order: {result['error']}")
            else:
                logger.info(f"Limit order placed successfully: {result}")

            return result

        except Exception as e:
            logger.error(f"Error placing limit order: {type(e).__name__}", exc_info=True)
            return {"error": f"Error placing limit order: {str(e)}"}

    def cancel_limit_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a Market-if-touched (limit) order before execution.

        Endpoint:
          Demo: DELETE /api/v1/trading/execution/demo/limit-orders/{orderId}
          Real: DELETE /api/v1/trading/execution/limit-orders/{orderId}
        """
        try:
            if not order_id:
                return {"error": "order_id cannot be empty"}

            path = self._get_trading_execution_path(f"limit-orders/{order_id}")
            logger.info(f"Cancelling limit order: {order_id}")
            result = self._make_request("DELETE", path)

            if "error" in result:
                logger.error(f"Failed to cancel limit order: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error cancelling limit order: {type(e).__name__}", exc_info=True)
            return {"error": f"Error cancelling limit order: {str(e)}"}

    def cancel_open_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a pending market order for open before execution.

        Endpoint:
          Demo: DELETE /api/v1/trading/execution/demo/market-open-orders/{orderId}
          Real: DELETE /api/v1/trading/execution/market-open-orders/{orderId}
        """
        try:
            if not order_id:
                return {"error": "order_id cannot be empty"}

            path = self._get_trading_execution_path(f"market-open-orders/{order_id}")
            logger.info(f"Cancelling open order: {order_id}")
            result = self._make_request("DELETE", path)

            if "error" in result:
                logger.error(f"Failed to cancel open order: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error cancelling open order: {type(e).__name__}", exc_info=True)
            return {"error": f"Error cancelling open order: {str(e)}"}

    def cancel_close_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a pending market order for close before execution.

        Endpoint:
          Demo: DELETE /api/v1/trading/execution/demo/market-close-orders/{orderId}
          Real: DELETE /api/v1/trading/execution/market-close-orders/{orderId}
        """
        try:
            if not order_id:
                return {"error": "order_id cannot be empty"}

            path = self._get_trading_execution_path(f"market-close-orders/{order_id}")
            logger.info(f"Cancelling close order: {order_id}")
            result = self._make_request("DELETE", path)

            if "error" in result:
                logger.error(f"Failed to cancel close order: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error cancelling close order: {type(e).__name__}", exc_info=True)
            return {"error": f"Error cancelling close order: {str(e)}"}

    # =====================
    # Watchlists
    # =====================

    def get_watchlists(self) -> Dict[str, Any]:
        """
        Get all watchlists for the authenticated user.

        Endpoint: GET /api/v1/watchlists
        """
        try:
            logger.debug("Getting watchlists")
            result = self._make_request("GET", "/api/v1/watchlists")

            if "error" in result:
                logger.error(f"Failed to get watchlists: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting watchlists: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting watchlists: {str(e)}"}

    def create_watchlist(self, name: str) -> Dict[str, Any]:
        """
        Create a new watchlist.

        Endpoint: POST /api/v1/watchlists?name={name}
        """
        try:
            if not name or not name.strip():
                return {"error": "name cannot be empty"}

            logger.info(f"Creating watchlist: {name}")
            result = self._make_request("POST", "/api/v1/watchlists", params={"name": name})

            if "error" in result:
                logger.error(f"Failed to create watchlist: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error creating watchlist: {type(e).__name__}", exc_info=True)
            return {"error": f"Error creating watchlist: {str(e)}"}

    def delete_watchlist(self, watchlist_id: str) -> Dict[str, Any]:
        """
        Delete a watchlist.

        Endpoint: DELETE /api/v1/watchlists/{watchlistId}
        """
        try:
            if not watchlist_id:
                return {"error": "watchlist_id cannot be empty"}

            logger.info(f"Deleting watchlist: {watchlist_id}")
            result = self._make_request("DELETE", f"/api/v1/watchlists/{watchlist_id}")

            if "error" in result:
                logger.error(f"Failed to delete watchlist: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error deleting watchlist: {type(e).__name__}", exc_info=True)
            return {"error": f"Error deleting watchlist: {str(e)}"}

    def add_watchlist_items(self, watchlist_id: str, instrument_ids: List[int]) -> Dict[str, Any]:
        """
        Add instruments to a watchlist.

        Endpoint: POST /api/v1/watchlists/{watchlistId}/items
        Body: [{"ItemId": 1001, "ItemType": "Instrument"}, ...]
        """
        try:
            if not watchlist_id:
                return {"error": "watchlist_id cannot be empty"}

            if not instrument_ids:
                return {"error": "instrument_ids cannot be empty"}

            items = [{"ItemId": iid, "ItemType": "Instrument"} for iid in instrument_ids]
            logger.info(f"Adding items to watchlist {watchlist_id}: {instrument_ids}")
            result = self._make_request("POST", f"/api/v1/watchlists/{watchlist_id}/items", json=items)

            if "error" in result:
                logger.error(f"Failed to add watchlist items: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error adding watchlist items: {type(e).__name__}", exc_info=True)
            return {"error": f"Error adding watchlist items: {str(e)}"}

    def remove_watchlist_items(self, watchlist_id: str, instrument_ids: List[int]) -> Dict[str, Any]:
        """
        Remove instruments from a watchlist.

        Endpoint: DELETE /api/v1/watchlists/{watchlistId}/items
        Body: [{"ItemId": 1001, "ItemType": "Instrument"}, ...]
        """
        try:
            if not watchlist_id:
                return {"error": "watchlist_id cannot be empty"}

            if not instrument_ids:
                return {"error": "instrument_ids cannot be empty"}

            items = [{"ItemId": iid, "ItemType": "Instrument"} for iid in instrument_ids]
            logger.info(f"Removing items from watchlist {watchlist_id}: {instrument_ids}")
            result = self._make_request("DELETE", f"/api/v1/watchlists/{watchlist_id}/items", json=items)

            if "error" in result:
                logger.error(f"Failed to remove watchlist items: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error removing watchlist items: {type(e).__name__}", exc_info=True)
            return {"error": f"Error removing watchlist items: {str(e)}"}

    def rename_watchlist(self, watchlist_id: str, new_name: str) -> Dict[str, Any]:
        """
        Rename a watchlist.

        Endpoint: PUT /api/v1/watchlists/{watchlistId}?newName={newName}
        """
        try:
            if not watchlist_id:
                return {"error": "watchlist_id cannot be empty"}

            if not new_name or not new_name.strip():
                return {"error": "new_name cannot be empty"}

            logger.info(f"Renaming watchlist {watchlist_id} to: {new_name}")
            result = self._make_request("PUT", f"/api/v1/watchlists/{watchlist_id}", params={"newName": new_name})

            if "error" in result:
                logger.error(f"Failed to rename watchlist: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error renaming watchlist: {type(e).__name__}", exc_info=True)
            return {"error": f"Error renaming watchlist: {str(e)}"}

    # =====================
    # Users Info
    # =====================

    def get_user_profile(self, username: str) -> Dict[str, Any]:
        """
        Get comprehensive user profile data.

        Endpoint: GET /api/v1/user-info/people?usernames={username}
        """
        try:
            if not username or not username.strip():
                return {"error": "username cannot be empty"}

            logger.debug(f"Getting user profile: {username}")
            result = self._make_request("GET", "/api/v1/user-info/people", params={"usernames": username})

            if "error" in result:
                logger.error(f"Failed to get user profile: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting user profile: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting user profile: {str(e)}"}

    def get_user_performance(self, username: str) -> Dict[str, Any]:
        """
        Get historical performance metrics for a user.

        Endpoint: GET /api/v1/user-info/people/{username}/gain
        """
        try:
            if not username or not username.strip():
                return {"error": "username cannot be empty"}

            logger.debug(f"Getting user performance: {username}")
            result = self._make_request("GET", f"/api/v1/user-info/people/{username}/gain")

            if "error" in result:
                logger.error(f"Failed to get user performance: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting user performance: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting user performance: {str(e)}"}

    def get_user_trade_info(self, username: str, period: str = "CurrMonth") -> Dict[str, Any]:
        """
        Get trade info for a specific user.

        Endpoint: GET /api/v1/user-info/people/{username}/tradeinfo?period={period}

        Args:
            username: eToro username
            period: Time period (CurrMonth, CurrQuarter, CurrYear, LastYear,
                     LastTwoYears, OneMonthAgo, TwoMonthsAgo, ThreeMonthsAgo,
                     SixMonthsAgo, OneYearAgo)
        """
        try:
            if not username or not username.strip():
                return {"error": "username cannot be empty"}

            valid_periods = [
                "CurrMonth", "CurrQuarter", "CurrYear", "LastYear",
                "LastTwoYears", "OneMonthAgo", "TwoMonthsAgo",
                "ThreeMonthsAgo", "SixMonthsAgo", "OneYearAgo"
            ]
            if period not in valid_periods:
                return {"error": f"period must be one of: {', '.join(valid_periods)}"}

            logger.debug(f"Getting trade info for {username}, period={period}")
            result = self._make_request(
                "GET",
                f"/api/v1/user-info/people/{username}/tradeinfo",
                params={"period": period}
            )

            if "error" in result:
                logger.error(f"Failed to get user trade info: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting user trade info: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting user trade info: {str(e)}"}

    def search_users(
        self,
        period: str = "CurrMonth",
        gain_min: Optional[int] = None,
        gain_max: Optional[int] = None,
        risk_score_min: Optional[int] = None,
        risk_score_max: Optional[int] = None,
        popular_investor: Optional[bool] = None,
        page_size: int = 10,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Search and discover users with filtering by performance metrics.

        Endpoint: GET /api/v1/user-info/people/search
        """
        try:
            params: Dict[str, Any] = {
                "period": period,
                "pageSize": page_size,
                "page": page,
            }

            if gain_min is not None:
                params["gainMin"] = gain_min
            if gain_max is not None:
                params["gainMax"] = gain_max
            if risk_score_min is not None:
                params["maxDailyRiskScoreMin"] = risk_score_min
            if risk_score_max is not None:
                params["maxDailyRiskScoreMax"] = risk_score_max
            if popular_investor is not None:
                params["popularInvestor"] = popular_investor

            logger.debug(f"Searching users with params: {params}")
            result = self._make_request("GET", "/api/v1/user-info/people/search", params=params)

            if "error" in result:
                logger.error(f"Failed to search users: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error searching users: {type(e).__name__}", exc_info=True)
            return {"error": f"Error searching users: {str(e)}"}

    # =====================
    # Feeds
    # =====================

    def get_user_feed(self, user_id: str, take: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Get feed posts for a specific user.

        Endpoint: GET /api/v1/feeds/user/{userId}
        """
        try:
            if not user_id:
                return {"error": "user_id cannot be empty"}

            params = {"take": take, "offset": offset}
            logger.debug(f"Getting user feed: {user_id}")
            result = self._make_request("GET", f"/api/v1/feeds/user/{user_id}", params=params)

            if "error" in result:
                logger.error(f"Failed to get user feed: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting user feed: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting user feed: {str(e)}"}

    def get_instrument_feed(self, market_id: str, take: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Get feed posts for a specific instrument/market.

        Endpoint: GET /api/v1/feeds/instrument/{marketId}
        """
        try:
            if not market_id:
                return {"error": "market_id cannot be empty"}

            params = {"take": take, "offset": offset}
            logger.debug(f"Getting instrument feed: {market_id}")
            result = self._make_request("GET", f"/api/v1/feeds/instrument/{market_id}", params=params)

            if "error" in result:
                logger.error(f"Failed to get instrument feed: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error getting instrument feed: {type(e).__name__}", exc_info=True)
            return {"error": f"Error getting instrument feed: {str(e)}"}

    def create_post(
        self,
        owner: int,
        message: str,
        tags: Optional[Dict[str, Any]] = None,
        mentions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new discussion post.

        Endpoint: POST /api/v1/feeds/post
        """
        try:
            if not message or not message.strip():
                return {"error": "message cannot be empty"}

            payload: Dict[str, Any] = {
                "owner": owner,
                "message": message,
            }

            if tags is not None:
                payload["tags"] = tags
            if mentions is not None:
                payload["mentions"] = mentions

            logger.info(f"Creating post for owner {owner}")
            result = self._make_request("POST", "/api/v1/feeds/post", json=payload)

            if "error" in result:
                logger.error(f"Failed to create post: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error creating post: {type(e).__name__}", exc_info=True)
            return {"error": f"Error creating post: {str(e)}"}

    def create_comment(self, post_id: str, owner: int, message: str) -> Dict[str, Any]:
        """
        Create a comment on a post.

        Endpoint: POST /api/v1/reactions/{postId}/comment
        """
        try:
            if not post_id:
                return {"error": "post_id cannot be empty"}

            if not message or not message.strip():
                return {"error": "message cannot be empty"}

            payload = {
                "owner": owner,
                "message": message,
            }

            logger.info(f"Creating comment on post {post_id}")
            result = self._make_request("POST", f"/api/v1/reactions/{post_id}/comment", json=payload)

            if "error" in result:
                logger.error(f"Failed to create comment: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Error creating comment: {type(e).__name__}", exc_info=True)
            return {"error": f"Error creating comment: {str(e)}"}
