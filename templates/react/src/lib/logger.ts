/**
 * Browser logger with level filtering.
 *
 * Levels (VITE_LOG_LEVEL): debug | info | warn | error. Default: info.
 * Import `log` instead of using `console.*` directly.
 *
 * Masking
 * -------
 * The browser console is visible to anyone with DevTools open. As a safety
 * net, this logger walks every argument and replaces values whose key is in
 * the sensitive list (password, token, authorization, ...) with
 * `[redacted: <key>]` before printing.
 *
 * Important: this only catches values nested inside an object. A raw string
 * like `log.info('the password is xyz')` cannot be detected — don't log raw
 * sensitive strings in the first place.
 *
 * For deliberate partial masking ("show last 4"), call mask() yourself.
 * Passwords and full tokens: do NOT log at all — not even masked.
 */

type Level = 'debug' | 'info' | 'warn' | 'error';

const RANK: Record<Level, number> = { debug: 0, info: 1, warn: 2, error: 3 };

const SENSITIVE_KEYS = new Set([
  'password', 'passwd', 'pwd',
  'token', 'access_token', 'accesstoken', 'refresh_token', 'refreshtoken',
  'id_token', 'idtoken',
  'secret', 'client_secret', 'clientsecret', 'api_key', 'apikey',
  'authorization', 'auth', 'cookie', 'session',
  'credit_card', 'creditcard', 'card_number', 'cardnumber', 'cvv', 'ssn',
]);

function currentLevel(): Level {
  const raw = (import.meta.env.VITE_LOG_LEVEL ?? 'info') as string;
  return (raw in RANK ? raw : 'info') as Level;
}

const threshold = RANK[currentLevel()];

function scrub(value: unknown): unknown {
  if (value == null || typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map(scrub);
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    out[k] = SENSITIVE_KEYS.has(k.toLowerCase()) ? `[redacted: ${k}]` : scrub(v);
  }
  return out;
}

function gated(min: Level, fn: (...args: unknown[]) => void) {
  return (...args: unknown[]) => {
    if (RANK[min] >= threshold) fn(...args.map(scrub));
  };
}

export const log = {
  debug: gated('debug', console.debug.bind(console)),
  info: gated('info', console.info.bind(console)),
  warn: gated('warn', console.warn.bind(console)),
  error: gated('error', console.error.bind(console)),
};

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
