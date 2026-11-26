// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import ShowViewerPage from './ShowViewerPage';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderCard(isCompleted: boolean) {
  const responses: Record<string, unknown> = {
    '/game/shows/booked-show/card': {
      show: { name: 'Booked Show', is_completed: isCompleted },
      segments: [
        { id: 'first', segment_type: 'match', match_id: 'unrun', participants: [] },
        ...(isCompleted
          ? [{ id: 'second', segment_type: 'match', match_id: 'finished', participants: [] }]
          : []),
      ],
    },
    '/game/matches/unrun': { id: 'unrun', match_type: 'singles', is_completed: false },
    '/game/matches/finished': {
      id: 'finished', match_type: 'singles', is_completed: true,
      finish_description: 'Healthy A wins by pinfall.', finish_type: 'pinfall',
    },
  };
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path in responses
    ? Response.json(responses[path])
    : new Response(null, { status: 404 })));

  render(
    <MemoryRouter initialEntries={['/show/booked-show']}>
      <Routes>
        <Route path="/show/:showId" element={<ShowViewerPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

it('labels an incomplete bout on a completed show as Did not run and keeps the finished bout result', async () => {
  renderCard(true);

  expect(await screen.findByRole('heading', { name: 'Show Complete' })).toBeDefined();
  expect(screen.getByText('Did not run')).toBeDefined();
  expect(screen.queryByText('Awaiting simulation...')).toBeNull();
  expect(screen.getByText('Healthy A wins by pinfall.')).toBeDefined();
  expect(screen.getByRole('button', { name: 'Full Play-by-Play' })).toBeDefined();
});

it('still labels an incomplete bout on an upcoming show as awaiting simulation', async () => {
  renderCard(false);

  expect(await screen.findByText('Awaiting simulation...')).toBeDefined();
  expect(screen.queryByText('Did not run')).toBeNull();
});
