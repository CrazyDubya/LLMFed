import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Player } from '../api/client';
import { useAuth } from './AuthContext';

interface GameState {
  worldId: string | null;
  playerId: string | null;
  playerType: 'promoter' | 'wrestler' | null;
  federationId: string | null;
  wrestlerId: string | null;
}

interface GameContextType extends GameState {
  savedWorldId: string | null;
  setGame: (worldId: string, player: Player) => void;
  clearGame: () => void;
}

const GameContext = createContext<GameContextType | null>(null);

export function GameProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const savedWorldKey = user ? `savedWorldId:${user.id}` : null;
  const [state, setState] = useState<GameState>({
    worldId: localStorage.getItem('worldId'),
    playerId: localStorage.getItem('playerId'),
    playerType: localStorage.getItem('playerType') as 'promoter' | 'wrestler' | null,
    federationId: localStorage.getItem('federationId'),
    wrestlerId: localStorage.getItem('wrestlerId'),
  });

  const setGame = (worldId: string, player: Player) => {
    const game: GameState = {
      worldId,
      playerId: player.id,
      playerType: player.player_type,
      federationId: player.federation_id ?? null,
      wrestlerId: player.wrestler_id ?? null,
    };
    for (const [key, value] of Object.entries(game)) {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    }
    setState(game);
  };

  const clearGame = () => {
    if (savedWorldKey && state.worldId && state.playerId) {
      localStorage.setItem(savedWorldKey, state.worldId);
    }
    ['worldId', 'playerId', 'playerType', 'federationId', 'wrestlerId'].forEach(k =>
      localStorage.removeItem(k)
    );
    setState({ worldId: null, playerId: null, playerType: null, federationId: null, wrestlerId: null });
  };

  const savedWorldId = savedWorldKey ? localStorage.getItem(savedWorldKey) : null;
  return (
    <GameContext.Provider value={{ ...state, savedWorldId, setGame, clearGame }}>
      {children}
    </GameContext.Provider>
  );
}

export function useGame() {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGame must be used within GameProvider');
  return ctx;
}
