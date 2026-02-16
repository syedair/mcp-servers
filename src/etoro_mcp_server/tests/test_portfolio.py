"""Tests for portfolio tools: account info, portfolio, positions."""


def test_get_account_info(etoro_client):
    result = etoro_client.get_account_info()
    assert "error" not in result, f"API error: {result}"
    assert "credit" in result, f"Missing 'credit' field in: {list(result.keys())}"


def test_get_portfolio(etoro_client):
    result = etoro_client.get_portfolio()
    assert "error" not in result, f"API error: {result}"
    assert "clientPortfolio" in result
    portfolio = result["clientPortfolio"]
    # Should have standard portfolio fields
    assert "credit" in portfolio or "Credit" in portfolio


def test_get_positions(etoro_client):
    result = etoro_client.get_positions()
    assert "error" not in result, f"API error: {result}"
    assert "positions" in result
    assert isinstance(result["positions"], list)
