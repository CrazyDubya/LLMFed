import { useState, useEffect } from 'react';
import { useGame } from '../context/GameContext';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

interface Wrestler {
  id: string; name: string; popularity: number; alignment: string;
  condition: number; is_injured: boolean; is_npc: boolean;
}

type TabKey = 'roster' | 'freeagents' | 'shows' | 'titles' | 'storylines' | 'factions' | 'relationships' | 'news';

const TAB_LABELS: Record<TabKey, string> = {
  roster: 'Roster',
  freeagents: 'Free Agents',
  shows: 'Shows',
  titles: 'Titles',
  storylines: 'Storylines',
  factions: 'Factions',
  relationships: 'Relationships',
  news: 'News',
};

function AlignmentBadge({ alignment }: { alignment: string }) {
  const cls = alignment === 'face' ? 'bg-blue-900/50 text-blue-300'
    : alignment === 'heel' ? 'bg-red-900/50 text-red-300'
    : 'bg-gray-800 text-gray-300';
  return <span className={`px-2 py-0.5 rounded text-xs ${cls}`}>{alignment}</span>;
}

function HeatBar({ value, label }: { value: number; label?: string }) {
  const color = value >= 70 ? 'bg-red-500' : value >= 40 ? 'bg-amber-500' : 'bg-gray-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 bg-gray-800 rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs text-gray-400">{label || value}</span>
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  const colors: Record<string, string> = {
    leader: 'bg-amber-900/50 text-amber-300',
    enforcer: 'bg-red-900/50 text-red-300',
    mouthpiece: 'bg-purple-900/50 text-purple-300',
    lieutenant: 'bg-cyan-900/50 text-cyan-300',
    member: 'bg-gray-800 text-gray-300',
    recruit: 'bg-gray-700 text-gray-400',
    protagonist: 'bg-blue-900/50 text-blue-300',
    antagonist: 'bg-red-900/50 text-red-300',
    ally: 'bg-green-900/50 text-green-300',
    manager: 'bg-purple-900/50 text-purple-300',
  };
  return <span className={`px-2 py-0.5 rounded text-xs ${colors[role] || 'bg-gray-800 text-gray-300'}`}>{role}</span>;
}

