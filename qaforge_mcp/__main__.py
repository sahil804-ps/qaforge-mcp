"""Entry point for QAForge MCP server.

Runs over stdio by default (for `claude mcp add ... -- python -m qaforge_mcp`).
Set MCP_TRANSPORT=http to run as a hosted HTTP/SSE connector instead — in that
mode each caller must send their own key via the X-Anthropic-Api-Key header
(see request_config.py), since the server is shared across users.
"""

import os


def main():
    from .server import mcp

    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport in ("http", "streamable-http", "sse"):
        port = int(os.getenv("PORT", "8000"))
        mcp.run(transport="http", host="0.0.0.0", port=port, uvicorn_config={"ws": "none"})
    else:
        mcp.run()


if __name__ == "__main__":
    main()
