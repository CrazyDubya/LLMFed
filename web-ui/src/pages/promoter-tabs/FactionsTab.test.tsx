// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import FactionsTab from './FactionsTab';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it('requires the leader and a distinct additional founding member', async () => {
  const createStable = vi.spyOn(api, 'createStable').mockResolvedValue({});
  const roster = [
    { id: 'atlas', name: 'Atlas Stone' },
    { id: 'blake', name: 'Blake Mercer' },
  ].map(w => ({ ...w, popularity: 50, alignment: 'heel', condition: 100, is_injured: false, is_npc: true }));

  function Form() {
    const [formData, setFormData] = useState({});
    const [showStableForm, setShowStableForm] = useState(true);
    return (
      <FactionsTab
        worldId="world-1"
        roster={roster}
        stables={[]}
        stableMemberMap={{}}
        expandedStable={null}
        setExpandedStable={() => {}}
        showStableForm={showStableForm}
        setShowStableForm={setShowStableForm}
        formData={formData}
        setFormData={setFormData}
        loadData={async () => {}}
        advanceDay={async () => {}}
        setError={() => {}}
      />
    );
  }

  render(<Form />);
  fireEvent.change(screen.getByPlaceholderText('The Wolfpack'), { target: { value: 'The Wolfpack' } });
  const leader = screen.getByRole('option', { name: 'Select leader...' }).closest('select');
  if (!leader) throw new Error('Leader picker not found');
  const members = screen.getByRole('listbox');
  const submit = screen.getByRole('button', { name: 'Create Faction' }) as HTMLButtonElement;

  fireEvent.change(leader, { target: { value: 'atlas' } });
  expect(submit.disabled).toBe(true);
  expect(screen.getByText(/at least 2 founding members: the leader and at least one additional member/i)).toBeDefined();
  fireEvent.click(submit);
  expect(createStable).not.toHaveBeenCalled();

  fireEvent.change(members, { target: { value: 'blake' } });
  expect(submit.disabled).toBe(false);
  fireEvent.change(leader, { target: { value: 'blake' } });
  expect(submit.disabled).toBe(true);

  fireEvent.change(members, { target: { value: 'atlas' } });
  expect(submit.disabled).toBe(false);
  fireEvent.click(submit);
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Create Faction' })).toBeNull());
  expect(createStable).toHaveBeenCalledExactlyOnceWith('world-1', expect.objectContaining({
    leader_id: 'blake',
    founding_member_ids: ['blake', 'atlas'],
  }));
});
