/**
 * Single source of truth for environment + secrets.
 *
 * Rules (CLAUDE.md):
 * - Secrets live in .env (gitignored) — one config field per secret, read
 *   directly. Declaring them here keeps every secret the app reads discoverable
 *   in one place (no ad-hoc `process.env` reads scattered through the code).
 * - .env is NEVER committed. In prod the same vars are injected as environment
 *   variables by the deploy platform — not read from a file.
 * - A shared secret store (Vault) is a deferred, future option — not required
 *   today. See ../../docs/vault.md.
 */

import { z } from 'zod';

// HTTP-service / SSO fields are not declared here. They live in
// shapes/http-service/config-additions.ts and get pasted in when that
// shape is applied. CLI / cron / worker / mcp-server projects don't need them.
const ConfigSchema = z.object({
  APP_NAME: z.string().default('apero-project'),
  APP_ENV: z.enum(['local', 'dev', 'staging', 'prod']).default('local'),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),

  // --- Secrets ---
  // Add one field per secret your app reads, named SECRET_*, matching a line in
  // .env. Read it directly at the use site — no helper, no provider:
  //     const apiKey = getConfig().SECRET_OPENAI_API_KEY;
  // Uncomment + add the matching line to .env (and .env.example):
  //
  //   SECRET_OPENAI_API_KEY: z.string().default(''),
  //   SECRET_GOOGLE_OAUTH_CLIENT_ID: z.string().default(''),
  //   SECRET_GOOGLE_OAUTH_CLIENT_SECRET: z.string().default(''),
  //
  // Never log the raw value — mask it (see logger.ts). Never commit .env.
});

export type Config = z.infer<typeof ConfigSchema>;

let cached: Config | null = null;

export function getConfig(): Config {
  if (cached) return cached;
  cached = ConfigSchema.parse(process.env);
  return cached;
}
