// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it('tabs to completed and upcoming show cards and opens the focused show with Enter', async () => {
  const completed = { id: 'summit-showdown', name: 'Summit Showdown', show_type: 'ppv', is_completed: true };
  const upcoming = { id: 'friday-night-live', name: 'Friday Night Live', show_type: 'weekly', is_completed: false };
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'booker', username: 'booker' },
      '/worlds/world-1/shows?status=all&limit=25&offset=0&include_counts=true': {
        shows: [completed, upcoming],
        counts: { all: 2, completed: 1, upcoming: 1 },
      },
      '/scheduler/status': { running: false },
      '/game/shows/friday-night-live/card': { show: upcoming, segments: [] },
    };
    return Response.json(responses[path] ?? []);
  }));
  vi.stubGlobal('WebSocket', class { close() {} });
  localStorage.setItem('token', 'test-token');
  localStorage.setItem('worldId', 'world-1');
  window.history.replaceState(null, '', '/shows');
  const user = userEvent.setup();

  render(<App />);
  await screen.findByRole('heading', { name: completed.name });

  for (const name of ['Back', /All/, /Completed/, /Upcoming/]) {
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('button', { name }));
  }
  await user.tab();
  expect(document.activeElement?.textContent).toContain(completed.name);
  expect(document.activeElement).toBe(screen.getByRole('link', { name: /Summit Showdown/ }));

  await user.tab();
  expect(document.activeElement).toBe(screen.getByRole('link', { name: /Friday Night Live/ }));
  await user.keyboard('{Enter}');

  await screen.findByRole('heading', { level: 1, name: upcoming.name });
  expect(window.location.pathname).toBe('/show/friday-night-live');
});

it('shows world-wide counts and reaches the last completed show', async () => {
  const shows = Array.from({ length: 205 }, (_, index) => ({
    id: String(205 - index),
    name: `Show ${205 - index}`,
    show_type: 'weekly',
    is_completed: index >= 101,
  }));
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    const url = new URL(path, window.location.origin);
    if (url.pathname === '/game/auth/me') return Response.json({ id: 'shows-user' });
    if (url.pathname === '/scheduler/status') return Response.json({ running: false });
    const limit = Number(url.searchParams.get('limit'));
    const offset = Number(url.searchParams.get('offset'));
    const status = url.searchParams.get('status');
    const filtered = shows.filter(show => status === 'completed' ? show.is_completed
      : status === 'upcoming' ? !show.is_completed : true);
    const page = filtered.slice(offset, offset + limit);
    return Response.json(url.searchParams.has('include_counts')
      ? { shows: page, counts: { all: 205, completed: 104, upcoming: 101 } }
      : page);
  }));
  vi.stubGlobal('WebSocket', class { close() {} });
  localStorage.setItem('token', 'shows-test-token');
  localStorage.setItem('worldId', 'shows-test-world');
  window.history.replaceState(null, '', '/shows');
  render(<App />);

  expect(await screen.findByRole('button', { name: 'All (205)' })).toBeDefined();
  expect(screen.getByRole('button', { name: 'Upcoming (101)' })).toBeDefined();
  expect(screen.getByRole('heading', { name: 'Show 205' })).toBeDefined();
  fireEvent.click(screen.getByRole('button', { name: 'Completed (104)' }));
  expect(await screen.findByRole('heading', { name: 'Show 104' })).toBeDefined();
  for (const first of [79, 54, 29, 4]) {
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByRole('heading', { name: `Show ${first}` })).toBeDefined();
  }
  expect(screen.getByRole('heading', { name: 'Show 1' })).toBeDefined();
  expect((screen.getByRole('button', { name: 'Next' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Upcoming (101)' }));
  expect(await screen.findByRole('heading', { name: 'Show 205' })).toBeDefined();
});

it('retries the requested page after a Next request fails', async () => {
  let nextRequests = 0;
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    const url = new URL(path, window.location.origin);
    if (url.pathname === '/game/auth/me') return Response.json({ id: 'shows-user' });
    if (url.pathname === '/scheduler/status') return Response.json({ running: false });
    const offset = Number(url.searchParams.get('offset'));
    if (offset === 25 && ++nextRequests === 1) {
      return Response.json({ message: 'Temporarily unavailable' }, { status: 503 });
    }
    return Response.json({
      shows: [{ id: String(offset), name: `Show at offset ${offset}`, show_type: 'weekly' }],
      counts: { all: 26, completed: 0, upcoming: 26 },
    });
  }));
  vi.stubGlobal('WebSocket', class { close() {} });
  localStorage.setItem('token', 'shows-test-token');
  localStorage.setItem('worldId', 'shows-retry-world');
  window.history.replaceState(null, '', '/shows');
  render(<App />);

  expect(await screen.findByRole('heading', { name: 'Show at offset 0' })).toBeDefined();
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect((await screen.findByRole('alert')).textContent).toContain('Temporarily unavailable');
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByRole('heading', { name: 'Show at offset 25' })).toBeDefined();
  expect(screen.getByText('Page 2 of 2')).toBeDefined();
  expect(screen.queryByRole('alert')).toBeNull();
  expect(nextRequests).toBe(2);
});
