// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it.each([[], [{ id: 'belt', name: 'World Championship' }]].map(championships => ({ championships })))(
  'blocks a title booking before a championship is selected (championships: $championships)',
  async ({ championships }) => {
    const bookMatch = vi.fn();
    vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
      const responses: Record<string, unknown> = {
        '/game/auth/me': { id: 'user', username: 'promoter' },
        '/game/shows/show/card': { show: { name: 'Test Show' }, segments: [] },
        '/game/federations/fed/roster': [
          { id: 'a', name: 'First Wrestler' },
          { id: 'b', name: 'Second Wrestler' },
        ],
        '/game/federations/fed/championships': championships,
      };
      if (path === '/game/shows/show/matches') bookMatch(JSON.parse(options.body as string));
      return Response.json(responses[path] ?? {});
    }));
    Object.entries({ token: 'test-token', worldId: 'world', federationId: 'fed', playerType: 'promoter' })
      .forEach(([key, value]) => localStorage.setItem(key, value));
    window.history.replaceState(null, '', '/show/show/book');
    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: /First Wrestler/ }));
    fireEvent.click(screen.getByRole('button', { name: /Second Wrestler/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Title Match' }));
    const submit = screen.getByRole<HTMLButtonElement>('button', { name: /Book Match/ });

    expect(submit.disabled).toBe(true);
    expect(screen.getByRole('alert').textContent).toBe(championships.length
      ? 'Select a championship to book a title match.'
      : 'No active championships are available for a title match.');
    fireEvent.click(submit);
    expect(bookMatch).not.toHaveBeenCalled();

    if (championships.length) {
      fireEvent.change(screen.getByRole('combobox', { name: 'Championship' }), { target: { value: 'belt' } });
      expect(submit.disabled).toBe(false);
      fireEvent.click(submit);
      expect(bookMatch).toHaveBeenCalledWith(expect.objectContaining({
        is_title_match: true,
        championship_id: 'belt',
      }));
      await screen.findByRole('checkbox', { name: 'Title Match', checked: false });
    } else {
      fireEvent.click(screen.getByRole('checkbox', { name: 'Title Match' }));
      expect(submit.disabled).toBe(false);
    }
  },
);
