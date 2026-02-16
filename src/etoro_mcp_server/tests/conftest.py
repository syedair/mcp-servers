import os
import pytest
from etoro_mcp_server.etoro_client import EtoroClient


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "trading: marks tests that create/close positions")
    config.addinivalue_line("markers", "social: marks tests that create posts/comments (write to social feed)")


def _missing_env_vars():
    required = ["ETORO_API_KEY", "ETORO_DEMO_USER_KEY"]
    return [v for v in required if not os.environ.get(v)]


skip_reason = (
    f"Missing env vars: {', '.join(_missing_env_vars())}" if _missing_env_vars() else None
)


@pytest.fixture(scope="session")
def etoro_client():
    if skip_reason:
        pytest.skip(skip_reason)
    return EtoroClient(
        api_key=os.environ["ETORO_API_KEY"],
        user_key=os.environ["ETORO_DEMO_USER_KEY"],
        account_type="demo",
    )
