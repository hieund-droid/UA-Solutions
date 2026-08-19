import request from 'supertest';
import { describe, expect, it } from 'vitest';

import { app } from '../src/main.js';

describe('GET /healthz', () => {
  it('returns ok', async () => {
    const res = await request(app).get('/healthz');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
  });
});
