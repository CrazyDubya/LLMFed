// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it('explains the tag team requirement and only lets four selected wrestlers be booked', async () => {
  const roster = ['Avery', 'Blake', 'Casey', 'Drew', 'Ellis'].map((name, index) => ({ id: String(index), name }));
  const bookMatch = vi.fn();
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    const responses: Record<string, unknown> = {
      '/game/auth/me': { id: 'user', username: 'promoter' },
      '/game/shows/show/card': { show: { name: 'Test Show' }, segments: [] },
      '/game/federations/fed/roster': roster,
      '/game/federations/fed/championships': [],
    };
    if (path === '/game/shows/show/matches') bookMatch(JSON.parse(options.body as string));
    return Response.json(responses[path] ?? {});
  }));
  Object.entries({ token: 'test-token', worldId: 'world', federationId: 'fed', playerType: 'promoter' })
    .forEach(([key, value]) => localStorage.setItem(key, value));
  window.history.replaceState(null, '', '/show/show/book');
  render(<App />);

  fireEvent.change(await screen.findByDisplayValue('Singles'), { target: { value: 'tag_team' } });

  const [first, second, third, fourth, fifth] = roster.map(({ name }) =>
    screen.getByRole<HTMLButtonElement>('button', { name: new RegExp(name) }),
  );
  fireEvent.click(first);
  fireEvent.click(second);
  const submit = screen.getByRole<HTMLButtonElement>('button', { name: 'Book Match (2 wrestlers)' });
  expect(submit.disabled).toBe(true);
  expect(screen.getByRole('group', {
    name: /Participants/,
    description: 'Select exactly 4 wrestlers for a tag team match.',
  })).toBeTruthy();
  fireEvent.click(submit);
  expect(bookMatch).not.toHaveBeenCalled();

  fireEvent.click(third);
  expect(submit.disabled).toBe(true);
  fireEvent.click(fourth);
  expect(submit.disabled).toBe(false);
  expect(fifth.disabled).toBe(true);
  fireEvent.click(fifth);
  expect(submit.textContent).toBe('Book Match (4 wrestlers)');

  fireEvent.click(fourth);
  expect(submit.disabled).toBe(true);
  expect(fifth.disabled).toBe(false);
  fireEvent.click(fifth);
  expect(submit.disabled).toBe(false);
  fireEvent.click(submit);
  expect(bookMatch).toHaveBeenCalledWith(expect.objectContaining({
    match_type: 'tag_team',
    participant_ids: ['0', '1', '2', '4'],
  }));
  await screen.findByRole('button', { name: 'Book Match (0 wrestlers)' });
});
