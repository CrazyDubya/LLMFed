import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

interface Wrestler {
  id: string; name: string; popularity: number; alignment: string;
  condition: number; is_injured: boolean; is_npc: boolean;
}

export function usePromoterData(worldId: string | null, federationId: string | null) {
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
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState('');

  const loadData = useCallback(async () => {
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
  }, [worldId, federationId]);

  useEffect(() => { loadData(); }, [loadData]);

  const advanceDay = useCallback(async (days: number = 1) => {
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
  }, [worldId, loadData]);

  const signWrestler = useCallback(async (wrestlerId: string) => {
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
  }, [worldId, federationId, advanceDay]);

  return {
    // Data state
    federation,
    roster,
    freeAgents,
    shows,
    championships,
    narrative,
    worldData,
    storylines,
    stables,
    managerBonds,
    managers,
    // UI state
    advancing,
    error,
    setError,
    // Actions
    loadData,
    advanceDay,
    signWrestler,
  };
}
