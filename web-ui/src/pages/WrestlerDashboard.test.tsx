// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it('refreshes the world date when the live feed reconnects without another tick', async () => {
  const before = '2026-01-01';
  const after = '2026-01-02';
  let worldDate = before;
  const getWorld = vi.fn(() => Response.json({ current_game_date: worldDate }));
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/game/worlds/career-world') return getWorld();
    if (path === '/game/auth/me') return Response.json({ id: 'career-user', username: 'career' });
    if (path === '/game/wrestlers/career-wrestler') {
      return Response.json({ wrestler: { name: 'Alex Summit' }, stats: null });
    }
    return Response.json([]);
  }));
  const sockets: TestSocket[] = [];
  class TestSocket {
    onopen: (() => void) | null = null;
    onclose: (() => void) | null = null;

    constructor() { sockets.push(this); }
    close() { this.onclose?.(); }
  }
  vi.stubGlobal('WebSocket', TestSocket);
  Object.entries({ token: 'test-token', worldId: 'career-world', wrestlerId: 'career-wrestler', playerType: 'wrestler' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/wrestler');
  render(<App />);
  await screen.findByText(new RegExp(before));
  vi.useFakeTimers();
  act(() => sockets[0].onopen?.());
  expect(screen.getByText('LIVE')).toBeDefined();
  expect(getWorld).toHaveBeenCalledTimes(1);

  act(() => sockets[0].close());
  expect(screen.getByText('OFFLINE')).toBeDefined();
  worldDate = after;
  act(() => vi.advanceTimersByTime(1000));
  expect(getWorld).toHaveBeenCalledTimes(1);
  await act(async () => sockets[1].onopen?.());

  expect(screen.getByText('LIVE')).toBeDefined();
  expect(screen.getByText(new RegExp(after))).toBeDefined();
});

it.each([
  { federation: 'summit-fed', titles: ['World Championship', 'TV Championship'], years: 7, contract: 'Signed' },
  { federation: null, titles: [], years: 0, contract: 'Free Agent' },
])('renders career data from the wrestler response: $contract', async ({ federation, titles, years, contract }) => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'career-user', username: 'career' },
      '/game/worlds/career-world': { current_game_date: '2026-01-01' },
      '/game/wrestlers/career-wrestler': {
        wrestler: { name: 'Alex Summit', experience_years: years },
        stats: null,
        current_federation: federation,
        current_championships: titles,
      },
    };
    return Response.json(responses[path] ?? []);
  }));
  vi.stubGlobal('WebSocket', class { close() {} });
  Object.entries({ token: 'test-token', worldId: 'career-world', wrestlerId: 'career-wrestler', playerType: 'wrestler' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/wrestler');
  render(<App />);
  await screen.findByRole('heading', { name: 'Alex Summit' });
  fireEvent.click(screen.getByRole('button', { name: /Career/ }));
  expect(screen.getByText('Contract:').textContent).toBe(`Contract: ${contract}`);
  expect(screen.getByText('Championships:').textContent).toBe(`Championships: ${titles.length}`);
  expect(screen.getByText('Years Active').previousElementSibling?.textContent).toBe(String(years));
});

it('shows an error when career data cannot be loaded', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path === '/game/auth/me'
    ? Response.json({ id: 'career-user', username: 'career' })
    : Response.json({ detail: 'Career unavailable' }, { status: 500 })));
  vi.stubGlobal('WebSocket', class { close() {} });
  Object.entries({ token: 'test-token', worldId: 'career-world', wrestlerId: 'career-wrestler', playerType: 'wrestler' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/wrestler');
  render(<App />);
  expect(await screen.findByText('Career unavailable')).toBeDefined();
});

function deferredResponse() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>(done => { resolve = done; });
  return { promise, resolve };
}

