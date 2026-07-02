"""Entry point for QAForge MCP server."""


def main():
    from .server import mcp
    mcp.run()


if __name__ == "__main__":
    main()
