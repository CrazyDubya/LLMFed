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

function deferredResponse() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>(done => { resolve = done; });
  return { promise, resolve };
}

async function renderRefreshDashboard() {
  const worldPath = '/game/worlds/refresh-world';
  const federationPath = '/game/federations/refresh-fed';
  const routes = [
    federationPath, `${federationPath}/roster`, `${worldPath}/free-agents`,
    `${federationPath}/shows?limit=20`, `${federationPath}/championships`,
    `${worldPath}/news?limit=20`, worldPath,
    `${worldPath}/storylines?federation_id=refresh-fed`,
    `${worldPath}/stables?federation_id=refresh-fed`,
    `${worldPath}/manager-bonds?federation_id=refresh-fed`,
    `${worldPath}/managers?federation_id=refresh-fed`,
  ].sort();
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
  let federationResponse: Promise<Response> | undefined;
  const fetchMock = vi.fn(async (path: string) => {
    if (path === `${worldPath}/tick?days=1`) return advance.promise;
    if (path === federationPath && federationResponse) return federationResponse;
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'refresh-user', username: 'promoter' },
      [worldPath]: { current_game_date: '2026-01-01', current_tick: 1 },
      [federationPath]: { name: 'Summit Wrestling' },
    };
    return Response.json(responses[path] ?? []);
  });
  vi.stubGlobal('fetch', fetchMock);
  Object.entries({ token: 'test-token', worldId: 'refresh-world', federationId: 'refresh-fed', playerType: 'promoter' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/promoter');
  render(<App />);
  await screen.findByRole('heading', { name: 'Summit Wrestling' });
  await act(async () => Socket.current.onopen?.());
  fetchMock.mockClear();
  const emit = (type: string, tick?: number | string) =>
    Socket.current.onmessage?.({ data: JSON.stringify({ type, tick }) });
  return {
    advance,
    emit,
    burst: (tick: number) => {
      emit('tick', tick);
      emit('show_completed');
      emit('show_completed');
    },
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
    blockRefresh: () => {
      const response = deferredResponse();
      federationResponse = response.promise;
      return (result = Response.json({ name: 'Summit Wrestling' })) => {
        federationResponse = undefined;
        response.resolve(result);
      };
    },
    expectRefreshes: (count: number) => expect(
      fetchMock.mock.calls.map(([path]) => path).filter(path => routes.includes(path)).sort(),
    ).toEqual(Array.from({ length: count }, () => routes).flat().sort()),
  };
}

it.each(['before', 'after'] as const)('refreshes once when the tick burst arrives %s the Next Day response', async (when) => {
  const { advance, burst, expectRefreshes } = await renderRefreshDashboard();
  fireEvent.click(screen.getByRole('button', { name: 'Next Day' }));
  if (when === 'before') await act(async () => burst(2));
  await act(async () => advance.resolve(Response.json({ current_tick: 2 })));
  if (when === 'after') await act(async () => burst(2));
  expectRefreshes(1);
});

it('refreshes once for an external tick and its completed shows', async () => {
  const { burst, expectRefreshes } = await renderRefreshDashboard();
  await act(async () => burst(2));
  expectRefreshes(1);
});

it('refreshes on reconnect and when a show arrives without a tick after reconnect', async () => {
  const { burst, emit, reconnect, expectRefreshes } = await renderRefreshDashboard();
  await act(async () => burst(2));
  await act(reconnect);
  expectRefreshes(2);
  await act(async () => emit('show_completed'));
  expectRefreshes(3);
});

it('coalesces genuinely newer requests during a load into one trailing refresh', async () => {
  const { blockRefresh, burst, emit, expectRefreshes } = await renderRefreshDashboard();
  const unblock = blockRefresh();
  await act(async () => burst(2));
  await act(async () => { burst(3); burst(4); });
  expectRefreshes(1);
  await act(async () => unblock());
  expectRefreshes(2);
  await act(async () => emit('show_completed'));
  expectRefreshes(2);
});

it.each([10, 100])('refreshes after a non-increasing socket tick resets coverage to %i', async (tick) => {
  const { blockRefresh, burst, expectRefreshes } = await renderRefreshDashboard();
  const unblock = blockRefresh();
  await act(async () => burst(100));
  await act(async () => burst(tick));
  expectRefreshes(1);
  await act(async () => unblock());
  expectRefreshes(2);
  await act(async () => burst(tick + 1));
  expectRefreshes(3);
});

it('refreshes after Next Day without a socket notification', async () => {
  const { advance, expectRefreshes } = await renderRefreshDashboard();
  fireEvent.click(screen.getByRole('button', { name: 'Next Day' }));
  await act(async () => advance.resolve(Response.json({ current_tick: 2 })));
  expectRefreshes(1);
});

it('retries a failed dashboard load on a later completed show for the same tick', async () => {
  const { blockRefresh, burst, emit, expectRefreshes } = await renderRefreshDashboard();
  const unblock = blockRefresh();
  await act(async () => burst(2));
  await act(async () => emit('show_completed'));
  expectRefreshes(1);
  await act(async () => unblock(Response.json({ message: 'Could not load federation' }, { status: 500 })));
  expect(screen.getByText('Could not load federation')).toBeTruthy();
  expectRefreshes(1);
  await act(async () => emit('show_completed'));
  expectRefreshes(2);
  await act(async () => emit('show_completed'));
  expectRefreshes(2);
});

it('still refreshes for malformed ticks and for deferred events when Next Day fails', async () => {
  const { advance, burst, emit, expectRefreshes } = await renderRefreshDashboard();
  await act(async () => emit('tick', 'unknown'));
  expectRefreshes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Next Day' }));
  await act(async () => burst(2));
  expectRefreshes(1);
  await act(async () => advance.resolve(Response.json({ message: 'Could not advance' }, { status: 500 })));
  expect(screen.getByText('Could not advance')).toBeTruthy();
  expectRefreshes(2);
});
