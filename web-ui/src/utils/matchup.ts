export interface MatchParticipant {
  wrestler_id: string;
  name: string;
  role: string;
  team: number | null;
}

/** "A vs B" for singles, "A & B vs C & D" when participants carry team numbers. */
export function formatMatchup(participants: MatchParticipant[]): string {
  const sides = new Map<string, string[]>();
  for (const p of participants) {
    if (p.role !== 'competitor') continue;
    const key = p.team === null ? `solo:${p.wrestler_id}` : `team:${p.team}`;
    sides.set(key, [...(sides.get(key) ?? []), p.name]);
  }
  return [...sides.values()].map(names => names.join(' & ')).join(' vs ');
}