export default function PromoterDashboard() {
  const { worldId, federationId, clearGame } = useGame();
  const navigate = useNavigate();

  const [federation, setFederation] = useState<any>(null);
  const [roster, setRoster] = useState<Wrestler[]>([]);
  const [freeAgents, setFreeAgents] = useState<Wrestler[]>([]);
  const [shows, setShows] = useState<any[]>([]);
  const [championships, setChampionships] = useState<any[]>([]);
  const [narrative, setNarrative] = useState<any[]>([]);
  const [worldData, setWorldData] = useState<any>(null);
  const [storylines, setStorylines] = useState<any[]>([]);
  const [stables, setStables] = useState<any[]>([]);
  const [managerBonds, setManagerBonds] = useState<any[]>([]);
  const [managers, setManagers] = useState<any[]>([]);
  const [tab, setTab] = useState<TabKey>('roster');
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState('');
  const [expandedStable, setExpandedStable] = useState<string | null>(null);

  const loadData = async () => {
    if (!worldId || !federationId) return;
    try {
      const [fed, rost, agents, sh, champs, narr, world, sls, stbs, bonds, mgrs] = await Promise.all([
        api.getFederation(federationId),
        api.getRoster(federationId),
        api.listFreeAgents(worldId),
        api.getShows(federationId),
        api.getChampionships(federationId),
        api.getNarrative(worldId, 20),
        api.getWorld(worldId),
        api.listStorylines(worldId),
        api.listStables(worldId, federationId).catch(() => []),
        api.listManagerBonds(worldId).catch(() => []),
        api.listManagers(worldId, federationId).catch(() => []),
      ]);
      setFederation(fed);
      setRoster(rost);
      setFreeAgents(agents);
      setShows(sh);
      setChampionships(champs);
      setNarrative(narr);
      setWorldData(world);
      setStorylines(sls);
      setStables(stbs);
      setManagerBonds(bonds);
      setManagers(mgrs);
    } catch (err: any) {
      setError(err.message);
    }
  };

  useEffect(() => { loadData(); }, [worldId, federationId]);

  const advanceDay = async (days: number = 1) => {
    if (!worldId) return;
    setAdvancing(true);
    try {
      await api.advanceWorld(worldId, days);
      await loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setAdvancing(false);
    }
  };

  const signWrestler = async (wrestlerId: string) => {
    if (!worldId || !federationId) return;
    try {
      await api.submitAction(worldId, 'sign_wrestler', {
        wrestler_id: wrestlerId,
        federation_id: federationId,
        salary_weekly: 2000,
      });
      await advanceDay(1);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const exitGame = () => {
    clearGame();
    navigate('/setup');
  };

  // Build lookup maps for roster enrichment
  const stableMemberMap: Record<string, { stableName: string; role: string }> = {};
  for (const s of stables) {
    for (const m of (s.members || [])) {
      stableMemberMap[m.wrestler_id] = { stableName: s.name, role: m.role };
    }
  }
  const managerMap: Record<string, string> = {};
  for (const b of managerBonds) {
    managerMap[b.client_wrestler_id] = b.manager_name;
  }

  if (!worldId || !federationId) {
    return <div className="p-8 text-center text-gray-400">No active game. <button onClick={() => navigate('/setup')} className="text-amber-400">Start a new game</button></div>;
  }

  return (
    <div className="min-h-screen bg-[#0f0f14]">
      {/* Header */}
      <header className="bg-[#1a1a24] border-b border-gray-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-amber-400">{federation?.name || 'Loading...'}</h1>
            <p className="text-sm text-gray-400">
              Promoter Mode | {worldData?.current_game_date || '...'} | Prestige: {federation?.prestige || 0}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-green-400">
              Budget: ${federation?.budget?.toLocaleString(undefined, { maximumFractionDigits: 0 }) || '0'}
            </span>
            <button
              onClick={() => advanceDay(1)}
              disabled={advancing}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 text-white rounded text-sm transition-colors"
            >
              {advancing ? 'Advancing...' : 'Next Day'}
            </button>
            <button
              onClick={() => advanceDay(7)}
              disabled={advancing}
              className="px-4 py-2 bg-amber-700 hover:bg-amber-600 disabled:bg-gray-700 text-white rounded text-sm transition-colors"
            >
              Next Week
            </button>
            <button onClick={exitGame} className="text-gray-500 hover:text-gray-300 text-sm">Exit</button>
          </div>
        </div>
      </header>

      {error && (
        <div className="max-w-7xl mx-auto px-6 mt-4">
          <div className="bg-red-900/30 border border-red-800 rounded p-3 text-red-400 text-sm">
            {error} <button onClick={() => setError('')} className="ml-2 text-red-300">dismiss</button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-6 mt-6">
        <div className="flex gap-1 mb-6 flex-wrap">
          {(Object.keys(TAB_LABELS) as TabKey[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-t text-sm ${tab === t ? 'bg-[#1a1a24] text-amber-400 border-t border-x border-gray-800' : 'text-gray-500 hover:text-gray-300'}`}
            >
              {TAB_LABELS[t]}
              {t === 'roster' && ` (${roster.length})`}
              {t === 'freeagents' && ` (${freeAgents.length})`}
              {t === 'factions' && stables.length > 0 && ` (${stables.length})`}
            </button>
          ))}
        </div>

        {/* ========== ROSTER TAB ========== */}
        {tab === 'roster' && (
          <div className="bg-[#1a1a24] rounded-lg border border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#0f0f14]">
                <tr className="text-gray-400">
                  <th className="text-left p-3">Name</th>
                  <th className="text-left p-3">Alignment</th>
                  <th className="text-left p-3">Faction</th>
                  <th className="text-left p-3">Manager</th>
                  <th className="text-center p-3">Popularity</th>
                  <th className="text-center p-3">Condition</th>
                  <th className="text-center p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {roster.map(w => {
                  const faction = stableMemberMap[w.id];
                  const mgr = managerMap[w.id];
                  return (
                    <tr key={w.id} className="border-t border-gray-800 hover:bg-[#0f0f14]/50">
                      <td className="p-3 text-white">{w.name}</td>
                      <td className="p-3"><AlignmentBadge alignment={w.alignment} /></td>
                      <td className="p-3">
                        {faction ? (
                          <span className="text-xs text-purple-300">
                            {faction.stableName} <RoleBadge role={faction.role} />
                          </span>
                        ) : <span className="text-xs text-gray-600">--</span>}
                      </td>
                      <td className="p-3">
                        {mgr ? <span className="text-xs text-cyan-300">{mgr}</span> : <span className="text-xs text-gray-600">--</span>}
                      </td>
                      <td className="p-3 text-center">
                        <div className="w-16 mx-auto bg-gray-800 rounded-full h-2">
                          <div className="bg-amber-500 h-2 rounded-full" style={{ width: `${w.popularity}%` }} />
                        </div>
                        <span className="text-xs text-gray-400">{w.popularity}</span>
                      </td>
                      <td className="p-3 text-center">
                        <span className={w.condition > 70 ? 'text-green-400' : w.condition > 40 ? 'text-yellow-400' : 'text-red-400'}>
                          {w.condition}%
                        </span>
                      </td>
                      <td className="p-3 text-center">
                        {w.is_injured ? <span className="text-red-400 text-xs">INJURED</span> : <span className="text-green-400 text-xs">Active</span>}
                      </td>
                    </tr>
                  );
                })}
                {roster.length === 0 && (
                  <tr><td colSpan={7} className="p-8 text-center text-gray-500">No wrestlers on roster. Sign some free agents!</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* ========== FREE AGENTS TAB ========== */}
        {tab === 'freeagents' && (
          <div className="bg-[#1a1a24] rounded-lg border border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#0f0f14]">
                <tr className="text-gray-400">
                  <th className="text-left p-3">Name</th>
                  <th className="text-left p-3">Alignment</th>
                  <th className="text-center p-3">Popularity</th>
                  <th className="text-center p-3">Condition</th>
                  <th className="text-center p-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {freeAgents.map(w => (
                  <tr key={w.id} className="border-t border-gray-800 hover:bg-[#0f0f14]/50">
                    <td className="p-3 text-white">{w.name}</td>
                    <td className="p-3"><AlignmentBadge alignment={w.alignment} /></td>
                    <td className="p-3 text-center text-gray-300">{w.popularity}</td>
                    <td className="p-3 text-center text-gray-300">{w.condition}%</td>
                    <td className="p-3 text-center">
                      <button onClick={() => signWrestler(w.id)} className="px-3 py-1 bg-green-700 hover:bg-green-600 text-white rounded text-xs transition-colors">Sign</button>
                    </td>
                  </tr>
                ))}
                {freeAgents.length === 0 && (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">No free agents available</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* ========== SHOWS TAB ========== */}
        {tab === 'shows' && (
          <div className="space-y-3">
            <div className="flex justify-end mb-2">
              <button
                onClick={async () => {
                  if (!worldId || !federationId) return;
                  try {
                    const nextDate = worldData?.current_game_date || '2026-01-01';
                    await api.createShow(federationId, {
                      name: `${federation?.short_name || 'My'} Live Event`,
                      show_type: 'weekly',
                      venue: `${federation?.home_region || 'Local'} Arena`,
                      capacity: 5000,
                      game_date: nextDate,
                    });
                    await loadData();
                  } catch (err: any) { setError(err.message); }
                }}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded text-sm"
              >
                Book New Show
              </button>
            </div>
            {shows.map(s => (
              <div key={s.id} className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4 flex items-center justify-between">
                <div>
                  <h3 className="text-white font-medium">{s.name}</h3>
                  <p className="text-sm text-gray-400">{s.game_date} | {s.venue} | {s.show_type}</p>
                </div>
                <div className="flex items-center gap-3">
                  {s.is_completed ? (
                    <div className="text-right">
                      <div className="text-amber-400">Rating: {s.overall_rating}</div>
                      <div className="text-sm text-gray-400">Attendance: {s.attendance?.toLocaleString()}</div>
                      {s.gate_revenue && <div className="text-sm text-green-400">${s.gate_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>}
                    </div>
                  ) : (
                    <button onClick={() => navigate(`/show/${s.id}/book`)} className="px-3 py-1 bg-purple-700 hover:bg-purple-600 text-white rounded text-xs">Build Card</button>
                  )}
                  <button onClick={() => navigate(`/show/${s.id}`)} className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-white rounded text-xs">View</button>
                </div>
              </div>
            ))}
            {shows.length === 0 && <div className="text-center text-gray-500 py-8">No shows yet. Book your first show!</div>}
          </div>
        )}

        {/* ========== CHAMPIONSHIPS TAB ========== */}
        {tab === 'titles' && (
          <div className="space-y-3">
            {championships.map(c => (
              <div key={c.id} className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4">
                <h3 className="text-amber-400 font-medium">{c.name}</h3>
                <p className="text-sm text-gray-400">
                  Prestige: {c.prestige} | Defenses: {c.defenses}
                  {c.current_holder_id ? '' : ' | VACANT'}
                </p>
              </div>
            ))}
            {championships.length === 0 && <div className="text-center text-gray-500 py-8">No championships</div>}
          </div>
        )}

        {/* ========== STORYLINES TAB (enhanced with wrestler names) ========== */}
        {tab === 'storylines' && (
          <div className="space-y-3">
            {storylines.map(sl => (
              <div key={sl.id} className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-white font-medium">{sl.name}</h3>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      sl.storyline_type === 'faction_war' ? 'bg-purple-900/50 text-purple-300' :
                      sl.storyline_type === 'power_struggle' ? 'bg-orange-900/50 text-orange-300' :
                      sl.storyline_type === 'manager_betrayal' ? 'bg-cyan-900/50 text-cyan-300' :
                      'bg-gray-700 text-gray-300'
                    }`}>{sl.storyline_type.replace(/_/g, ' ')}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      sl.status === 'climax' ? 'bg-red-900/50 text-red-300' :
                      sl.status === 'active' ? 'bg-green-900/50 text-green-300' :
                      sl.status === 'brewing' ? 'bg-yellow-900/50 text-yellow-300' :
                      'bg-gray-800 text-gray-300'
                    }`}>{sl.status}</span>
                    <HeatBar value={sl.heat} label={`Heat: ${sl.heat}`} />
                  </div>
                </div>
                {sl.description && <p className="text-sm text-gray-300 mb-2">{sl.description}</p>}
                {sl.participants && sl.participants.length > 0 && (
                  <div className="mt-2 flex gap-2 flex-wrap">
                    {sl.participants.map((p: any, i: number) => (
                      <span key={i} className="flex items-center gap-1">
                        <span className="text-xs text-white">{p.wrestler_name || 'Unknown'}</span>
                        <RoleBadge role={p.role} />
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {storylines.length === 0 && (
              <div className="text-center text-gray-500 py-8">No storylines yet. Advance time for feuds to develop!</div>
            )}
          </div>
        )}

        {/* ========== FACTIONS TAB (NEW) ========== */}
        {tab === 'factions' && (
          <div className="space-y-4">
            {stables.map(s => (
              <div key={s.id} className="bg-[#1a1a24] rounded-lg border border-gray-800 overflow-hidden">
                <div
                  className="p-4 cursor-pointer hover:bg-[#1e1e2a] transition-colors"
                  onClick={() => setExpandedStable(expandedStable === s.id ? null : s.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <h3 className="text-white font-bold text-lg">{s.name}</h3>
                      {s.short_name && <span className="text-xs text-gray-500">({s.short_name})</span>}
                      <AlignmentBadge alignment={s.alignment} />
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="flex items-center gap-3">
                          <HeatBar value={s.heat} label={`Heat: ${s.heat}`} />
                          <HeatBar value={s.prestige} label={`Prestige: ${s.prestige}`} />
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`text-xs ${s.cohesion >= 60 ? 'text-green-400' : s.cohesion >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                            Cohesion: {s.cohesion}%
                          </span>
                          <span className="text-xs text-gray-500">{(s.members || []).length} members</span>
                        </div>
                      </div>
                      <span className="text-gray-500">{expandedStable === s.id ? '\u25B2' : '\u25BC'}</span>
                    </div>
                  </div>
                  {s.catchphrase && <p className="text-sm text-gray-400 italic mt-1">"{s.catchphrase}"</p>}
                  {s.manager_name && <p className="text-xs text-cyan-400 mt-1">Managed by: {s.manager_name}</p>}
                </div>

                {expandedStable === s.id && (
                  <div className="border-t border-gray-800 p-4">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-gray-400 text-xs">
                          <th className="text-left pb-2">Member</th>
                          <th className="text-left pb-2">Role</th>
                          <th className="text-center pb-2">Loyalty</th>
                          <th className="text-center pb-2">Influence</th>
                          <th className="text-left pb-2">Joined</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(s.members || []).map((m: any) => (
                          <tr key={m.wrestler_id} className="border-t border-gray-800/50">
                            <td className="py-2 text-white">{m.wrestler_name}</td>
                            <td className="py-2"><RoleBadge role={m.role} /></td>
                            <td className="py-2 text-center">
                              <span className={m.loyalty >= 60 ? 'text-green-400' : m.loyalty >= 30 ? 'text-yellow-400' : 'text-red-400'}>
                                {m.loyalty}
                              </span>
                            </td>
                            <td className="py-2 text-center text-gray-300">{m.influence}</td>
                            <td className="py-2 text-xs text-gray-500">{m.joined_date || '--'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {s.group_finisher_name && (
                      <p className="mt-3 text-xs text-amber-400">Group Finisher: {s.group_finisher_name}</p>
                    )}
                  </div>
                )}
              </div>
            ))}
            {stables.length === 0 && (
              <div className="text-center text-gray-500 py-8">No factions formed yet. Create stables to unlock faction warfare!</div>
            )}
          </div>
        )}

        {/* ========== RELATIONSHIPS TAB (NEW) ========== */}
        {tab === 'relationships' && (
          <div className="space-y-6">
            {/* Manager/Valet Bonds */}
            <div>
              <h3 className="text-lg font-semibold text-amber-400 mb-3">Manager &amp; Valet Bonds</h3>
              {managerBonds.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {managerBonds.map((b: any) => (
                    <div key={b.id} className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div>
                          <span className="text-cyan-300 font-medium">{b.manager_name}</span>
                          <span className="text-gray-500 mx-2">&rarr;</span>
                          <span className="text-white font-medium">{b.client_name}</span>
                        </div>
                        <RoleBadge role={b.role} />
                      </div>
                      <div className="flex items-center gap-4 text-xs text-gray-400">
                        <span>Effectiveness: {b.effectiveness}%</span>
                        <span>Specialization: {b.specialization}</span>
                        <span>+{b.charisma_bonus} CHA</span>
                        <span>+{b.heat_bonus} Heat</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No manager bonds. Assign managers to wrestlers to boost their presence!</p>
              )}
            </div>

            {/* Managers roster */}
            {managers.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-amber-400 mb-3">Available Managers</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {managers.map((m: any) => (
                    <div key={m.id} className="bg-[#1a1a24] rounded-lg border border-gray-800 p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-white font-medium">{m.name}</span>
                        <AlignmentBadge alignment={m.alignment} />
                      </div>
                      <div className="text-xs text-gray-400">
                        <span className="capitalize">{m.archetype.replace(/_/g, ' ')}</span>
                        <span className="mx-1">|</span>
                        <span>CHA: {m.charisma}</span>
                        <span className="mx-1">|</span>
                        <span>Mic: {m.mic_skill}</span>
                        <span className="mx-1">|</span>
                        <span>Pop: {m.popularity}</span>
                      </div>
                      {m.catchphrase && <p className="text-xs text-gray-500 italic mt-1">"{m.catchphrase}"</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========== NEWS TAB (enhanced with event type colors) ========== */}
        {tab === 'news' && (
          <div className="space-y-3">
            {narrative.map(n => (
              <div key={n.id} className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    n.event_type === 'show' ? 'bg-amber-900/50 text-amber-300' :
                    n.event_type === 'injury' ? 'bg-red-900/50 text-red-300' :
                    n.event_type === 'signing' ? 'bg-green-900/50 text-green-300' :
                    n.event_type === 'stable_formed' ? 'bg-purple-900/50 text-purple-300' :
                    n.event_type === 'stable_dissolved' ? 'bg-purple-900/50 text-purple-300' :
                    n.event_type === 'manager_assigned' ? 'bg-cyan-900/50 text-cyan-300' :
                    n.event_type === 'manager_removed' ? 'bg-cyan-900/50 text-cyan-300' :
                    n.event_type === 'power_struggle' ? 'bg-orange-900/50 text-orange-300' :
                    n.event_type === 'betrayal_brewing' ? 'bg-red-900/50 text-red-300' :
                    n.event_type === 'stable_member_added' ? 'bg-purple-900/50 text-purple-300' :
                    n.event_type === 'stable_member_removed' ? 'bg-purple-900/50 text-purple-300' :
                    'bg-gray-800 text-gray-300'
                  }`}>{n.event_type.replace(/_/g, ' ')}</span>
                  <span className="text-xs text-gray-500">{n.game_date}</span>
                </div>
                <p className="text-gray-300 text-sm">{n.description}</p>
              </div>
            ))}
            {narrative.length === 0 && <div className="text-center text-gray-500 py-8">No events yet. Advance time to see the world come alive!</div>}
          </div>
        )}
      </div>
    </div>
  );
}
