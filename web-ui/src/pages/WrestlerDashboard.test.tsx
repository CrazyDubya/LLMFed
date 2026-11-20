// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
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
