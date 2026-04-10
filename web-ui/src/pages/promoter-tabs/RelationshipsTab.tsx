import { api } from '../../api/client';
import { AlignmentBadge, RoleBadge } from '../PromoterDashboard';
import type { Wrestler } from '../PromoterDashboard';

interface RelationshipsTabProps {
  worldId: string | null;
  federationId: string | null;
  roster: Wrestler[];
  managers: any[];
  managerBonds: any[];
  managerMap: Record<string, string>;
  showManagerForm: boolean;
  setShowManagerForm: (v: boolean) => void;
  showAssignForm: boolean;
  setShowAssignForm: (v: boolean) => void;
  formData: any;
  setFormData: (v: any) => void;
  loadData: () => Promise<void>;
  setError: (msg: string) => void;
}

export default function RelationshipsTab({
  worldId, federationId,
  roster, managers, managerBonds, managerMap,
  showManagerForm, setShowManagerForm,
  showAssignForm, setShowAssignForm,
  formData, setFormData,
  loadData, setError,
}: RelationshipsTabProps) {
  return (
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
  );
}
