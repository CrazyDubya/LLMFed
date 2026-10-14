import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Player } from '../api/client';

interface GameState {
  worldId: string | null;
  playerId: string | null;
  playerType: 'promoter' | 'wrestler' | null;
  federationId: string | null;
  wrestlerId: string | null;
}

interface GameContextType extends GameState {
  setWorld: (worldId: string) => void;
  setPlayer: (player: Player) => void;
  clearGame: () => void;
}

const GameContext = createContext<GameContextType | null>(null);

export function GameProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<GameState>({
    worldId: localStorage.getItem('worldId'),
    playerId: localStorage.getItem('playerId'),
    playerType: localStorage.getItem('playerType') as 'promoter' | 'wrestler' | null,
    federationId: localStorage.getItem('federationId'),
    wrestlerId: localStorage.getItem('wrestlerId'),
  });

  const setWorld = (worldId: string) => {
    localStorage.setItem('worldId', worldId);
    setState(s => ({ ...s, worldId }));
  };

  const setPlayer = (player: Player) => {
    localStorage.setItem('playerId', player.id);
    localStorage.setItem('playerType', player.player_type);
    if (player.federation_id) localStorage.setItem('federationId', player.federation_id);
    if (player.wrestler_id) localStorage.setItem('wrestlerId', player.wrestler_id);
    setState(s => ({
      ...s,
      playerId: player.id,
      playerType: player.player_type,
      federationId: player.federation_id || null,
      wrestlerId: player.wrestler_id || null,
    }));
  };

  const clearGame = () => {
    ['worldId', 'playerId', 'playerType', 'federationId', 'wrestlerId'].forEach(k =>
      localStorage.removeItem(k)
    );
    setState({ worldId: null, playerId: null, playerType: null, federationId: null, wrestlerId: null });
  };

  return (
    <GameContext.Provider value={{ ...state, setWorld, setPlayer, clearGame }}>
      {children}
    </GameContext.Provider>
  );
}

export function useGame() {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGame must be used within GameProvider');
  return ctx;
}
