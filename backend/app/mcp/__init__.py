"""MCP server mounted in the API process. Tools call the shared services."""

from app.mcp.server import mcp, mcp_app

__all__ = ["mcp", "mcp_app"]
