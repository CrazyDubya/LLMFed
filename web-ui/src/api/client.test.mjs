import assert from 'node:assert/strict';
import { test } from 'node:test';
import { api } from './client.ts';

function mockRequest(t, { path, method = 'GET', body, response, status = 200 }) {
  const previousStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: { getItem: key => key === 'token' ? 'signed-in-token' : null },
  });
  t.after(() => {
    if (previousStorage) Object.defineProperty(globalThis, 'localStorage', previousStorage);
    else delete globalThis.localStorage;
  });

  return t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, path);
    assert.equal(options.method ?? 'GET', method);
    const headers = new Headers(options.headers);
    assert.equal(headers.get('Authorization'), 'Bearer signed-in-token');
    if (body) assert.equal(headers.get('Content-Type'), 'application/json');
    assert.deepEqual(options.body ? JSON.parse(options.body) : undefined, body);
    return Response.json(response, { status });
  });
}

const cases = [
  {
    path: '/game/worlds/world-1/manager-bonds?federation_id=home-fed',
    request: () => api.listManagerBonds('world-1', 'home-fed'),
    response: [{ id: 'home-bond' }],
  },
  {
    path: '/game/worlds/world-1/manager-bonds',
    request: () => api.listManagerBonds('world-1'),
    response: [],
  },
  {
    path: '/game/worlds/world-1/storylines?status=active&federation_id=home-fed',
    request: () => api.listStorylines('world-1', 'active', 'home-fed'),
    response: [{ id: 'story-1', federation_id: 'home-fed' }],
  },
  {
    path: '/worlds/world-1/shows?limit=100',
    request: () => api.getWorldShows('world-1', 100),
    response: [{ id: 'show-1' }],
  },
  {
    path: '/scheduler/status',
    request: () => api.getSchedulerStatus(),
    response: { running: false },
  },
  {
    path: '/scheduler/start',
    method: 'POST',
    body: { interval_seconds: 120 },
    request: () => api.startScheduler(120),
    response: { running: true },
  },
  {
    path: '/scheduler/stop',
    method: 'POST',
    request: () => api.stopScheduler(),
    response: { running: false },
  },
];

for (const scenario of cases) {
  const label = `${scenario.method ?? 'GET'} ${scenario.path}`;
  test(`${label} sends the current bearer token`, async t => {
    const fetch = mockRequest(t, scenario);
    assert.deepEqual(await scenario.request(), scenario.response);
    assert.equal(fetch.mock.callCount(), 1);
  });

  test(`${label} rejects an API error instead of returning status data`, async t => {
    const message = 'Authentication required';
    mockRequest(t, { ...scenario, status: 401, response: { message } });
    await assert.rejects(scenario.request(), { message });
  });
}
