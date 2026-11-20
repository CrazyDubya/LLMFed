import { describe, expect, it } from 'vitest';
import { formatMatchup, type MatchParticipant } from './matchup';

const participant = (name: string, team: number | null, role = 'competitor'): MatchParticipant => ({
  wrestler_id: name.toLowerCase(), name, role, team,
});

describe('formatMatchup', () => {
  it('joins singles competitors with vs', () => {
    expect(formatMatchup([participant('Ace', null), participant('Blaze', null)])).toBe('Ace vs Blaze');
  });

  it('groups tag partners by team', () => {
    expect(formatMatchup([
      participant('Ace', 0), participant('Blaze', 0), participant('Cole', 1), participant('Dax', 1),
    ])).toBe('Ace & Blaze vs Cole & Dax');
  });

  it('leaves out non-competitors and returns empty for no participants', () => {
    expect(formatMatchup([participant('Ace', null), participant('Ref', null, 'referee'),
      participant('Blaze', null)])).toBe('Ace vs Blaze');
    expect(formatMatchup([])).toBe('');
  });
});
