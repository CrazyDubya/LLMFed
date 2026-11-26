// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
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

it('shows written world news separately from the Live Feed', async () => {
  const headline = 'Weekly Dirt Sheet: Behind the Curtain';
  const body = "- Summit Wrestling is looking to make a big signing.\n\n- Its talent is optimistic.";
  const liveEvent = 'Summit Wrestling completed a show';
  const rawNarrative = 'The main event drew a big crowd';
  let emitLiveEvent: () => void;
  vi.stubGlobal('WebSocket', class {
    onmessage?: (event: { data: string }) => void;
    constructor() {
      emitLiveEvent = () => this.onmessage?.({ data: JSON.stringify({ type: 'show_completed', description: liveEvent }) });
    }
    close() {}
  });
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'news-user', username: 'promoter' },
      '/game/worlds/news-world': { current_game_date: '2026-01-08' },
      '/game/federations/news-fed': { name: 'Summit Wrestling' },
      '/game/worlds/news-world/narrative?limit=20': [{ id: 'event', event_type: 'show', description: rawNarrative }],
      '/game/worlds/news-world/news?limit=20': [{
        id: 'article',
        headline,
        body,
        category: 'dirt_sheet',
        game_date: '2026-01-07',
        source: 'Wrestling Observer Newsletter',
        is_kayfabe: false,
      }],
    };
    return Response.json(responses[path] ?? []);
  }));
  Object.entries({ token: 'test-token', worldId: 'news-world', federationId: 'news-fed', playerType: 'promoter' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/promoter');
  render(<App />);
  await screen.findByRole('heading', { name: 'Summit Wrestling' });
  fireEvent.click(screen.getByRole('button', { name: 'News' }));

  const article = within(await screen.findByRole('article'));
  expect(article.getByRole('heading', { name: headline })).toBeTruthy();
  expect(article.getByText(body, { normalizer: text => text })).toBeTruthy();
  expect(article.getByText('dirt sheet')).toBeTruthy();
  expect(article.getByText('Wrestling Observer Newsletter')).toBeTruthy();
  expect(article.getByText('2026-01-07').getAttribute('datetime')).toBe('2026-01-07');
  expect(screen.queryByText(rawNarrative)).toBeNull();

  await act(async () => emitLiveEvent());
  expect(screen.getByText('Live Feed')).toBeTruthy();
  expect(screen.getByText(liveEvent)).toBeTruthy();
  expect(article.queryByText(liveEvent)).toBeNull();
});
