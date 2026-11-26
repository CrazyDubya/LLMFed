// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it('starts a new game with one request and opens the returned world', async () => {
  const player = { id: 'player-1', world_id: 'world-1', player_type: 'promoter', federation_id: 'promotion-1' };
  const fetchGame = vi.fn(async (path: string, options: RequestInit) => {
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'account-1', username: 'booker' },
      '/game/new-game': player,
      '/game/worlds': { id: player.world_id },
      '/game/players': player,
      '/game/worlds/world-1': { current_game_date: '2026-01-02' },
      '/game/federations/promotion-1': { name: 'Apex Pro Wrestling' },
    };
    return Response.json(responses[path] ?? [], { status: options.method === 'POST' ? 201 : 200 });
  });
  vi.stubGlobal('fetch', fetchGame);
  vi.stubGlobal('WebSocket', class { close() {} });
  localStorage.setItem('token', 'test-token');
  window.history.replaceState(null, '', '/setup');

  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: /Promoter Mode/ }));
  fireEvent.change(screen.getByPlaceholderText('e.g. Apex Pro Wrestling'), { target: { value: 'Apex Pro Wrestling' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start as Promoter' }));

  await screen.findByRole('heading', { name: 'Apex Pro Wrestling' });
  const submissions = fetchGame.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(submissions.map(([path, options]) => [path, JSON.parse(String(options.body))])).toEqual([
    ['/game/new-game', {
      world: { name: 'My Wrestling World' },
      player: { player_type: 'promoter', federation_name: 'Apex Pro Wrestling', federation_description: '' },
    }],
  ]);
  expect(window.location.pathname).toBe('/promoter');
  expect(localStorage.getItem('worldId')).toBe(player.world_id);
});

it('continues the same saved world after Exit and a reload', async () => {
  const user = { id: 'account-1', username: 'booker' };
  const player = { id: 'player-1', player_type: 'promoter', federation_id: 'promotion-1' };
  const fetchGame = vi.fn(async (path: string) => {
    const responses: Record<string, unknown> = {
      '/game/auth/me': user,
      '/game/worlds/world-1/my-player': player,
      '/game/worlds/world-1': { current_game_date: '2026-01-02' },
      '/game/federations/promotion-1': { name: 'Saved Promotion' },
    };
    return Response.json(responses[path] ?? []);
  });
  vi.stubGlobal('fetch', fetchGame);
  vi.stubGlobal('WebSocket', class { close() {} });
  localStorage.setItem('token', 'test-token');
  localStorage.setItem('worldId', 'world-1');
  localStorage.setItem('playerId', player.id);
  localStorage.setItem('playerType', player.player_type);
  localStorage.setItem('federationId', player.federation_id);
  window.history.replaceState(null, '', '/promoter');

  const { unmount } = render(<App />);
  await screen.findByRole('heading', { name: 'Saved Promotion' });
  fireEvent.click(screen.getByRole('button', { name: 'Exit' }));
  expect(screen.getByRole('heading', { name: 'New Game' })).toBeDefined();
  expect(localStorage.getItem('worldId')).toBeNull();
  expect(localStorage.getItem('playerId')).toBeNull();
  unmount();

  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Continue' }));

  await screen.findByRole('heading', { name: 'Saved Promotion' });
  expect(screen.getByText(/Promoter Mode \| 2026-01-02/)).toBeDefined();
  expect(window.location.pathname).toBe('/promoter');
  expect(localStorage.getItem('worldId')).toBe('world-1');
  expect(localStorage.getItem('playerId')).toBe(player.id);
  expect(fetchGame).toHaveBeenCalledWith('/game/worlds/world-1/my-player', expect.anything());
  expect(fetchGame.mock.calls.some(([path]) => path === '/game/worlds' || path === '/game/players')).toBe(false);
});
