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

it('shows a newly booked show with its Build Card action after the dashboard reloads', async () => {
  const endpoint = '/game/federations/shows-fed/shows';
  const date = '2026-01-01';
  const laterShows = Array.from({ length: 20 }, (_, index) => ({
    id: `later-${index}`,
    name: `Future Event ${20 - index}`,
    game_date: `2026-02-${String(20 - index).padStart(2, '0')}`,
    is_completed: false,
  }));
  const created = {
    id: 'new-show', name: 'Summit Live Event', game_date: date,
    federation_id: 'shows-fed', show_type: 'weekly', venue: 'Local Arena', is_completed: false,
  };
  const soonestFirst = [...laterShows].reverse();
  let booked = false;
  const fetch = vi.fn(async (path: string, options?: RequestInit) => {
    if (path === endpoint && options?.method === 'POST') {
      booked = true;
      return Response.json(created, { status: 201 });
    }
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'shows-user', username: 'promoter' },
      '/game/worlds/shows-world': { current_game_date: date },
      '/game/federations/shows-fed': { name: 'Summit Wrestling', short_name: 'Summit' },
      [`${endpoint}?limit=20`]: laterShows,
      [`${endpoint}?limit=20&order=booking`]: booked ? [created, ...soonestFirst.slice(0, 19)] : soonestFirst,
      '/game/shows/new-show/card': { show: created, segments: [] },
    };
    return Response.json(responses[path] ?? []);
  });
  vi.stubGlobal('fetch', fetch);
  vi.stubGlobal('WebSocket', class { close() {} });
  Object.entries({ token: 'test-token', worldId: 'shows-world', federationId: 'shows-fed', playerType: 'promoter' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/promoter');
  const dashboard = render(<App />);
  await screen.findByRole('heading', { name: 'Summit Wrestling' });
  fireEvent.click(screen.getByRole('button', { name: 'Shows' }));
  expect(screen.getByRole('heading', { name: 'Future Event 1' })).toBeTruthy();
  expect(screen.queryByRole('heading', { name: created.name })).toBeNull();

  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Book New Show' })));
  expect(fetch).toHaveBeenCalledWith(endpoint, expect.objectContaining({ method: 'POST' }));
  expect(screen.getByRole('heading', { name: created.name })).toBeTruthy();

  dashboard.unmount();
  render(<App />);
  await screen.findByRole('heading', { name: 'Summit Wrestling' });
  fireEvent.click(screen.getByRole('button', { name: 'Shows' }));
  const newShow = screen.getByRole('heading', { name: created.name }).parentElement!.parentElement!;
  expect(screen.getByRole('heading', { name: 'Future Event 1' })).toBeTruthy();
  fireEvent.click(within(newShow).getByRole('button', { name: 'Build Card' }));
  expect(window.location.pathname).toBe('/show/new-show/book');
  await screen.findByRole('heading', { name: `Card Builder: ${created.name}` });
});

it('shows written world news separately from the Live Feed', async () => {
  const headline = 'Weekly Dirt Sheet: Behind the Curtain';
  const rumors = [
    'Summit Wrestling is looking to make a big signing.',
    'Its talent is optimistic.',
    'Rival promoters are watching closely.',
  ];
  const reportHeadline = 'Summit Weekly delivers solid action';
  const reportParagraph = 'Summit Weekly earned an overall rating of 3.5 stars.';
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
        body: `- ${rumors[0]}\n\n- ${rumors[1]}\n- ${rumors[2]}`,
        category: 'dirt_sheet',
        game_date: '2026-01-07',
        source: 'Wrestling Observer Newsletter',
        is_kayfabe: false,
      }, {
        id: 'report',
        headline: reportHeadline,
        body: 'Summit Weekly earned an overall\nrating of 3.5 stars.\n\nFans filled the arena.',
        category: 'show_results',
        game_date: '2026-01-06',
        source: 'Summit Report',
        is_kayfabe: true,
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

  const [dirtSheet, showResults] = await screen.findAllByRole('article');
  const article = within(dirtSheet);
  expect(article.getByRole('heading', { name: headline })).toBeTruthy();
  const list = within(article.getByRole('list'));
  expect(list.getAllByRole('listitem').map(item => item.textContent)).toEqual(rumors);
  expect(within(showResults).getByRole('heading', { name: reportHeadline })).toBeTruthy();
  expect(Array.from(showResults.querySelectorAll('p')).map(p => p.textContent))
    .toEqual(['Summit Report', reportParagraph, 'Fans filled the arena.']);
  expect(article.getByText('dirt sheet')).toBeTruthy();
  expect(article.getByText('Wrestling Observer Newsletter')).toBeTruthy();
  expect(article.getByText('2026-01-07').getAttribute('datetime')).toBe('2026-01-07');
  expect(screen.queryByText(rawNarrative)).toBeNull();

  await act(async () => emitLiveEvent());
  expect(screen.getByText('Live Feed')).toBeTruthy();
  expect(screen.getByText(liveEvent)).toBeTruthy();
  expect(article.queryByText(liveEvent)).toBeNull();
});
