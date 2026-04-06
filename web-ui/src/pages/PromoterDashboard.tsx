import { useState, useEffect } from 'react';
import { useGame } from '../context/GameContext';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

interface Wrestler {
  id: string; name: string; popularity: number; alignment: string;
  condition: number; is_injured: boolean; is_npc: boolean;
}

type TabKey = 'warroom' | 'roster' | 'freeagents' | 'shows' | 'titles' | 'storylines' | 'factions' | 'relationships' | 'news';

const TAB_LABELS: Record<TabKey, string> = {
  warroom: 'War Room',
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
  const [tab, setTab] = useState<TabKey>('warroom');
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState('');
  const [expandedStable, setExpandedStable] = useState<string | null>(null);
  // Form states for management actions
  const [showStableForm, setShowStableForm] = useState(false);
  const [showManagerForm, setShowManagerForm] = useState(false);
  const [showAssignForm, setShowAssignForm] = useState(false);
  const [showStorylineForm, setShowStorylineForm] = useState(false);
  const [formData, setFormData] = useState<any>({});

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

        {/* ========== WAR ROOM TAB ========== */}
        {tab === 'warroom' && (
          <div className="space-y-6">
            {/* Quick Stats Row */}
            <div className="grid grid-cols-5 gap-4">
              <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4 text-center">
                <div className="text-2xl text-amber-400 font-bold">{roster.length}</div>
                <div className="text-xs text-gray-400">Roster Size</div>
              </div>
              <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4 text-center">
                <div className="text-2xl text-purple-400 font-bold">{stables.length}</div>
                <div className="text-xs text-gray-400">Active Factions</div>
              </div>
              <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4 text-center">
                <div className="text-2xl text-cyan-400 font-bold">{managerBonds.length}</div>
                <div className="text-xs text-gray-400">Manager Bonds</div>
              </div>
              <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4 text-center">
                <div className="text-2xl text-red-400 font-bold">{storylines.filter(s => s.status !== 'resolved').length}</div>
                <div className="text-xs text-gray-400">Active Storylines</div>
              </div>
              <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4 text-center">
                <div className="text-2xl text-green-400 font-bold">{roster.filter(w => w.is_injured).length}</div>
                <div className="text-xs text-gray-400">Injured</div>
              </div>
            </div>

            {/* Faction Health Monitor */}
            {stables.length > 0 && (
              <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-5">
                <h3 className="text-white font-semibold mb-4">Faction Health Monitor</h3>
                <div className="space-y-3">
                  {stables.map((s: any) => {
                    const isFragile = s.cohesion < 40;
                    const isCritical = s.cohesion < 20;
                    return (
                      <div key={s.id} className={`p-3 rounded border ${isCritical ? 'border-red-700 bg-red-900/10' : isFragile ? 'border-yellow-700 bg-yellow-900/10' : 'border-gray-700'}`}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-3">
                            <span className="text-white font-medium">{s.name}</span>
                            <AlignmentBadge alignment={s.alignment} />
                            <span className="text-xs text-gray-500">{(s.members || []).length} members</span>
                          </div>
                          <div className="flex items-center gap-4">
                            {isCritical && <span className="text-xs text-red-400 font-bold animate-pulse">CRITICAL - BETRAYAL IMMINENT</span>}
                            {isFragile && !isCritical && <span className="text-xs text-yellow-400 font-semibold">FRACTURING</span>}
                            <HeatBar value={s.heat} label={`Heat ${s.heat}`} />
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500 w-16">Cohesion</span>
                          <div className="flex-1 bg-gray-800 rounded-full h-2">
                            <div className={`h-2 rounded-full ${isCritical ? 'bg-red-500' : isFragile ? 'bg-yellow-500' : 'bg-green-500'}`} style={{ width: `${s.cohesion}%` }} />
                          </div>
                          <span className="text-xs text-gray-400 w-8">{s.cohesion}%</span>
                        </div>
                        {/* Members with low loyalty */}
                        {(s.members || []).filter((m: any) => m.loyalty < 40).length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {(s.members || []).filter((m: any) => m.loyalty < 40).map((m: any) => (
                              <span key={m.wrestler_id} className="text-xs px-2 py-0.5 bg-red-900/30 border border-red-800/50 rounded text-red-300">
                                {m.wrestler_name}: loyalty {m.loyalty}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Storyline Heat Tracker */}
            {storylines.filter(s => s.status !== 'resolved').length > 0 && (
              <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-5">
                <h3 className="text-white font-semibold mb-4">Storyline Heat Tracker</h3>
                <div className="space-y-2">
                  {storylines.filter(s => s.status !== 'resolved').sort((a: any, b: any) => b.heat - a.heat).map((sl: any) => (
                    <div key={sl.id} className="flex items-center gap-3 p-2 rounded hover:bg-[#0f0f14]/50">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        sl.status === 'climax' ? 'bg-red-900/50 text-red-300' :
                        sl.status === 'active' ? 'bg-green-900/50 text-green-300' :
                        'bg-yellow-900/50 text-yellow-300'
                      }`}>{sl.status}</span>
                      <span className="text-white text-sm flex-1">{sl.name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        sl.storyline_type === 'faction_war' ? 'bg-purple-900/50 text-purple-300' :
                        sl.storyline_type === 'power_struggle' ? 'bg-orange-900/50 text-orange-300' :
                        'bg-gray-700 text-gray-300'
                      }`}>{sl.storyline_type.replace(/_/g, ' ')}</span>
                      <div className="w-24">
                        <div className="bg-gray-800 rounded-full h-2">
                          <div className={`h-2 rounded-full ${sl.heat >= 70 ? 'bg-red-500' : sl.heat >= 40 ? 'bg-amber-500' : 'bg-gray-500'}`}
                            style={{ width: `${sl.heat}%` }} />
                        </div>
                      </div>
                      <span className="text-xs text-gray-400 w-6">{sl.heat}</span>
                      <div className="flex gap-1">
                        {sl.status !== 'climax' && (
                          <button
                            onClick={async () => {
                              try {
                                await api.advanceStoryline(sl.id, { heat_boost: 10 });
                                await loadData();
                              } catch (err: any) { setError(err.message); }
                            }}
                            className="px-2 py-0.5 text-xs bg-amber-800 hover:bg-amber-700 text-amber-200 rounded"
                            title="Boost heat +10"
                          >+Heat</button>
                        )}
                        {sl.status === 'brewing' && (
                          <button
                            onClick={async () => {
                              try {
                                await api.advanceStoryline(sl.id, { status: 'active' });
                                await loadData();
                              } catch (err: any) { setError(err.message); }
                            }}
                            className="px-2 py-0.5 text-xs bg-green-800 hover:bg-green-700 text-green-200 rounded"
                          >Activate</button>
                        )}
                        {sl.status === 'active' && (
                          <button
                            onClick={async () => {
                              try {
                                await api.advanceStoryline(sl.id, { status: 'climax' });
                                await loadData();
                              } catch (err: any) { setError(err.message); }
                            }}
                            className="px-2 py-0.5 text-xs bg-red-800 hover:bg-red-700 text-red-200 rounded"
                          >Climax</button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Unaffiliated Talent + Quick Actions */}
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-5">
                <h3 className="text-white font-semibold mb-3">Unaffiliated Talent</h3>
                <p className="text-xs text-gray-500 mb-3">Wrestlers not in a faction or without a manager — potential recruits or storyline targets.</p>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {roster.filter(w => !stableMemberMap[w.id] && !managerMap[w.id]).map(w => (
                    <div key={w.id} className="flex items-center justify-between py-1 px-2 rounded hover:bg-[#0f0f14]/50">
                      <span className="text-sm text-gray-300">{w.name}</span>
                      <div className="flex items-center gap-2">
                        <AlignmentBadge alignment={w.alignment} />
                        <span className="text-xs text-gray-500">Pop: {w.popularity}</span>
                      </div>
                    </div>
                  ))}
                  {roster.filter(w => !stableMemberMap[w.id] && !managerMap[w.id]).length === 0 && (
                    <p className="text-gray-600 text-sm">Everyone is affiliated!</p>
                  )}
                </div>
              </div>

              <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-5">
                <h3 className="text-white font-semibold mb-3">Quick Actions</h3>
                <div className="space-y-2">
                  <button
                    onClick={() => { setShowStableForm(true); setFormData({}); setTab('factions'); }}
                    className="w-full text-left px-3 py-2 rounded bg-purple-900/20 border border-purple-800/30 text-purple-300 hover:bg-purple-900/30 text-sm"
                  >Form New Faction</button>
                  <button
                    onClick={() => { setShowManagerForm(true); setFormData({}); setTab('relationships'); }}
                    className="w-full text-left px-3 py-2 rounded bg-cyan-900/20 border border-cyan-800/30 text-cyan-300 hover:bg-cyan-900/30 text-sm"
                  >Create Manager</button>
                  <button
                    onClick={() => { setShowStorylineForm(true); setFormData({}); setTab('storylines'); }}
                    className="w-full text-left px-3 py-2 rounded bg-amber-900/20 border border-amber-800/30 text-amber-300 hover:bg-amber-900/30 text-sm"
                  >Start Storyline</button>
                  <button
                    onClick={() => { setShowAssignForm(true); setFormData({}); setTab('relationships'); }}
                    className="w-full text-left px-3 py-2 rounded bg-green-900/20 border border-green-800/30 text-green-300 hover:bg-green-900/30 text-sm"
                  >Assign Manager to Client</button>
                </div>
              </div>
            </div>
          </div>
        )}

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

        {/* ========== STORYLINES TAB ========== */}
        {tab === 'storylines' && (
          <div className="space-y-3">
            <div className="flex justify-end">
              <button
                onClick={() => { setShowStorylineForm(!showStorylineForm); setFormData({}); }}
                className="px-4 py-2 bg-amber-700 hover:bg-amber-600 text-white rounded text-sm"
              >{showStorylineForm ? 'Cancel' : 'Start Storyline'}</button>
            </div>
            {showStorylineForm && (
              <div className="bg-[#1a1a24] rounded-lg border border-amber-800/50 p-5">
                <h3 className="text-amber-300 font-semibold mb-4">Start New Storyline</h3>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Name (optional)</label>
                    <input
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      placeholder="Auto-generated if blank"
                      value={formData.sl_name || ''}
                      onChange={e => setFormData({ ...formData, sl_name: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Type</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={formData.sl_type || 'feud'}
                      onChange={e => setFormData({ ...formData, sl_type: e.target.value })}
                    >
                      <option value="feud">Feud</option>
                      <option value="betrayal">Betrayal</option>
                      <option value="alliance">Alliance</option>
                      <option value="title_chase">Title Chase</option>
                      <option value="faction_war">Faction War</option>
                      <option value="power_struggle">Power Struggle</option>
                      <option value="manager_betrayal">Manager Betrayal</option>
                    </select>
                  </div>
                </div>
                <div className="mb-4">
                  <label className="text-xs text-gray-400 block mb-1">Wrestlers (select 2+, hold Ctrl/Cmd)</label>
                  <select
                    multiple
                    className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm h-28"
                    value={formData.sl_wrestlers || []}
                    onChange={e => setFormData({ ...formData, sl_wrestlers: Array.from(e.target.selectedOptions, o => o.value) })}
                  >
                    {roster.map(w => (
                      <option key={w.id} value={w.id}>{w.name} ({w.alignment})</option>
                    ))}
                  </select>
                </div>
                <div className="mb-4">
                  <label className="text-xs text-gray-400 block mb-1">Description (optional)</label>
                  <input
                    className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                    placeholder="Auto-generated if blank"
                    value={formData.sl_desc || ''}
                    onChange={e => setFormData({ ...formData, sl_desc: e.target.value })}
                  />
                </div>
                <button
                  onClick={async () => {
                    if (!worldId || !formData.sl_wrestlers || formData.sl_wrestlers.length < 2) {
                      setError('Select at least 2 wrestlers'); return;
                    }
                    try {
                      await api.createStoryline(worldId, {
                        wrestler_ids: formData.sl_wrestlers,
                        storyline_type: formData.sl_type || 'feud',
                        name: formData.sl_name || undefined,
                        description: formData.sl_desc || undefined,
                      });
                      setShowStorylineForm(false);
                      setFormData({});
                      await loadData();
                    } catch (err: any) { setError(err.message); }
                  }}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded text-sm font-medium"
                >Create Storyline</button>
              </div>
            )}

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

        {/* ========== FACTIONS TAB ========== */}
        {tab === 'factions' && (
          <div className="space-y-4">
            {/* Form Faction Button/Form */}
            <div className="flex justify-end">
              <button
                onClick={() => { setShowStableForm(!showStableForm); setFormData({}); }}
                className="px-4 py-2 bg-purple-700 hover:bg-purple-600 text-white rounded text-sm"
              >{showStableForm ? 'Cancel' : 'Form Faction'}</button>
            </div>
            {showStableForm && (
              <div className="bg-[#1a1a24] rounded-lg border border-purple-800/50 p-5">
                <h3 className="text-purple-300 font-semibold mb-4">Form New Faction</h3>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Name</label>
                    <input
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      placeholder="The Wolfpack"
                      value={formData.name || ''}
                      onChange={e => setFormData({ ...formData, name: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Alignment</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={formData.alignment || 'heel'}
                      onChange={e => setFormData({ ...formData, alignment: e.target.value })}
                    >
                      <option value="heel">Heel</option>
                      <option value="face">Face</option>
                      <option value="tweener">Tweener</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Leader</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={formData.leader_id || ''}
                      onChange={e => setFormData({ ...formData, leader_id: e.target.value })}
                    >
                      <option value="">Select leader...</option>
                      {roster.filter(w => !stableMemberMap[w.id]).map(w => (
                        <option key={w.id} value={w.id}>{w.name} (Pop: {w.popularity})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Catchphrase</label>
                    <input
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      placeholder="Optional..."
                      value={formData.catchphrase || ''}
                      onChange={e => setFormData({ ...formData, catchphrase: e.target.value })}
                    />
                  </div>
                </div>
                <div className="mb-4">
                  <label className="text-xs text-gray-400 block mb-1">Additional Members (hold Ctrl/Cmd to select multiple)</label>
                  <select
                    multiple
                    className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm h-28"
                    value={formData.member_ids || []}
                    onChange={e => setFormData({ ...formData, member_ids: Array.from(e.target.selectedOptions, o => o.value) })}
                  >
                    {roster.filter(w => !stableMemberMap[w.id] && w.id !== formData.leader_id).map(w => (
                      <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={async () => {
                    if (!worldId || !formData.name || !formData.leader_id) {
                      setError('Name and leader required'); return;
                    }
                    try {
                      const allMembers = [formData.leader_id, ...(formData.member_ids || [])];
                      await api.createStable(worldId, {
                        name: formData.name,
                        leader_id: formData.leader_id,
                        founding_member_ids: allMembers,
                        alignment: formData.alignment || 'heel',
                        catchphrase: formData.catchphrase || undefined,
                      });
                      setShowStableForm(false);
                      setFormData({});
                      await loadData();
                    } catch (err: any) { setError(err.message); }
                  }}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded text-sm font-medium"
                >Create Faction</button>
              </div>
            )}

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
                    {/* Management controls */}
                    <div className="mt-4 pt-3 border-t border-gray-800 flex items-center gap-3">
                      <select
                        className="p-1.5 bg-[#0f0f14] border border-gray-700 rounded text-white text-xs flex-1"
                        value={formData[`add_to_${s.id}`] || ''}
                        onChange={e => setFormData({ ...formData, [`add_to_${s.id}`]: e.target.value })}
                      >
                        <option value="">Add member...</option>
                        {roster.filter(w => !stableMemberMap[w.id]).map(w => (
                          <option key={w.id} value={w.id}>{w.name}</option>
                        ))}
                      </select>
                      <button
                        onClick={async () => {
                          const wid = formData[`add_to_${s.id}`];
                          if (!wid) return;
                          try {
                            await api.addStableMember(s.id, { wrestler_id: wid, role: 'recruit' });
                            setFormData({ ...formData, [`add_to_${s.id}`]: '' });
                            await loadData();
                          } catch (err: any) { setError(err.message); }
                        }}
                        className="px-3 py-1.5 bg-purple-700 hover:bg-purple-600 text-white rounded text-xs"
                      >Add</button>
                      <button
                        onClick={async () => {
                          if (!confirm(`Dissolve ${s.name}? This cannot be undone.`)) return;
                          try {
                            await api.submitAction(worldId!, 'dissolve_stable', { stable_id: s.id });
                            await advanceDay(1);
                          } catch (err: any) { setError(err.message); }
                        }}
                        className="px-3 py-1.5 bg-red-800 hover:bg-red-700 text-red-200 rounded text-xs"
                      >Dissolve</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {stables.length === 0 && (
              <div className="text-center text-gray-500 py-8">No factions formed yet. Create stables to unlock faction warfare!</div>
            )}
          </div>
        )}

        {/* ========== RELATIONSHIPS TAB ========== */}
        {tab === 'relationships' && (
          <div className="space-y-6">
            {/* Action buttons */}
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setShowManagerForm(!showManagerForm); setShowAssignForm(false); setFormData({}); }}
                className="px-4 py-2 bg-cyan-700 hover:bg-cyan-600 text-white rounded text-sm"
              >{showManagerForm ? 'Cancel' : 'Create Manager'}</button>
              <button
                onClick={() => { setShowAssignForm(!showAssignForm); setShowManagerForm(false); setFormData({}); }}
                className="px-4 py-2 bg-green-700 hover:bg-green-600 text-white rounded text-sm"
              >{showAssignForm ? 'Cancel' : 'Assign Manager'}</button>
            </div>

            {/* Create Manager Form */}
            {showManagerForm && (
              <div className="bg-[#1a1a24] rounded-lg border border-cyan-800/50 p-5">
                <h3 className="text-cyan-300 font-semibold mb-4">Create New Manager</h3>
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Name</label>
                    <input
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      placeholder="Paul Bearer"
                      value={formData.mgr_name || ''}
                      onChange={e => setFormData({ ...formData, mgr_name: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Archetype</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={formData.mgr_archetype || 'scheming_manager'}
                      onChange={e => setFormData({ ...formData, mgr_archetype: e.target.value })}
                    >
                      <option value="scheming_manager">Scheming Manager</option>
                      <option value="corporate_suit">Corporate Suit</option>
                      <option value="flamboyant_mouthpiece">Flamboyant Mouthpiece</option>
                      <option value="enforcer_type">Enforcer Type</option>
                      <option value="old_school">Old School</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Alignment</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={formData.mgr_alignment || 'heel'}
                      onChange={e => setFormData({ ...formData, mgr_alignment: e.target.value })}
                    >
                      <option value="heel">Heel</option>
                      <option value="face">Face</option>
                      <option value="tweener">Tweener</option>
                    </select>
                  </div>
                </div>
                <div className="mb-4">
                  <label className="text-xs text-gray-400 block mb-1">Catchphrase (optional)</label>
                  <input
                    className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                    placeholder="Oh yesss!"
                    value={formData.mgr_catchphrase || ''}
                    onChange={e => setFormData({ ...formData, mgr_catchphrase: e.target.value })}
                  />
                </div>
                <button
                  onClick={async () => {
                    if (!worldId || !formData.mgr_name) { setError('Name required'); return; }
                    try {
                      await api.createManager(worldId, {
                        name: formData.mgr_name,
                        archetype: formData.mgr_archetype || 'scheming_manager',
                        alignment: formData.mgr_alignment || 'heel',
                        catchphrase: formData.mgr_catchphrase || undefined,
                      }, federationId || undefined);
                      setShowManagerForm(false);
                      setFormData({});
                      await loadData();
                    } catch (err: any) { setError(err.message); }
                  }}
                  className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-sm font-medium"
                >Create Manager</button>
              </div>
            )}

            {/* Assign Manager Form */}
            {showAssignForm && (
              <div className="bg-[#1a1a24] rounded-lg border border-green-800/50 p-5">
                <h3 className="text-green-300 font-semibold mb-4">Assign Manager to Client</h3>
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Manager</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={formData.assign_mgr || ''}
                      onChange={e => setFormData({ ...formData, assign_mgr: e.target.value })}
                    >
                      <option value="">Select manager...</option>
                      {managers.map((m: any) => (
                        <option key={m.id} value={m.id}>{m.name} ({m.archetype.replace(/_/g, ' ')})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Client Wrestler</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={formData.assign_client || ''}
                      onChange={e => setFormData({ ...formData, assign_client: e.target.value })}
                    >
                      <option value="">Select wrestler...</option>
                      {roster.filter(w => !managerMap[w.id]).map(w => (
                        <option key={w.id} value={w.id}>{w.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Role</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={formData.assign_role || 'manager'}
                      onChange={e => setFormData({ ...formData, assign_role: e.target.value })}
                    >
                      <option value="manager">Manager</option>
                      <option value="valet">Valet</option>
                      <option value="advocate">Advocate</option>
                      <option value="handler">Handler</option>
                    </select>
                  </div>
                </div>
                <button
                  onClick={async () => {
                    if (!worldId || !formData.assign_mgr || !formData.assign_client) {
                      setError('Select manager and client'); return;
                    }
                    try {
                      await api.assignManager(worldId, {
                        manager_id: formData.assign_mgr,
                        client_wrestler_id: formData.assign_client,
                        role: formData.assign_role || 'manager',
                      });
                      setShowAssignForm(false);
                      setFormData({});
                      await loadData();
                    } catch (err: any) { setError(err.message); }
                  }}
                  className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded text-sm font-medium"
                >Assign</button>
              </div>
            )}

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
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4 text-xs text-gray-400">
                          <span>Effectiveness: {b.effectiveness}%</span>
                          <span>Specialization: {b.specialization}</span>
                          <span>+{b.charisma_bonus} CHA</span>
                          <span>+{b.heat_bonus} Heat</span>
                        </div>
                        <button
                          onClick={async () => {
                            try {
                              await api.removeManagerBond(b.id);
                              await loadData();
                            } catch (err: any) { setError(err.message); }
                          }}
                          className="px-2 py-0.5 text-xs bg-red-900/50 hover:bg-red-800/50 text-red-300 rounded"
                        >End</button>
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
