/**
 * Apero Node.js entry point.
 *
 * Run with:    pnpm start                              (tsx src/main.ts)
 *      or:    pnpm dev                                 (auto-reload)
 *      or:    pnpm build && node dist/src/main.js      (prod)
 *
 * This is the shape-agnostic default. Out of the box it logs "hello" and
 * exits — your job is to fill in what the program actually does.
 *
 * If this project is going to accept inbound HTTP from users, see
 * `shapes/http-service/`. If it speaks MCP over stdio, see
 * `shapes/mcp-server/`. CLI / cron / worker projects stay shaped like
 * this file (single entry point, logger, exit).
 */

import { getConfig } from './config.js';
import { logger } from './logger.js';

const config = getConfig();

export async function main(): Promise<number> {
  logger.info({ app: config.APP_NAME, env: config.APP_ENV }, 'hello');
  // TODO: replace this stub with what your program actually does.
  return 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  void main().then((code) => process.exit(code));
}
