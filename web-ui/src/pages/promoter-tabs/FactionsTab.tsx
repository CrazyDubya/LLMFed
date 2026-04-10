import { api } from '../../api/client';
import { AlignmentBadge, HeatBar, RoleBadge } from '../PromoterDashboard';
import type { Wrestler } from '../PromoterDashboard';

interface FactionsTabProps {
  worldId: string | null;
  roster: Wrestler[];
  stables: any[];
  stableMemberMap: Record<string, { stableName: string; role: string }>;
  expandedStable: string | null;
  setExpandedStable: (id: string | null) => void;
  showStableForm: boolean;
  setShowStableForm: (v: boolean) => void;
  formData: any;
  setFormData: (v: any) => void;
  loadData: () => Promise<void>;
  advanceDay: (days?: number) => Promise<void>;
  setError: (msg: string) => void;
}

export default function FactionsTab({
  worldId, roster, stables, stableMemberMap,
  expandedStable, setExpandedStable,
  showStableForm, setShowStableForm,
  formData, setFormData,
  loadData, advanceDay, setError,
}: FactionsTabProps) {
  return (
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
  );
}
