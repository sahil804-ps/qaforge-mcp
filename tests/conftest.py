import pytest

from qaforge_mcp.config import config


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    """Keep tests offline and deterministic: never call the Anthropic API."""
    monkeypatch.setattr(config, "anthropic_api_key", "")
