"""Apero MCP server entry point (stdio JSON-RPC).

Run with:   python -m src.main
            (stdin/stdout speaks MCP — the host launches this process and
            pipes JSON-RPC. There is no HTTP, no port, no auth middleware.)

Replaces the base src/main.py when this project is an MCP server.

Spec + SDK: https://github.com/modelcontextprotocol/python-sdk

Why Python for MCP (Apero default):
    Reads as English. Non-coders writing tool wrappers can focus on
    "what should this tool do" instead of TypeScript types and async
    plumbing. Pick the Node mcp-server shape only if the project has a
    JS-ecosystem reason (existing Node libraries you must call, etc.).
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from src.config import get_settings
from src.logging_setup import setup_logging

setup_logging()
log = logging.getLogger("apero")
settings = get_settings()

# Python's logging.basicConfig() defaults to stderr — safe for MCP (stdout
# is the transport). Don't reconfigure to stdout.

server = FastMCP(settings.app_name)


@server.tool()
def echo(text: str) -> str:
    """Echo the input back. Replace with your real tools."""
    log.info("tool=echo chars=%d", len(text))
    return text


if __name__ == "__main__":
    log.info("mcp server starting (app=%s env=%s)", settings.app_name, settings.app_env)
    server.run()
