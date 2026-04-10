import { api } from '../../api/client';
import { AlignmentBadge, HeatBar } from '../PromoterDashboard';
import type { Wrestler, TabKey } from '../PromoterDashboard';

interface WarRoomTabProps {
  roster: Wrestler[];
  stables: any[];
  managerBonds: any[];
  storylines: any[];
  stableMemberMap: Record<string, { stableName: string; role: string }>;
  managerMap: Record<string, string>;
  loadData: () => Promise<void>;
  setError: (msg: string) => void;
  setShowStableForm: (v: boolean) => void;
  setShowManagerForm: (v: boolean) => void;
  setShowStorylineForm: (v: boolean) => void;
  setShowAssignForm: (v: boolean) => void;
  setFormData: (v: any) => void;
  setTab: (tab: TabKey) => void;
}

export default function WarRoomTab({
  roster, stables, managerBonds, storylines,
  stableMemberMap, managerMap,
  loadData, setError,
  setShowStableForm, setShowManagerForm, setShowStorylineForm, setShowAssignForm,
  setFormData, setTab,
}: WarRoomTabProps) {
  return (
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
  );
}
