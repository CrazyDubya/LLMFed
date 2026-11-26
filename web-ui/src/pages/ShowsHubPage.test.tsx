// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
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
