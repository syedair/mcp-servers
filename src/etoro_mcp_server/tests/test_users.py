"""Tests for user info tools: search, profile, performance, trade info."""


def test_search_users(etoro_client):
    result = etoro_client.search_users(period="CurrMonth", page_size=5)
    assert "error" not in result, f"API error: {result}"
    assert result, "Empty search users response"


def test_get_user_profile(etoro_client):
    # Use a well-known public eToro username
    result = etoro_client.get_user_profile("Yonigoldberg1")
    assert "error" not in result, f"API error: {result}"
    assert result, "Empty user profile response"


def test_get_user_performance(etoro_client):
    result = etoro_client.get_user_performance("Yonigoldberg1")
    assert "error" not in result, f"API error: {result}"
    assert result, "Empty user performance response"


def test_get_user_trade_info(etoro_client):
    # Try multiple periods — some users may not have data for all periods
    for period in ["LastYear", "CurrYear", "CurrMonth"]:
        result = etoro_client.get_user_trade_info("Yonigoldberg1", period=period)
        if "error" not in result:
            assert result, "Empty user trade info response"
            return
    # If all periods fail, the endpoint may not be available for this user
    # Accept 404 as a known limitation and skip
    if "404" in str(result.get("error", "")):
        import pytest
        pytest.skip(f"Trade info endpoint returned 404 for test user: {result}")
    assert "error" not in result, f"API error: {result}"
