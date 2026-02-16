"""Tests for feed tools: user feed, instrument feed, create post, create comment.

Write tests (create_post, create_comment) are gated behind @pytest.mark.social.
"""

import pytest

# AAPL instrument ID / market ID
AAPL_MARKET_ID = "1001"


def test_get_instrument_feed(etoro_client):
    result = etoro_client.get_instrument_feed(AAPL_MARKET_ID, take=5)
    assert "error" not in result, f"API error: {result}"
    assert result, "Empty instrument feed response"


def test_get_user_feed(etoro_client):
    # Use a numeric user ID; search for a known user first
    profile = etoro_client.get_user_profile("Yonigoldberg1")
    if "error" in profile:
        pytest.skip(f"Could not get user profile: {profile}")

    # Extract user ID from profile response
    users = profile if isinstance(profile, list) else profile.get("users", [profile])
    if not users:
        pytest.skip("No user data in profile response")

    user = users[0] if isinstance(users, list) else users
    user_id = (
        user.get("realCID")
        or user.get("RealCID")
        or user.get("cid")
        or user.get("CID")
        or user.get("userId")
    )
    if not user_id:
        pytest.skip(f"Could not extract user ID from profile: {list(user.keys())}")

    result = etoro_client.get_user_feed(str(user_id), take=5)
    assert "error" not in result, f"API error: {result}"
    assert result, "Empty user feed response"


@pytest.mark.social
def test_create_post(etoro_client):
    """Create a test discussion post. Requires social marker."""
    # This requires a valid owner ID (the authenticated user's CID)
    # We'll get it from account info / portfolio
    portfolio = etoro_client.get_portfolio()
    if "error" in portfolio:
        pytest.skip(f"Could not get portfolio: {portfolio}")

    # Try to extract the user's CID
    client_portfolio = portfolio.get("clientPortfolio", portfolio)
    cid = client_portfolio.get("cid") or client_portfolio.get("CID")
    if not cid:
        pytest.skip("Could not determine user CID from portfolio")

    result = etoro_client.create_post(
        owner=int(cid),
        message="Test post from MCP integration tests - please ignore"
    )
    assert "error" not in result, f"API error: {result}"


@pytest.mark.social
def test_create_comment(etoro_client):
    """Create a test comment. Requires social marker and a valid post ID."""
    # Get an instrument feed to find a post ID
    feed = etoro_client.get_instrument_feed(AAPL_MARKET_ID, take=1)
    if "error" in feed:
        pytest.skip(f"Could not get feed: {feed}")

    posts = feed.get("discussions") or feed.get("Discussions") or feed.get("items") or []
    if not posts:
        pytest.skip("No posts found in instrument feed")

    post = posts[0]
    post_id = post.get("postId") or post.get("PostId") or post.get("id") or post.get("Id")
    if not post_id:
        pytest.skip(f"Could not extract post ID from: {list(post.keys())}")

    # Get owner CID
    portfolio = etoro_client.get_portfolio()
    client_portfolio = portfolio.get("clientPortfolio", portfolio)
    cid = client_portfolio.get("cid") or client_portfolio.get("CID")
    if not cid:
        pytest.skip("Could not determine user CID")

    result = etoro_client.create_comment(
        post_id=str(post_id),
        owner=int(cid),
        message="Test comment from MCP integration tests"
    )
    assert "error" not in result, f"API error: {result}"