async function renderRefreshDashboard() {
  const world = '/game/worlds/refresh-world';
  const wrestler = '/game/wrestlers/refresh-wrestler';
  const routes = [world, wrestler, `${world}/narrative?limit=20`, `${world}/federations`,
    `${wrestler}/stable`, `${wrestler}/manager`].sort();
  class Socket {
    static current: Socket;
    onopen?: () => void;
    onclose?: () => void;
    onmessage?: (event: { data: string }) => void;
    constructor() { Socket.current = this; }
    close() {}
  }
  vi.stubGlobal('WebSocket', Socket);
  const advance = deferredResponse();
  let worldResponse: Promise<Response> | undefined;
  let worldDate = '2026-01-01';
  const fetchMock = vi.fn(async (path: string) => {
    if (path === `${world}/tick?days=7`) return advance.promise;
    if (path === world) return worldResponse ?? Response.json({ current_game_date: worldDate });
    if (path === wrestler) return Response.json({ wrestler: { name: 'Alex Summit' } });
    return Response.json([]);
  });
  vi.stubGlobal('fetch', fetchMock);
  Object.entries({ token: 'test-token', worldId: 'refresh-world', wrestlerId: 'refresh-wrestler', playerType: 'wrestler' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/wrestler');
  render(<App />);
  await screen.findByText(new RegExp(worldDate));
  fetchMock.mockClear();

  const emit = (type: string, tick?: number) =>
    Socket.current.onmessage?.({ data: JSON.stringify({ type, tick }) });
  return {
    advance,
    emit,
    reconnect: async () => {
      vi.useFakeTimers();
      try {
        Socket.current.onclose?.();
        await vi.advanceTimersByTimeAsync(1000);
        Socket.current.onopen?.();
      } finally {
        vi.useRealTimers();
      }
    },
    burst: (tick: number) => {
      emit('tick', tick);
      emit('show_completed');
      emit('show_completed');
    },
    blockRefresh: () => {
      const response = deferredResponse();
      worldResponse = response.promise;
      return (result = Response.json({ current_game_date: worldDate })) => {
        worldResponse = undefined;
        response.resolve(result);
      };
    },
    setWorldDate: (date: string) => { worldDate = date; },
    expectRefreshes: (count: number) => expect(
      fetchMock.mock.calls.map(([path]) => path).filter(path => routes.includes(path)).sort(),
    ).toEqual(Array.from({ length: count }, () => routes).flat().sort()),
  };
}

it.each(['before', 'after', 'without'] as const)(
  'refreshes once when Next Week returns %s socket tick and show frames',
  async (when) => {
    const { advance, burst, setWorldDate, expectRefreshes } = await renderRefreshDashboard();
    fireEvent.click(screen.getByRole('button', { name: 'Next Week' }));
    setWorldDate('2026-01-08');
    if (when === 'after') await act(async () => burst(7));
    expectRefreshes(0);
    await act(async () => advance.resolve(Response.json({ current_tick: 7 })));
    if (when === 'before') await act(async () => burst(7));
    expectRefreshes(1);
    expect(screen.getByText(/2026-01-08/)).toBeDefined();
    if (when !== 'without') expect(screen.getByText('3 events')).toBeDefined();
  },
);

it('refreshes once for an external tick and coalesces newer ticks during that load', async () => {
  const { blockRefresh, burst, emit, expectRefreshes } = await renderRefreshDashboard();
  const unblock = blockRefresh();
  await act(async () => burst(7));
  await act(async () => { burst(8); burst(9); });
  expectRefreshes(1);
  await act(async () => unblock());
  await act(async () => emit('show_completed'));
  expectRefreshes(2);
});

it.each([2, 7])('reloads after a non-increasing socket tick (%i)', async (tick) => {
  const { blockRefresh, burst, setWorldDate, expectRefreshes } = await renderRefreshDashboard();
  const unblock = blockRefresh();
  await act(async () => burst(7));
  await act(async () => burst(tick));
  expectRefreshes(1);
  setWorldDate('2026-01-03');
  await act(async () => unblock(Response.json({ current_game_date: '2026-01-08' })));
  expectRefreshes(2);
  expect(screen.getByText(/2026-01-03/)).toBeDefined();
});

it('retries an unsuccessful refresh on a later show frame for the same tick', async () => {
  const { blockRefresh, burst, emit, expectRefreshes } = await renderRefreshDashboard();
  const unblock = blockRefresh();
  await act(async () => burst(7));
  expectRefreshes(1);
  await act(async () => unblock(Response.json({ message: 'Could not load world' }, { status: 500 })));
  expect(screen.getByText('Could not load world')).toBeDefined();
  await act(async () => emit('show_completed'));
  expectRefreshes(2);
  await act(async () => emit('show_completed'));
  expectRefreshes(2);
});

it('refreshes a lower tick after a rollback while disconnected', async () => {
  const { burst, reconnect, setWorldDate, expectRefreshes } = await renderRefreshDashboard();
  await act(async () => burst(7));
  setWorldDate('2026-01-02');
  await act(reconnect);
  setWorldDate('2026-01-03');
  await act(async () => burst(2));
  expectRefreshes(3);
  expect(screen.getByText(/2026-01-03/)).toBeDefined();
});

it('refreshes deferred socket changes if the advance request fails', async () => {
  const { advance, burst, expectRefreshes } = await renderRefreshDashboard();
  fireEvent.click(screen.getByRole('button', { name: 'Next Week' }));
  await act(async () => burst(7));
  expectRefreshes(0);
  await act(async () => advance.resolve(Response.json({ message: 'Could not advance' }, { status: 500 })));
  expect(screen.getByText('Could not advance')).toBeDefined();
  expectRefreshes(1);
});
