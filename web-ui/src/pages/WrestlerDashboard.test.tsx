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
