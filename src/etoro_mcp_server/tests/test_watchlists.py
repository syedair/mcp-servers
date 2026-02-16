"""Tests for watchlist CRUD operations.

Ordered: create → add items → remove items → rename → delete.
"""

import time
import pytest

# AAPL and MSFT instrument IDs
AAPL_ID = 1001
MSFT_ID = 1002


class TestWatchlistLifecycle:
    """Full watchlist lifecycle test."""

    _watchlist_id = None

    def test_01_get_watchlists(self, etoro_client):
        """List existing watchlists."""
        result = etoro_client.get_watchlists()
        assert "error" not in result, f"API error: {result}"

    def test_02_create_watchlist(self, etoro_client):
        """Create a new test watchlist with a unique name."""
        unique_name = f"MCPTest{int(time.time())}"
        result = etoro_client.create_watchlist(unique_name)
        assert "error" not in result, f"API error: {result}"
        # Response may nest watchlist inside a 'watchlists' array
        wid = (
            result.get("watchlistId")
            or result.get("WatchlistId")
            or result.get("id")
            or result.get("Id")
        )
        if not wid:
            watchlists = result.get("watchlists", [])
            if watchlists:
                wid = watchlists[0].get("watchlistId") or watchlists[0].get("WatchlistId")
        assert wid is not None, f"No watchlist ID in response: {result}"
        TestWatchlistLifecycle._watchlist_id = str(wid)

    def test_03_add_items(self, etoro_client):
        """Add instruments to the watchlist."""
        if not TestWatchlistLifecycle._watchlist_id:
            pytest.skip("No watchlist_id from previous test")

        result = etoro_client.add_watchlist_items(
            TestWatchlistLifecycle._watchlist_id, [AAPL_ID, MSFT_ID]
        )
        assert "error" not in result, f"API error: {result}"

    def test_04_remove_items(self, etoro_client):
        """Remove one instrument from the watchlist."""
        if not TestWatchlistLifecycle._watchlist_id:
            pytest.skip("No watchlist_id from previous test")

        result = etoro_client.remove_watchlist_items(
            TestWatchlistLifecycle._watchlist_id, [MSFT_ID]
        )
        # DELETE on watchlist items may return 405 if API key lacks permission
        if "error" in result and "405" in str(result.get("error", "")):
            pytest.skip("DELETE watchlist items not permitted by API key (405)")
        assert "error" not in result, f"API error: {result}"

    def test_05_rename_watchlist(self, etoro_client):
        """Rename the watchlist."""
        if not TestWatchlistLifecycle._watchlist_id:
            pytest.skip("No watchlist_id from previous test")

        result = etoro_client.rename_watchlist(
            TestWatchlistLifecycle._watchlist_id, f"MCPRenamed{int(time.time())}"
        )
        # PUT on watchlist may return 405 if API key lacks permission
        if "error" in result and "405" in str(result.get("error", "")):
            pytest.skip("PUT rename watchlist not permitted by API key (405)")
        assert "error" not in result, f"API error: {result}"

    def test_06_delete_watchlist(self, etoro_client):
        """Delete the watchlist (cleanup)."""
        if not TestWatchlistLifecycle._watchlist_id:
            pytest.skip("No watchlist_id from previous test")

        result = etoro_client.delete_watchlist(TestWatchlistLifecycle._watchlist_id)
        # DELETE on watchlist may return 405 if API key lacks permission
        if "error" in result and "405" in str(result.get("error", "")):
            pytest.skip("DELETE watchlist not permitted by API key (405)")
        assert "error" not in result, f"API error: {result}"
