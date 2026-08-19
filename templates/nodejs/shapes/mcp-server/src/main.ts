/**
 * Apero MCP server entry point (stdio JSON-RPC).
 *
 * Run with:    pnpm start    (tsx src/main.ts — stdin/stdout speaks MCP)
 *
 * Replaces the base src/main.ts when this project is an MCP server.
 *
 * Spec + SDK: https://github.com/modelcontextprotocol/typescript-sdk
 *
 * Note: MCP servers do NOT bind to a port. The transport is stdio — the
 * host (e.g. Claude Code) launches this process and pipes JSON-RPC. There
 * is no HTTP, no auth middleware, no docker-compose port mapping.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';

import { getConfig } from './config.js';
import { logger } from './logger.js';

const config = getConfig();

const server = new Server(
  { name: config.APP_NAME, version: '0.1.0' },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    // TODO: declare your tools here.
    // {
    //   name: 'echo',
    //   description: 'Echo the input back',
    //   inputSchema: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] },
    // },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  logger.info({ tool: req.params.name }, 'tool call');
  // TODO: dispatch on req.params.name.
  throw new Error(`Unknown tool: ${req.params.name}`);
});

export async function main(): Promise<number> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  logger.info({ app: config.APP_NAME, env: config.APP_ENV }, 'mcp server ready');
  // server.connect() keeps the process alive on stdio.
  return 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  void main().catch((err) => {
    logger.error({ err: err instanceof Error ? err.message : String(err) }, 'fatal');
    process.exit(1);
  });
}
