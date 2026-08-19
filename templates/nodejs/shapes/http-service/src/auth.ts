/**
 * hq-apero-sso integration.
 *
 * This is the ONLY place auth lives. Use the `requireUser` middleware in routes.
 * Replace `_decodeToken` with the real call from https://github.com/Apero-Vibecode/hq-apero-sso
 * (or invoke /sso-wire-up).
 */

import type { NextFunction, Request, Response } from 'express';

import { getConfig } from './config.js';

export interface User {
  sub: string;
  email: string;
  groups: readonly string[];
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      user?: User;
    }
  }
}

async function _decodeToken(_token: string): Promise<User> {
  void getConfig();
  throw new Error(
    'SSO not yet wired — see auth.ts and https://github.com/Apero-Vibecode/hq-apero-sso',
  );
}

export async function requireUser(req: Request, res: Response, next: NextFunction): Promise<void> {
  const header = req.header('authorization');
  if (!header?.toLowerCase().startsWith('bearer ')) {
    res.status(401).json({ error: 'Missing bearer token' });
    return;
  }
  const token = header.slice('bearer '.length).trim();
  try {
    req.user = await _decodeToken(token);
    next();
  } catch (_err) {
    res.status(401).json({ error: 'Invalid token' });
  }
}

export function requireGroup(group: string) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user?.groups.includes(group)) {
      res.status(403).json({ error: `Requires group: ${group}` });
      return;
    }
    next();
  };
}
