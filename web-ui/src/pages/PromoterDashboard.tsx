import { useState, useEffect } from 'react';
import { useGame } from '../context/GameContext';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

interface Wrestler {
  id: string; name: string; popularity: number; alignment: string;
  condition: number; is_injured: boolean; is_npc: boolean;
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
  const [tab, setTab] = useState<'roster' | 'freeagents' | 'shows' | 'titles' | 'news'>('roster');
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState('');

  const loadData = async () => {
    if (!worldId || !federationId) return;
    try {
      const [fed, rost, agents, sh, champs, narr, world] = await Promise.all([
        api.getFederation(federationId),
        api.getRoster(federationId),
        api.listFreeAgents(worldId),
        api.getShows(federationId),
        api.getChampionships(federationId),
        api.getNarrative(worldId, 20),
        api.getWorld(worldId),
      ]);
      setFederation(fed);
      setRoster(rost);
      setFreeAgents(agents);
      setShows(sh);
      setChampionships(champs);
      setNarrative(narr);
      setWorldData(world);
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
      // Advance a day to process the action
      await advanceDay(1);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const exitGame = () => {
    clearGame();
    navigate('/setup');
  };

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
        <div className="flex gap-1 mb-6">
          {(['roster', 'freeagents', 'shows', 'titles', 'news'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-t text-sm ${tab === t ? 'bg-[#1a1a24] text-amber-400 border-t border-x border-gray-800' : 'text-gray-500 hover:text-gray-300'}`}
            >
              {t === 'freeagents' ? 'Free Agents' : t.charAt(0).toUpperCase() + t.slice(1)}
              {t === 'roster' && ` (${roster.length})`}
              {t === 'freeagents' && ` (${freeAgents.length})`}
            </button>
          ))}
        </div>

        {/* Roster Tab */}
        {tab === 'roster' && (
          <div className="bg-[#1a1a24] rounded-lg border border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#0f0f14]">
                <tr className="text-gray-400">
                  <th className="text-left p-3">Name</th>
                  <th className="text-left p-3">Alignment</th>
                  <th className="text-center p-3">Popularity</th>
                  <th className="text-center p-3">Condition</th>
                  <th className="text-center p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {roster.map(w => (
                  <tr key={w.id} className="border-t border-gray-800 hover:bg-[#0f0f14]/50">
                    <td className="p-3 text-white">{w.name}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        w.alignment === 'face' ? 'bg-blue-900/50 text-blue-300' :
                        w.alignment === 'heel' ? 'bg-red-900/50 text-red-300' :
                        'bg-gray-800 text-gray-300'
                      }`}>{w.alignment}</span>
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
                ))}
                {roster.length === 0 && (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">No wrestlers on roster. Sign some free agents!</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Free Agents Tab */}
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
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        w.alignment === 'face' ? 'bg-blue-900/50 text-blue-300' :
                        w.alignment === 'heel' ? 'bg-red-900/50 text-red-300' :
                        'bg-gray-800 text-gray-300'
                      }`}>{w.alignment}</span>
                    </td>
                    <td className="p-3 text-center text-gray-300">{w.popularity}</td>
                    <td className="p-3 text-center text-gray-300">{w.condition}%</td>
                    <td className="p-3 text-center">
                      <button
                        onClick={() => signWrestler(w.id)}
                        className="px-3 py-1 bg-green-700 hover:bg-green-600 text-white rounded text-xs transition-colors"
                      >
                        Sign
                      </button>
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

        {/* Shows Tab */}
        {tab === 'shows' && (
          <div className="space-y-3">
            {shows.map(s => (
              <div key={s.id} className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4 flex items-center justify-between">
                <div>
                  <h3 className="text-white font-medium">{s.name}</h3>
                  <p className="text-sm text-gray-400">{s.game_date} | {s.venue} | {s.show_type}</p>
                </div>
                <div className="text-right">
                  {s.is_completed ? (
                    <>
                      <div className="text-amber-400">Rating: {s.overall_rating}</div>
                      <div className="text-sm text-gray-400">Attendance: {s.attendance?.toLocaleString()}</div>
                      {s.gate_revenue && <div className="text-sm text-green-400">${s.gate_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>}
                    </>
                  ) : (
                    <span className="text-yellow-400 text-sm">Upcoming</span>
                  )}
                </div>
              </div>
            ))}
            {shows.length === 0 && <div className="text-center text-gray-500 py-8">No shows yet</div>}
          </div>
        )}

        {/* Championships Tab */}
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

        {/* News Tab */}
        {tab === 'news' && (
          <div className="space-y-3">
            {narrative.map(n => (
              <div key={n.id} className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    n.event_type === 'show' ? 'bg-amber-900/50 text-amber-300' :
                    n.event_type === 'injury' ? 'bg-red-900/50 text-red-300' :
                    n.event_type === 'signing' ? 'bg-green-900/50 text-green-300' :
                    'bg-gray-800 text-gray-300'
                  }`}>{n.event_type}</span>
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
