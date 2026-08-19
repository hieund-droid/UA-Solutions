/**
 * Configured logger. Import `logger` everywhere instead of `console.log`.
 *
 * Levels (LOG_LEVEL env var): debug | info | warn | error. Default: info.
 *
 * Masking
 * -------
 * Secrets / PII must never appear in logs as raw values.
 *
 *   1. Pass sensitive fields as structured properties — pino redacts the
 *      paths below automatically:
 *          logger.info({ userId, password }, 'login');
 *          // → { ..., password: '***' }
 *
 *   2. For deliberate partial masking, call mask() yourself:
 *          logger.info({ key: mask(apiKey) }, 'api call');
 *          // → { ..., key: '…cdef' }
 *
 * Passwords and full tokens: do NOT log at all — not even masked. Log the
 * user ID, not the token.
 */

import pino from 'pino';

const level = (process.env.LOG_LEVEL ?? 'info').toLowerCase();
const allowed = new Set(['debug', 'info', 'warn', 'error']);

const SENSITIVE_PATHS = [
  'password', '*.password', 'passwd', '*.passwd',
  'token', '*.token',
  'access_token', '*.access_token', 'accessToken', '*.accessToken',
  'refresh_token', '*.refresh_token', 'refreshToken', '*.refreshToken',
  'id_token', '*.id_token', 'idToken', '*.idToken',
  'secret', '*.secret',
  'client_secret', '*.client_secret', 'clientSecret', '*.clientSecret',
  'api_key', '*.api_key', 'apiKey', '*.apiKey',
  'authorization', '*.authorization', 'Authorization', '*.Authorization',
  'cookie', '*.cookie', 'Cookie', '*.Cookie',
  'headers.authorization', 'headers.Authorization',
  'headers.cookie', 'headers.Cookie',
];

export const logger = pino({
  level: allowed.has(level) ? level : 'info',
  redact: { paths: SENSITIVE_PATHS, censor: '***' },
});

/**
 * Partial-mask a value: keep the last `keep` chars, replace the rest with `…`.
 * Use for values you intentionally want partially visible in logs
 * (e.g. an API key suffix for debugging). Never use as an excuse to log
 * a password or full token — those should not be logged at all.
 */
export function mask(value: string | null | undefined, keep = 4): string {
  if (value == null) return '***';
  const s = String(value);
  if (s.length <= keep) return '***';
  return `…${s.slice(-keep)}`;
}
