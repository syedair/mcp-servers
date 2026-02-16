"""Tests for market data tools: search, resolve, metadata, rates."""


def test_search_instruments(etoro_client):
    result = etoro_client.search_instruments(search_term="Apple")
    assert "error" not in result, f"API error: {result}"
    assert "items" in result
    assert len(result["items"]) > 0
    first = result["items"][0]
    assert "instrumentId" in first or "InstrumentId" in first


def test_resolve_symbol(etoro_client):
    result = etoro_client.get_instrument_by_symbol("AAPL")
    assert "error" not in result, f"API error: {result}"
    # AAPL should resolve to instrumentId 1001
    iid = result.get("instrumentId") or result.get("InstrumentId")
    assert iid == 1001, f"Expected instrumentId 1001, got {iid}"


def test_get_instrument_metadata(etoro_client):
    result = etoro_client.get_instrument_metadata(1001)
    assert "error" not in result, f"API error: {result}"
    assert "instrumentDisplayDatas" in result
    data = result["instrumentDisplayDatas"]
    assert len(data) > 0
    first = data[0]
    display_name = (
        first.get("instrumentDisplayName")
        or first.get("displayName")
        or first.get("DisplayName")
    )
    assert display_name is not None, f"displayName missing from metadata keys: {list(first.keys())}"


def test_get_current_rates(etoro_client):
    result = etoro_client.get_current_rates(1001)
    assert "error" not in result, f"API error: {result}"
    # Should contain rate data with bid/ask
    assert result, "Empty rates response"


def test_get_historical_candles(etoro_client):
    result = etoro_client.get_historical_candles(1001, interval="OneDay", candles_count=10)
    assert "error" not in result, f"API error: {result}"
    assert "candles" in result or "Candles" in result, f"Missing candles in: {list(result.keys())}"


def test_get_closing_prices(etoro_client):
    result = etoro_client.get_closing_prices()
    assert "error" not in result, f"API error: {result}"
    assert result, "Empty closing prices response"


def test_get_instrument_types(etoro_client):
    result = etoro_client.get_instrument_types()
    assert "error" not in result, f"API error: {result}"
    assert result, "Empty instrument types response"
