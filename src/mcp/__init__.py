"""MCP (Model Context Protocol) - Agent communication layer"""
from .server import MCPServer, get_mcp_server
from .client import MCPClient

__all__ = ["MCPServer", "MCPClient", "get_mcp_server"]
