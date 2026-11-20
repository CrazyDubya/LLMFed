import { useState } from 'react';
import { skipToken, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useGame } from '../context/GameContext';
import { api, type Player, type PlayerCreateData } from '../api/client';
import { getErrorMessage } from '../utils/errors';

export default function GameSetupPage() {
  const { user, logout } = useAuth();
  const { savedWorldId, setGame } = useGame();
  const navigate = useNavigate();
  const { data: savedPlayer, isSuccess: canContinue, isError: saveUnavailable } = useQuery({
    queryKey: ['savedPlayer', user?.id, savedWorldId],
    queryFn: savedWorldId ? () => api.getMyPlayer(savedWorldId) : skipToken,
    retry: false,
  });

  const [step, setStep] = useState<'mode' | 'promoter' | 'wrestler'>('mode');
  const [worldName, setWorldName] = useState('My Wrestling World');
  const [fedName, setFedName] = useState('');
  const [fedDesc, setFedDesc] = useState('');
  const [wrestlerName, setWrestlerName] = useState('');
  const [wrestlerGimmick, setWrestlerGimmick] = useState('');
  const [wrestlerStyle, setWrestlerStyle] = useState('allrounder');
  const [alignment, setAlignment] = useState('face');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const openGame = (worldId: string, player: Player) => {
    setGame(worldId, player);
    navigate(player.player_type === 'promoter' ? '/promoter' : '/wrestler');
  };

  const startGame = async (playerType: 'promoter' | 'wrestler') => {
    setLoading(true);
    setError('');
    try {
      // Create world
      const world = await api.createWorld({ name: worldName });

      // Create player
      const playerData: PlayerCreateData = {
        world_id: world.id,
        player_type: playerType,
      };

      if (playerType === 'promoter') {
        playerData.federation_name = fedName || 'My Wrestling Federation';
        playerData.federation_description = fedDesc;
      } else {
        playerData.wrestler_name = wrestlerName || 'The Rookie';
        playerData.wrestler_gimmick = wrestlerGimmick;
        playerData.wrestler_alignment = alignment;
        playerData.wrestler_style = wrestlerStyle;
      }

      const player = await api.createPlayer(playerData);
      openGame(world.id, player);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0f0f14] p-8">
      <div className="max-w-2xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-amber-400">New Game</h1>
          <div className="flex items-center gap-4">
            <span className="text-gray-400">{user?.username}</span>
            <button onClick={logout} className="text-sm text-gray-500 hover:text-gray-300">Logout</button>
          </div>
        </div>

        {step === 'mode' && savedWorldId && canContinue && (
          <div className="bg-[#1a1a24] rounded-lg p-6 border border-gray-800 mb-6 flex items-center justify-between">
            <h2 className="text-xl text-white">Saved Game</h2>
            <button
              onClick={() => openGame(savedWorldId, savedPlayer)}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded transition-colors"
            >
              Continue
            </button>
          </div>
        )}
        {step === 'mode' && saveUnavailable && (
          <p role="status" className="text-gray-400 text-sm mb-6">Could not load your saved game.</p>
        )}

        {/* World Name */}
        <div className="bg-[#1a1a24] rounded-lg p-6 border border-gray-800 mb-6">
          <h2 className="text-xl text-white mb-4">World Name</h2>
          <input
            type="text"
            value={worldName}
            onChange={e => setWorldName(e.target.value)}
            className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white focus:border-amber-500 focus:outline-none"
            placeholder="Name your wrestling world..."
          />
        </div>

        {step === 'mode' && (
          <div className="grid grid-cols-2 gap-6">
            <button
              onClick={() => setStep('promoter')}
              className="bg-[#1a1a24] rounded-lg p-8 border border-gray-800 hover:border-amber-500 transition-colors text-left group"
            >
              <div className="text-4xl mb-4">&#127919;</div>
              <h2 className="text-xl text-white mb-2 group-hover:text-amber-400">Promoter Mode</h2>
              <p className="text-gray-400 text-sm">
                Build a wrestling empire. Book shows, sign talent, create championships,
                and shape storylines. Start from a small indie promotion and grow to global dominance.
              </p>
              <div className="mt-4 text-xs text-gray-500">Management Sim / World Builder</div>
            </button>

            <button
              onClick={() => setStep('wrestler')}
              className="bg-[#1a1a24] rounded-lg p-8 border border-gray-800 hover:border-amber-500 transition-colors text-left group"
            >
              <div className="text-4xl mb-4">&#128170;</div>
              <h2 className="text-xl text-white mb-2 group-hover:text-amber-400">Wrestler Mode</h2>
              <p className="text-gray-400 text-sm">
                Create your character. Train skills, cut promos, form alliances,
                chase championships. Start as an unknown rookie and become a legend.
              </p>
              <div className="mt-4 text-xs text-gray-500">Character RPG / Career Mode</div>
            </button>
          </div>
        )}

        {step === 'promoter' && (
          <div className="bg-[#1a1a24] rounded-lg p-6 border border-gray-800">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl text-white">Create Your Federation</h2>
              <button onClick={() => setStep('mode')} className="text-gray-500 hover:text-gray-300 text-sm">Back</button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-gray-400 block mb-1">Federation Name</label>
                <input
                  type="text"
                  value={fedName}
                  onChange={e => setFedName(e.target.value)}
                  className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white focus:border-amber-500 focus:outline-none"
                  placeholder="e.g. Apex Pro Wrestling"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-1">Description</label>
                <textarea
                  value={fedDesc}
                  onChange={e => setFedDesc(e.target.value)}
                  className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white focus:border-amber-500 focus:outline-none h-24 resize-none"
                  placeholder="A new indie promotion focused on..."
                />
              </div>
              {error && <p className="text-red-400 text-sm">{error}</p>}
              <button
                onClick={() => startGame('promoter')}
                disabled={loading}
                className="w-full py-3 bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 text-white font-semibold rounded transition-colors"
              >
                {loading ? 'Creating World...' : 'Start as Promoter'}
              </button>
            </div>
          </div>
        )}

        {step === 'wrestler' && (
          <div className="bg-[#1a1a24] rounded-lg p-6 border border-gray-800">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl text-white">Create Your Wrestler</h2>
              <button onClick={() => setStep('mode')} className="text-gray-500 hover:text-gray-300 text-sm">Back</button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-gray-400 block mb-1">Ring Name</label>
                <input
                  type="text"
                  value={wrestlerName}
                  onChange={e => setWrestlerName(e.target.value)}
                  className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white focus:border-amber-500 focus:outline-none"
                  placeholder="e.g. Thunder Rose"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-1">Gimmick / Character</label>
                <textarea
                  value={wrestlerGimmick}
                  onChange={e => setWrestlerGimmick(e.target.value)}
                  className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white focus:border-amber-500 focus:outline-none h-20 resize-none"
                  placeholder="A fierce competitor who..."
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-gray-400 block mb-1">Wrestling Style</label>
                  <select
                    value={wrestlerStyle}
                    onChange={e => setWrestlerStyle(e.target.value)}
                    className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white focus:border-amber-500 focus:outline-none"
                  >
                    <option value="allrounder">All-Rounder</option>
                    <option value="technical">Technical</option>
                    <option value="brawler">Brawler</option>
                    <option value="highflyer">High-Flyer</option>
                    <option value="powerhouse">Powerhouse</option>
                    <option value="showman">Showman</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm text-gray-400 block mb-1">Alignment</label>
                  <select
                    value={alignment}
                    onChange={e => setAlignment(e.target.value)}
                    className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white focus:border-amber-500 focus:outline-none"
                  >
                    <option value="face">Face (Fan Favorite)</option>
                    <option value="heel">Heel (Villain)</option>
                    <option value="tweener">Tweener</option>
                  </select>
                </div>
              </div>
              {error && <p className="text-red-400 text-sm">{error}</p>}
              <button
                onClick={() => startGame('wrestler')}
                disabled={loading}
                className="w-full py-3 bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 text-white font-semibold rounded transition-colors"
              >
                {loading ? 'Creating World...' : 'Start as Wrestler'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
