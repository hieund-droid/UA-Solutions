# shapes/mcp-server — convert this Node project to an MCP server

> **Apero default is Python for MCP — see `templates/python/shapes/mcp-server/`.** The Python `FastMCP` API reads as English (decorate a function with `@server.tool()` and you're done), which suits the many non-coders at Apero building Claude tooling. Pick this Node variant only when you have a specific reason — e.g. existing Node libraries you must call, an MCP server that's part of a larger Node codebase, or genuine team preference. Both stacks produce a valid MCP server; the question is which language your team will maintain happily.

The base `templates/nodejs/` ships shape-agnostic. This folder converts the project into an **MCP server** (Model Context Protocol — stdio JSON-RPC). MCP servers are launched by a host (e.g. Claude Code, Claude Desktop, an internal MCP client) and speak JSON-RPC over stdin/stdout. **No HTTP, no port, no auth middleware.**

## When to apply this shape

Apply if you're building a tool/resource provider that an MCP host calls. Typical examples:
- Wrap an internal Apero service so it's available to Claude as a tool.
- Expose a data source as MCP resources.
- Build an internal Claude Code plugin.

If users / browsers / other services need to reach this directly over HTTP, you want `shapes/http-service/` instead.

## Apply the shape

```bash
SHAPE=shapes/mcp-server

# 1. Replace src/main.ts with the MCP stdio scaffold
cp -R "$SHAPE/src/." src/

# 2. Merge package-additions.json into your package.json (dependencies),
#    then `pnpm install`. The SDK is published as @modelcontextprotocol/sdk —
#    pin to the latest stable version at conversion time.

# 3. (Optional) Declare your tools in src/main.ts (ListToolsRequestSchema /
#    CallToolRequestSchema handlers — the scaffold has TODOs).
```

## What you now have

- `pnpm start` runs an MCP server over stdio. The host pipes JSON-RPC to/from this process.
- Tool declarations + dispatch in `src/main.ts`.
- The same `logger` as every Apero project (pino, redaction). **Log to stderr only** — stdout is the MCP transport; anything written there corrupts the protocol. Pino defaults to stdout, so you'll want to configure a destination stream pointing at `process.stderr` in `src/logger.ts` for MCP projects.

## Rules that activate with this shape

- **stdout is the transport — DO NOT write to it.** The pino logger ships pointing at stdout; change it to `process.stderr` for MCP. Any `console.log` (already banned) would break the host.
- **No auth middleware.** Authn is the host's job; the host has already authenticated the user before launching this process. The process's environment / arguments are trusted.
- **Secrets via `ConfigSchema` fields from `src/config.ts`** (read from `.env`) — same rules as every Apero project. Never log a raw secret; never commit `.env`.
- **Tools should be idempotent where possible.** MCP clients retry; double-invocations should be safe.

## Rolling back

`git checkout src/main.ts package.json && pnpm install`.
