// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it.each([
  { budget: -17181.2, text: `Budget: -$${(17181).toLocaleString()}`, color: 'text-red-400' },
  { budget: -0.5, text: `Budget: -$${(1).toLocaleString()}`, color: 'text-red-400' },
  { budget: -0.4, text: `Budget: $${(0).toLocaleString()}`, color: 'text-green-400' },
  { budget: 17181.2, text: `Budget: $${(17181).toLocaleString()}`, color: 'text-green-400' },
  { budget: 0, text: `Budget: $${(0).toLocaleString()}`, color: 'text-green-400' },
])('renders the budget with the expected sign and color: $budget', async ({ budget, text, color }) => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'budget-user', username: 'promoter' },
      '/game/worlds/budget-world': { current_game_date: '2026-01-01' },
      '/game/federations/budget-fed': { name: 'Summit Wrestling', budget },
    };
    return Response.json(responses[path] ?? []);
  }));
  vi.stubGlobal('WebSocket', class { close() {} });
  Object.entries({ token: 'test-token', worldId: 'budget-world', federationId: 'budget-fed', playerType: 'promoter' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/promoter');
  render(<App />);
  await screen.findByRole('heading', { name: 'Summit Wrestling' });
  expect(screen.getByText(text).classList.contains(color)).toBe(true);
});

it('shows the reigning champion and distinguishes vacant titles', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'titles-user', username: 'promoter' },
      '/game/worlds/titles-world': { current_game_date: '2026-01-01' },
      '/game/federations/titles-fed': { name: 'Summit Wrestling' },
      '/game/federations/titles-fed/roster': [{ id: 'ivy', name: 'Ivy Steel' }],
      '/game/federations/titles-fed/championships': [
        { id: 'world', name: 'World Championship', current_holder_id: 'ivy', prestige: 50, defenses: 3 },
        { id: 'tv', name: 'Television Championship', current_holder_id: null, prestige: 35, defenses: 0 },
        { id: 'openweight', name: 'Openweight Championship', current_holder_id: 'nova', prestige: 40, defenses: 1 },
        { id: 'national', name: 'National Championship', current_holder_id: 'missing', prestige: 45, defenses: 2 },
      ],
      '/game/wrestlers/nova': { wrestler: { id: 'nova', name: 'Nova Reyes' } },
    };
    if (path === '/game/wrestlers/missing') return new Response(null, { status: 404 });
    return Response.json(responses[path] ?? []);
  }));
  vi.stubGlobal('WebSocket', class { close() {} });
  Object.entries({ token: 'test-token', worldId: 'titles-world', federationId: 'titles-fed', playerType: 'promoter' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/promoter');
  render(<App />);
  await screen.findByRole('heading', { name: 'Summit Wrestling' });
  fireEvent.click(screen.getByRole('button', { name: 'Titles' }));

  const title = (name: string) => within(screen.getByRole('heading', { name }).parentElement!);
  expect(title('World Championship').getByText('Ivy Steel')).toBeDefined();
  expect(title('World Championship').getByText('Prestige: 50 | Defenses: 3')).toBeDefined();
  expect(title('Television Championship').getByText('Vacant')).toBeDefined();
  expect(title('Openweight Championship').getByText('Nova Reyes')).toBeDefined();
  expect(title('National Championship').getByText('Unknown')).toBeDefined();
  expect(screen.getAllByText('Vacant')).toHaveLength(1);
});
