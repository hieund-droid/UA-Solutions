/**
 * Public config — every value here ships in the JS bundle and is visible to users.
 * NEVER put a secret here. See CLAUDE.md.
 */

export const config = {
  appName: import.meta.env.VITE_APP_NAME ?? 'apero-app',
  appEnv: import.meta.env.VITE_APP_ENV ?? 'local',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000',
  sso: {
    issuer: import.meta.env.VITE_APERO_SSO_ISSUER ?? 'https://sso.apero.vn',
    clientId: import.meta.env.VITE_APERO_SSO_CLIENT_ID ?? '',
  },
} as const;
