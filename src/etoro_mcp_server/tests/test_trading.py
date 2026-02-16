"""Tests for trading tools: create, get_order_info, close, limit orders, PnL.

Uses BTC (instrumentId=100000) — crypto markets are always open.
Tests are ordered: create → get_order_info → close.
"""

import pytest

# BTC instrument ID on eToro
BTC_INSTRUMENT_ID = 100000


def test_get_pnl(etoro_client):
    """Get account PnL — wrapper around existing client method."""
    result = etoro_client.get_pnl()
    assert "error" not in result, f"API error: {result}"
    assert result, "Empty PnL response"


@pytest.mark.trading
class TestLimitOrderLifecycle:
    """Place a limit order at an impossible price, then cancel it."""

    _order_token = None

    def test_01_place_limit_order(self, etoro_client):
        """Place a BTC limit BUY order at $1 (will never fill)."""
        result = etoro_client.place_limit_order(
            instrument_id=BTC_INSTRUMENT_ID,
            is_buy=True,
            leverage=1,
            rate=1.0,  # impossibly low price
            amount=50,
            stop_loss_rate=0.5,
            take_profit_rate=2.0,
        )
        assert "error" not in result, f"API error: {result}"
        token = result.get("token") or result.get("Token")
        assert token is not None, f"No token in response: {result}"
        TestLimitOrderLifecycle._order_token = str(token)

    def test_02_cancel_limit_order(self, etoro_client):
        """Cancel the limit order placed above.

        We need the orderId from the portfolio's pending orders.
        """
        # Find the pending limit order from portfolio
        portfolio = etoro_client.get_portfolio()
        if "error" in portfolio:
            pytest.skip(f"Could not get portfolio: {portfolio}")

        client_portfolio = portfolio.get("clientPortfolio", portfolio)
        orders = client_portfolio.get("orders", [])

        # Find a pending limit order for BTC
        order_id = None
        for order in orders:
            iid = order.get("instrumentID") or order.get("InstrumentID") or order.get("instrumentId")
            if iid == BTC_INSTRUMENT_ID:
                oid = order.get("orderID") or order.get("OrderID") or order.get("orderId")
                if oid:
                    order_id = str(oid)
                    break

        if not order_id:
            pytest.skip("No pending limit order found for BTC in portfolio")

        result = etoro_client.cancel_limit_order(order_id)
        assert "error" not in result, f"API error: {result}"


@pytest.mark.trading
class TestTradingLifecycle:
    """Ordered test class: open position → check order → close position."""

    _order_id = None
    _position_id = None

    def test_01_create_position_by_amount(self, etoro_client):
        """Open a BTC position by dollar amount ($50)."""
        result = etoro_client.create_position(
            instrument_id=BTC_INSTRUMENT_ID,
            is_buy=True,
            amount=50,
            leverage=1,
        )
        assert "error" not in result, f"API error: {result}"
        assert "orderForOpen" in result, f"Missing orderForOpen in: {list(result.keys())}"
        order = result["orderForOpen"]
        order_id = order.get("orderID") or order.get("OrderID") or order.get("orderId")
        assert order_id is not None, f"No orderID found in orderForOpen: {order}"
        TestTradingLifecycle._order_id = str(order_id)

    def test_02_get_order_info(self, etoro_client):
        """Look up the order from the previous test.

        Note: Market orders that execute instantly may return 404 from the
        orders endpoint. The test verifies the API call succeeds or returns
        a known 404 pattern, and tries to extract a position ID if available.
        """
        if not TestTradingLifecycle._order_id:
            pytest.skip("No order_id from previous test")
        result = etoro_client.get_order_info(TestTradingLifecycle._order_id)
        # A 404 "Order was not found" is acceptable for instantly-filled market orders
        if "error" in result:
            if "not found" in result.get("details", "").lower():
                pytest.skip(
                    f"Order {TestTradingLifecycle._order_id} not found (instantly filled market order)"
                )
            else:
                pytest.fail(f"Unexpected API error: {result}")
        # Extract position ID for the close test
        positions = result.get("positions") or result.get("Positions") or []
        if positions:
            pos = positions[0]
            pid = pos.get("positionID") or pos.get("PositionID") or pos.get("positionId")
            if pid:
                TestTradingLifecycle._position_id = str(pid)

    def test_03_close_position(self, etoro_client):
        """Close the position opened in test_01."""
        # If we didn't get position_id from order info, try fetching from positions
        if not TestTradingLifecycle._position_id:
            positions_result = etoro_client.get_positions()
            if "positions" in positions_result and positions_result["positions"]:
                for pos in positions_result["positions"]:
                    iid = pos.get("instrumentID") or pos.get("InstrumentID") or pos.get("instrumentId")
                    if iid == BTC_INSTRUMENT_ID:
                        pid = (
                            pos.get("positionID")
                            or pos.get("PositionID")
                            or pos.get("positionId")
                        )
                        if pid:
                            TestTradingLifecycle._position_id = str(pid)
                            break

        if not TestTradingLifecycle._position_id:
            pytest.skip("No position_id available to close")

        result = etoro_client.close_position(
            position_id=TestTradingLifecycle._position_id,
            instrument_id=BTC_INSTRUMENT_ID,
        )
        assert "error" not in result, f"API error: {result}"
        assert "orderForClose" in result, f"Missing orderForClose in: {list(result.keys())}"

    def test_04_create_position_by_units(self, etoro_client):
        """Open a BTC position by units (0.001 BTC), then close it."""
        result = etoro_client.create_position_by_units(
            instrument_id=BTC_INSTRUMENT_ID,
            is_buy=True,
            units=0.001,
            leverage=1,
        )
        assert "error" not in result, f"API error: {result}"
        assert "orderForOpen" in result, f"Missing orderForOpen in: {list(result.keys())}"

        # Clean up: close the position
        order = result["orderForOpen"]
        order_id = str(
            order.get("orderID") or order.get("OrderID") or order.get("orderId")
        )
        if order_id:
            order_info = etoro_client.get_order_info(order_id)
            positions = order_info.get("positions") or order_info.get("Positions") or []
            if positions:
                pos = positions[0]
                pid = str(
                    pos.get("positionID") or pos.get("PositionID") or pos.get("positionId")
                )
                if pid:
                    etoro_client.close_position(
                        position_id=pid, instrument_id=BTC_INSTRUMENT_ID
                    )
