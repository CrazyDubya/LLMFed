import { useState, useEffect } from 'react';
import { useGame } from '../context/GameContext';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

export default function WrestlerDashboard() {
  const { worldId, wrestlerId, clearGame } = useGame();
  const navigate = useNavigate();

  const [wrestler, setWrestler] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [worldData, setWorldData] = useState<any>(null);
  const [narrative, setNarrative] = useState<any[]>([]);
  const [federations, setFederations] = useState<any[]>([]);
  const [stableInfo, setStableInfo] = useState<any>(null);
  const [managerInfo, setManagerInfo] = useState<any>(null);
  const [tab, setTab] = useState<'stats' | 'career' | 'train' | 'world'>('stats');
  const [advancing, setAdvancing] = useState(false);
  const [trainingStat, setTrainingStat] = useState('stamina');
  const [error, setError] = useState('');

  const loadData = async () => {
    if (!worldId || !wrestlerId) return;
    try {
      const [wd, wData, narr, feds, stbl, mgr] = await Promise.all([
        api.getWorld(worldId),
        api.getWrestler(wrestlerId),
        api.getNarrative(worldId, 20),
        api.listFederations(worldId),
        api.getWrestlerStable(wrestlerId).catch(() => null),
        api.getWrestlerManager(wrestlerId).catch(() => null),
      ]);
      setWorldData(wd);
      setWrestler(wData.wrestler);
      setStats(wData.stats);
      setNarrative(narr);
      setFederations(feds);
      setStableInfo(stbl);
      setManagerInfo(mgr);
    } catch (err: any) {
      setError(err.message);
    }
  };

  useEffect(() => { loadData(); }, [worldId, wrestlerId]);

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

  const trainStat = async () => {
    if (!worldId || !wrestlerId) return;
    try {
      await api.submitAction(worldId, 'train', {
        wrestler_id: wrestlerId,
        stat: trainingStat,
      });
      await advanceDay(1);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const exitGame = () => { clearGame(); navigate('/setup'); };

  const statBar = (label: string, value: number, color = 'amber') => (
    <div className="flex items-center gap-3 py-1">
      <span className="text-gray-400 text-sm w-24 text-right">{label}</span>
      <div className="flex-1 bg-gray-800 rounded-full h-3">
        <div className={`bg-${color}-500 h-3 rounded-full transition-all`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-white text-sm w-8">{value}</span>
    </div>
  );

  if (!worldId || !wrestlerId) {
    return <div className="p-8 text-center text-gray-400">No active game. <button onClick={() => navigate('/setup')} className="text-amber-400">Start a new game</button></div>;
  }

  return (
    <div className="min-h-screen bg-[#0f0f14]">
      {/* Header */}
      <header className="bg-[#1a1a24] border-b border-gray-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-amber-400">{wrestler?.name || 'Loading...'}</h1>
            <p className="text-sm text-gray-400">
              Wrestler Mode | {worldData?.current_game_date || '...'} |
              Popularity: {wrestler?.popularity || 0} |
              {wrestler?.alignment && <span className={wrestler.alignment === 'face' ? ' text-blue-400' : wrestler.alignment === 'heel' ? ' text-red-400' : ' text-gray-400'}> {wrestler.alignment.toUpperCase()}</span>}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <span className={`text-sm ${wrestler?.condition > 70 ? 'text-green-400' : wrestler?.condition > 40 ? 'text-yellow-400' : 'text-red-400'}`}>
              Condition: {wrestler?.condition || 0}%
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

      <div className="max-w-7xl mx-auto px-6 mt-6">
        {/* Tabs */}
        <div className="flex gap-1 mb-6">
          {(['stats', 'train', 'career', 'world'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-t text-sm ${tab === t ? 'bg-[#1a1a24] text-amber-400 border-t border-x border-gray-800' : 'text-gray-500 hover:text-gray-300'}`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {/* Stats Tab */}
        {tab === 'stats' && stats && (
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-6">
              <h3 className="text-white font-medium mb-4">In-Ring Abilities</h3>
              {statBar('Power', stats.power)}
              {statBar('Speed', stats.speed)}
              {statBar('Technical', stats.technical)}
              {statBar('Aerial', stats.aerial)}
              {statBar('Brawling', stats.brawling)}
              {statBar('Submission', stats.submission)}
              {statBar('Stamina', stats.stamina)}
              {statBar('Toughness', stats.toughness)}
            </div>
            <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-6">
              <h3 className="text-white font-medium mb-4">Character & Presence</h3>
              {statBar('Charisma', stats.charisma)}
              {statBar('Mic Skill', stats.mic_skill)}
              {statBar('Psychology', stats.psychology)}
              {statBar('Selling', stats.selling)}

              <div className="mt-6 pt-4 border-t border-gray-800">
                <h3 className="text-white font-medium mb-2">Character Info</h3>
                <div className="space-y-2 text-sm">
                  <p className="text-gray-400">Gimmick: <span className="text-gray-300">{wrestler?.gimmick}</span></p>
                  <p className="text-gray-400">Finisher: <span className="text-gray-300">{wrestler?.finisher_name}</span></p>
                  <p className="text-gray-400">Weight: <span className="text-gray-300">{wrestler?.weight_class}</span></p>
                  <p className="text-gray-400">Age: <span className="text-gray-300">{wrestler?.age}</span></p>
                  {wrestler?.is_injured && <p className="text-red-400 font-medium">INJURED - Return: {wrestler.injury_return_date}</p>}
                </div>
              </div>

              {/* Faction & Manager Info */}
              {(stableInfo?.in_stable || managerInfo?.has_manager) && (
                <div className="mt-6 pt-4 border-t border-gray-800">
                  <h3 className="text-white font-medium mb-2">Alliances</h3>
                  <div className="space-y-3">
                    {stableInfo?.in_stable && (
                      <div className="bg-purple-900/20 border border-purple-800/30 rounded p-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-purple-300 font-medium">{stableInfo.stable_name}</span>
                          <span className="px-2 py-0.5 rounded text-xs bg-purple-900/50 text-purple-300">{stableInfo.role}</span>
                        </div>
                        <div className="flex gap-4 text-xs text-gray-400">
                          <span>Loyalty: <span className={stableInfo.loyalty >= 60 ? 'text-green-400' : stableInfo.loyalty >= 30 ? 'text-yellow-400' : 'text-red-400'}>{stableInfo.loyalty}</span></span>
                          <span>Influence: {stableInfo.influence}</span>
                        </div>
                      </div>
                    )}
                    {managerInfo?.has_manager && (
                      <div className="bg-cyan-900/20 border border-cyan-800/30 rounded p-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-cyan-300 font-medium">{managerInfo.manager_name}</span>
                          <span className="px-2 py-0.5 rounded text-xs bg-cyan-900/50 text-cyan-300">{managerInfo.role}</span>
                        </div>
                        <div className="flex gap-4 text-xs text-gray-400">
                          <span>Effectiveness: {managerInfo.effectiveness}%</span>
                          <span>+{managerInfo.charisma_bonus} CHA</span>
                          <span>+{managerInfo.heat_bonus} Heat</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Training Tab */}
        {tab === 'train' && (
          <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-6 max-w-lg">
            <h3 className="text-white font-medium mb-4">Training Session</h3>
            <p className="text-gray-400 text-sm mb-4">
              Choose a stat to train. Training improves the stat but costs condition.
              Higher stats are harder to improve.
            </p>
            <select
              value={trainingStat}
              onChange={e => setTrainingStat(e.target.value)}
              className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white focus:border-amber-500 focus:outline-none mb-4"
            >
              <optgroup label="In-Ring">
                <option value="power">Power</option>
                <option value="speed">Speed</option>
                <option value="technical">Technical</option>
                <option value="aerial">Aerial</option>
                <option value="brawling">Brawling</option>
                <option value="submission">Submission</option>
                <option value="stamina">Stamina</option>
                <option value="toughness">Toughness</option>
              </optgroup>
              <optgroup label="Character">
                <option value="charisma">Charisma</option>
                <option value="mic_skill">Mic Skill</option>
                <option value="psychology">Psychology</option>
                <option value="selling">Selling</option>
              </optgroup>
            </select>
            <button
              onClick={trainStat}
              disabled={advancing || (wrestler?.condition || 0) < 10}
              className="w-full py-3 bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 text-white font-semibold rounded transition-colors"
            >
              {wrestler?.condition < 10 ? 'Too Tired to Train' : 'Train!'}
            </button>
            {stats && (
              <p className="text-gray-500 text-xs mt-2">
                Current {trainingStat}: {stats[trainingStat] ?? '?'} | Condition: {wrestler?.condition}%
              </p>
            )}
          </div>
        )}

        {/* Career Tab */}
        {tab === 'career' && (
          <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-6">
            <h3 className="text-white font-medium mb-4">Career Overview</h3>
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-[#0f0f14] rounded p-4 text-center">
                <div className="text-2xl text-amber-400 font-bold">{wrestler?.popularity || 0}</div>
                <div className="text-xs text-gray-400">Popularity</div>
              </div>
              <div className="bg-[#0f0f14] rounded p-4 text-center">
                <div className="text-2xl text-blue-400 font-bold">{wrestler?.morale || 0}</div>
                <div className="text-xs text-gray-400">Morale</div>
              </div>
              <div className="bg-[#0f0f14] rounded p-4 text-center">
                <div className="text-2xl text-green-400 font-bold">{wrestler?.experience_years || 0}</div>
                <div className="text-xs text-gray-400">Years Active</div>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <p className="text-gray-400">Contract: <span className="text-gray-300">{wrestler?.current_federation ? 'Signed' : 'Free Agent'}</span></p>
              <p className="text-gray-400">Championships: <span className="text-gray-300">{wrestler?.current_championships?.length || 0}</span></p>
            </div>
          </div>
        )}

        {/* World Tab */}
        {tab === 'world' && (
          <div className="space-y-4">
            <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-6">
              <h3 className="text-white font-medium mb-3">Federations</h3>
              <div className="grid grid-cols-2 gap-3">
                {federations.map(f => (
                  <div key={f.id} className="bg-[#0f0f14] rounded p-3">
                    <div className="text-amber-400 font-medium">{f.name}</div>
                    <div className="text-xs text-gray-400">
                      Prestige: {f.prestige} | {f.style} | {f.home_region}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-6">
              <h3 className="text-white font-medium mb-3">Recent Events</h3>
              {narrative.map(n => (
                <div key={n.id} className="py-2 border-b border-gray-800 last:border-0">
                  <span className="text-xs text-gray-500">{n.game_date}</span>
                  <span className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                    n.event_type === 'show' ? 'bg-amber-900/50 text-amber-300' :
                    n.event_type === 'injury' ? 'bg-red-900/50 text-red-300' :
                    'bg-gray-800 text-gray-300'
                  }`}>{n.event_type}</span>
                  <p className="text-gray-300 text-sm mt-1">{n.description}</p>
                </div>
              ))}
              {narrative.length === 0 && <p className="text-gray-500 text-sm">No events yet</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
