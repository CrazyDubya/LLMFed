// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
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
