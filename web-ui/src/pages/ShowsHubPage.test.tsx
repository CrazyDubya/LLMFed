// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
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
      '/worlds/world-1/shows?limit=100': [completed, upcoming],
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
