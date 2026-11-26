import { useState, useEffect, useCallback } from 'react';
import { api, type Championship, type World, type WorldNewsArticle } from '../api/client';
import { getErrorMessage } from '../utils/errors';

interface Wrestler {
  id: string; name: string; popularity: number; alignment: string;
  condition: number; is_injured: boolean; is_npc: boolean;
}

type PromoterChampionship = Championship & { holderName: string | null };

export function usePromoterData(worldId: string | null, federationId: string | null) {
  const [federation, setFederation] = useState<any>(null);
  const [roster, setRoster] = useState<Wrestler[]>([]);
  const [freeAgents, setFreeAgents] = useState<Wrestler[]>([]);
  const [shows, setShows] = useState<any[]>([]);
  const [championships, setChampionships] = useState<PromoterChampionship[]>([]);
  const [news, setNews] = useState<WorldNewsArticle[] | 'error' | null>(null);
  const [worldData, setWorldData] = useState<World | null>(null);
  const [storylines, setStorylines] = useState<any[]>([]);
  const [stables, setStables] = useState<any[]>([]);
  const [managerBonds, setManagerBonds] = useState<any[]>([]);
  const [managers, setManagers] = useState<any[]>([]);
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState('');

  const loadData = useCallback(async () => {
    if (!worldId || !federationId) return;
    try {
      const [fed, rost, agents, sh, champs, articles, world, sls, stbs, bonds, mgrs] = await Promise.all([
        api.getFederation(federationId),
        api.getRoster(federationId),
        api.listFreeAgents(worldId),
        api.getShows(federationId),
        api.getChampionships(federationId),
        api.getNews(worldId).catch(() => 'error' as const),
        api.getWorld(worldId),
        api.listStorylines(worldId, undefined, federationId),
        api.listStables(worldId, federationId).catch(() => []),
        api.listManagerBonds(worldId, federationId).catch(() => []),
        api.listManagers(worldId, federationId).catch(() => []),
      ]);
      const wrestlerNames = new Map<string, string>(
        [...agents, ...rost].map((w: Wrestler) => [w.id, w.name]),
      );
      const missingHolderIds = new Set(champs.flatMap(({ current_holder_id }) =>
        current_holder_id && !wrestlerNames.has(current_holder_id) ? [current_holder_id] : [],
      ));
      await Promise.all([...missingHolderIds].map(async id => {
        const detail = await api.getWrestler(id).catch(() => null);
        if (detail?.wrestler?.name) wrestlerNames.set(id, detail.wrestler.name);
      }));
      setFederation(fed);
      setRoster(rost);
      setFreeAgents(agents);
      setShows(sh);
      setChampionships(champs.map(champ => ({
        ...champ,
        holderName: champ.current_holder_id ? wrestlerNames.get(champ.current_holder_id) ?? null : null,
      })));
      setNews(articles);
      setWorldData(world);
      setStorylines(sls);
      setStables(stbs);
      setManagerBonds(bonds);
      setManagers(mgrs);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }, [worldId, federationId]);

  useEffect(() => { loadData(); }, [loadData]);

  const advanceDay = useCallback(async (days: number = 1) => {
    if (!worldId) return;
    setAdvancing(true);
    try {
      await api.advanceWorld(worldId, days);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err));
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
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }, [worldId, federationId, advanceDay]);

  return {
    // Data state
    federation,
    roster,
    freeAgents,
    shows,
    championships,
    news,
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
