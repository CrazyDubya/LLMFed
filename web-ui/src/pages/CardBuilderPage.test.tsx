// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it.each([
  { change: 'remove the winner', participants: ['b', 'c'], matchType: 'singles', winnerId: undefined },
  { change: 'change the match type', participants: ['a', 'b', 'c'], matchType: 'triple_threat', winnerId: undefined },
  { change: 'remove the opponent', participants: ['a', 'c'], matchType: 'singles', winnerId: 'a' },
])('submits the displayed planned winner after you $change', async ({ change, participants, matchType, winnerId }) => {
  const wrestlers = [
    { id: 'a', name: 'First Wrestler' },
    { id: 'b', name: 'Second Wrestler' },
    { id: 'c', name: 'Third Wrestler' },
  ];
  const bookMatch = vi.fn();
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'user', username: 'promoter' },
      '/game/shows/show/card': { show: { name: 'Test Show' }, segments: [] },
      '/game/federations/fed/roster': wrestlers,
      '/game/federations/fed/championships': [],
    };
    if (path === '/game/shows/show/matches') bookMatch(JSON.parse(options.body as string));
    return Response.json(responses[path] ?? {});
  }));
  Object.entries({ token: 'test-token', worldId: 'world', federationId: 'fed', playerType: 'promoter' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/show/show/book');
  render(<App />);

  const firstWrestler = await screen.findByRole('button', { name: /First Wrestler/ });
  const secondWrestler = screen.getByRole('button', { name: /Second Wrestler/ });
  fireEvent.click(firstWrestler);
  fireEvent.click(secondWrestler);
  fireEvent.change(screen.getByRole('option', { name: 'Let it play out' }).closest('select')!, {
    target: { value: 'a' },
  });
  expect(screen.getByRole<HTMLOptionElement>('option', { name: 'First Wrestler' }).selected).toBe(true);

  if (change === 'change the match type') {
    fireEvent.change(screen.getByRole('option', { name: 'Singles' }).closest('select')!, {
      target: { value: 'triple_threat' },
    });
    fireEvent.click(firstWrestler);
    fireEvent.click(secondWrestler);
  } else {
    fireEvent.click(change === 'remove the winner' ? firstWrestler : secondWrestler);
  }
  fireEvent.click(screen.getByRole('button', { name: /Third Wrestler/ }));

  const displayedWinner = winnerId ? 'First Wrestler' : 'Let it play out';
  const selected = screen.getByRole<HTMLOptionElement>('option', { name: displayedWinner }).selected;
  fireEvent.click(screen.getByRole('button', { name: /Book Match/ }));
  await screen.findByRole('button', { name: 'Book Match (0 wrestlers)' });

  expect(bookMatch).toHaveBeenCalledWith(expect.objectContaining({
    participant_ids: participants,
    match_type: matchType,
  }));
  expect(bookMatch.mock.calls[0][0].planned_winner_id).toBe(winnerId);
  expect(selected).toBe(true);
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
