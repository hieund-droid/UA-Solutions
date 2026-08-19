/**
 * Shape-agnostic smoke test.
 *
 * Proves config + logger load and the entry point's `main()` resolves to 0.
 * Replace with real tests as the project grows. The http-service shape
 * overwrites this file with a supertest version — see
 * shapes/http-service/tests/main.test.ts.
 */
import { describe, expect, it } from 'vitest';

import { main } from '../src/main.js';

describe('main', () => {
  it('runs and returns 0', async () => {
    expect(await main()).toBe(0);
  });
});
