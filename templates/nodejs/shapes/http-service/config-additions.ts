/**
 * HTTP-service-only zod schema fields.
 *
 * When converting the project to an HTTP service, ADD these fields to the
 * `ConfigSchema` z.object({...}) in the project's `src/config.ts`. They're
 * split out so CLI / cron / worker / mcp-server projects don't carry inert
 * HTTP/SSO settings.
 *
 * NOTE: This file is not imported — it's a reference snippet. Copy the
 * field declarations below into your project's `ConfigSchema`.
 */
import { z } from 'zod';

void z;

/* Add to ConfigSchema:

  APP_PORT: z.coerce.number().int().positive().default(3000),
  APERO_SSO_ISSUER: z.string().default(''),
  APERO_SSO_CLIENT_ID: z.string().default(''),
  APERO_SSO_AUDIENCE: z.string().default(''),

`src/auth.ts::_decodeToken` reads APERO_SSO_* to verify inbound bearer tokens.
*/
