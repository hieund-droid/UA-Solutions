# shapes/mcp-server — convert this Python project to an MCP server

The base `templates/python/` ships shape-agnostic. This folder converts the project into an **MCP server** (Model Context Protocol — stdio JSON-RPC). MCP servers are launched by a host (Claude Code, Claude Desktop, an internal MCP client) and speak JSON-RPC over stdin/stdout. **No HTTP, no port, no auth middleware.**

## Python is the Apero default for MCP

MCP servers can be written in Python or Node. **Python is preferred** unless you have a specific JS-ecosystem reason — it reads as English and lets non-coders focus on *what the tool does* rather than transports and async types. The `mcp` Python SDK's `FastMCP` helper keeps the file short: declare a function, decorate it with `@server.tool()`, done. The Node variant is in `templates/nodejs/shapes/mcp-server/` for the cases where you need it.

## When to apply this shape

Apply if you're building a tool/resource provider that an MCP host calls:
- Wrap an Apero internal service so Claude can call it as a tool.
- Expose a data source as MCP resources.
- Build an internal Claude Code plugin.

If users / browsers / other services need to reach this directly over HTTP, you want `shapes/http-service/` instead.

## Apply the shape

```bash
SHAPE=shapes/mcp-server

# 1. Replace src/main.py with the MCP stdio scaffold
cp -R "$SHAPE/src/." src/

# 2. Add the MCP SDK to requirements.txt and install
cat "$SHAPE/requirements-add.txt" >> requirements.txt
python -m pip install -r requirements.txt

# 3. Declare your tools in src/main.py — each is a function decorated
#    with @server.tool(). The scaffold ships with an `echo` example.
```

## What you now have

- `python -m src.main` runs an MCP server over stdio. The host pipes JSON-RPC to/from this process.
- Tool declarations are functions in `src/main.py` decorated with `@server.tool()`. Type hints become the tool's input schema automatically — no separate JSON Schema to maintain.
- The same `logger` as every Apero project (Python `logging`, which defaults to stderr — safe for MCP since stdout is the transport).

## Rules that activate with this shape

- **stdout is the transport — DO NOT write to it.** `print(...)` is already banned by CLAUDE.md; for MCP the rule is now load-bearing. Python's standard `logging` defaults to stderr, so `log.info(...)` is safe. Don't override `setup_logging()` to use stdout.
- **No auth middleware.** Authn is the host's job; the host has already authenticated the user before launching this process. The process's environment / arguments are trusted.
- **Secrets via `Settings` fields from `src/config.py`** (read from `.env`) — same rules as every Apero project. Never log a raw secret; never commit `.env`.
- **Tools should be idempotent where possible.** MCP clients retry; double-invocations should be safe.

## Rolling back

`git checkout src/main.py requirements.txt && python -m pip install -r requirements.txt`.
