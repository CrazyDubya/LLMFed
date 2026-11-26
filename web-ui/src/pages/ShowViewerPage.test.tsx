// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import ShowViewerPage from './ShowViewerPage';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const segment = (n: number) => ({
  id: `segment-${n}`,
  position: n,
  segment_type: 'match',
  match_id: `match-${n}`,
  description: null,
  planned_duration_minutes: 10,
  actual_duration_minutes: 10,
  rating: null,
  crowd_reaction: null,
  is_completed: true,
  participants: [],
});

const match = (n: number) => ({
  id: `match-${n}`,
  match_type: 'singles',
  stipulation: null,
  is_title_match: false,
  winner_id: null,
  finish_type: 'pinfall',
  finish_description: `Finish of match ${n}`,
  match_rating: null,
  crowd_heat: 50,
  duration_minutes: 10,
  is_completed: true,
});

it('requests every match at once and keeps the ones that load', async () => {
  const pending = new Map<string, (response: Response) => void>();
  vi.stubGlobal('fetch', vi.fn((path: string) => {
    if (path === '/game/shows/show-1/card') {
      return Promise.resolve(Response.json({
        show: { name: 'Parallel Show' },
        segments: [segment(1), segment(2), segment(3)],
      }));
    }
    return new Promise<Response>(resolve => pending.set(path, resolve));
  }));

  render(
    <MemoryRouter initialEntries={['/show/show-1']}>
      <Routes>
        <Route path="/show/:showId" element={<ShowViewerPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => expect([...pending.keys()]).toEqual([
    '/game/matches/match-1', '/game/matches/match-2', '/game/matches/match-3',
  ]));
  pending.get('/game/matches/match-1')!(Response.json(match(1)));
  pending.get('/game/matches/match-2')!(Response.json({ detail: 'Match not found' }, { status: 404 }));
  pending.get('/game/matches/match-3')!(Response.json(match(3)));

  expect(await screen.findByText('Finish of match 1')).toBeDefined();
  expect(screen.getByText('Finish of match 3')).toBeDefined();
  expect(screen.queryByText('Finish of match 2')).toBeNull();
  expect(screen.getByRole('heading', { name: 'Parallel Show' })).toBeDefined();
});
