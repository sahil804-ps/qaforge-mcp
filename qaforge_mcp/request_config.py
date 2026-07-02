"""Per-request config resolution for multi-tenant (HTTP) deployments.

When running over stdio (local `claude mcp add`), there is one user per process,
so the ANTHROPIC_API_KEY env var (see config.py) is used directly.

When running over HTTP (a shared, hosted connector), each caller must supply
their own key via the `X-Anthropic-Api-Key` header so nobody's usage is billed
to the server operator's account. `get_http_headers()` returns {} outside of an
HTTP request context, so this is a no-op fallback to the env var locally.
"""

from fastmcp.server.dependencies import get_http_headers
from .config import config


def get_anthropic_api_key() -> str:
    header_key = get_http_headers().get("x-anthropic-api-key", "").strip()
    return header_key or config.anthropic_api_key


def ai_configured() -> bool:
    return bool(get_anthropic_api_key())
