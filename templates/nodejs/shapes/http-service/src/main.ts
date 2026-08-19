/**
 * Apero HTTP service entry point.
 *
 * Run with:    pnpm dev                                 (auto-reload)
 *      or:    pnpm start                                (tsx src/main.ts)
 *      or:    pnpm build && node dist/src/main.js       (prod)
 *
 * Replaces the base src/main.ts when this project is shaped as an HTTP service.
 */

import 'express-async-errors';

import express, { type Request, type Response } from 'express';
import helmet from 'helmet';
import pinoHttp from 'pino-http';

import { requireUser } from './auth.js';
import { getConfig } from './config.js';
import { logger } from './logger.js';

const config = getConfig();

export const app = express();

app.use(helmet());
app.use(express.json({ limit: '100kb' }));
app.use(pinoHttp({ logger }));

app.get('/healthz', (_req: Request, res: Response) => {
  logger.debug('healthz hit');
  res.json({ status: 'ok', env: config.APP_ENV });
});

app.get('/me', requireUser, (req: Request, res: Response) => {
  const user = req.user!;
  logger.info({ sub: user.sub }, 'me requested');
  res.json({ sub: user.sub, email: user.email, groups: user.groups });
});

app.use((err: Error, _req: Request, res: Response, _next: express.NextFunction) => {
  logger.error({ err: err.message }, 'unhandled error');
  res.status(500).json({ error: 'Internal error' });
});

if (import.meta.url === `file://${process.argv[1]}`) {
  app.listen(config.APP_PORT, () => {
    logger.info(
      { port: config.APP_PORT, env: config.APP_ENV, level: config.LOG_LEVEL },
      `${config.APP_NAME} listening`,
    );
  });
}
