import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { api, type Championship, type World, type WorldNewsArticle } from '../api/client';
import { getErrorMessage } from '../utils/errors';
import type { WorldEvent } from './useWorldSocket';

interface Wrestler {
  id: string; name: string; popularity: number; alignment: string;
  condition: number; is_injured: boolean; is_npc: boolean;
}

type PromoterChampionship = Championship & { holderName: string | null };

const unknownTick = -Infinity;

function tickNumber(tick: unknown) {
  return typeof tick === 'number' && Number.isFinite(tick) ? tick : unknownTick;
}

type Scope = { worldId: string | null; federationId: string | null };

function createRefreshState(scope: Scope) {
  return {
    scope,
    active: true,
    running: null as Promise<void> | null,
    queuedTick: null as number | null,
    coveredTick: unknownTick,
    lastSocketTick: unknownTick,
    advancing: 0,
    deferredTick: null as number | null,
  };
}

type RefreshState = ReturnType<typeof createRefreshState>;

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
  const [advancingScope, setAdvancingScope] = useState<Scope | null>(null);
  const [error, setError] = useState('');

  const scope = useMemo(() => ({ worldId, federationId }), [worldId, federationId]);
  const refreshRef = useRef<RefreshState | null>(null);
  const getRefresh = useCallback(() => {
    const refresh = refreshRef.current;
    return refresh?.scope === scope ? refresh : null;
  }, [scope]);

  const fetchData = useCallback(async (refresh: RefreshState) => {
    const { worldId, federationId } = refresh.scope;
    if (!worldId || !federationId) return;
    try {
      const requests = [
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
      ] as const;
      const [fed, rost, agents, sh, champs, articles, world, sls, stbs, bonds, mgrs] =
        await Promise.all(requests).catch(async err => {
          await Promise.allSettled(requests);
          throw err;
        });
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
      if (!refresh.active) return;
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
      if (refresh.active) setError(getErrorMessage(err));
    }
  }, []);

  const requestRefresh = useCallback(async (refresh: RefreshState | null, tick: number) => {
    if (!refresh?.active || !refresh.scope.worldId || !refresh.scope.federationId) return;
    refresh.queuedTick = Math.max(refresh.queuedTick ?? unknownTick, tick);
    return refresh.running ??= Promise.resolve().then(async () => {
      try {
        while (refresh.active && refresh.queuedTick !== null) {
          refresh.coveredTick = Math.max(refresh.coveredTick, refresh.queuedTick);
          refresh.queuedTick = null;
          await fetchData(refresh);
        }
      } finally {
        refresh.running = null;
      }
    });
  }, [fetchData]);

  const loadData = useCallback(() => requestRefresh(getRefresh(), unknownTick), [getRefresh, requestRefresh]);

  useEffect(() => {
    const refresh = createRefreshState(scope);
    refreshRef.current = refresh;
    requestRefresh(refresh, unknownTick);
    return () => {
      refresh.active = false;
      refreshRef.current = null;
    };
  }, [requestRefresh, scope]);

  const refreshFromSocket = useCallback((refresh: RefreshState, tick: number) => {
    if (refresh.advancing > 0) {
      refresh.deferredTick = Math.max(refresh.deferredTick ?? unknownTick, tick);
    } else {
      requestRefresh(refresh, tick);
    }
  }, [requestRefresh]);

  const onTick = useCallback((event: WorldEvent) => {
    const refresh = getRefresh();
    if (!refresh || (event.world_id && event.world_id !== worldId)) return;
    const tick = refresh.lastSocketTick = tickNumber(event.tick);
    if (tick === unknownTick || tick > refresh.coveredTick) refreshFromSocket(refresh, tick);
  }, [getRefresh, refreshFromSocket, worldId]);

  const onShowCompleted = useCallback((event: WorldEvent) => {
    const refresh = getRefresh();
    if (!refresh || (event.world_id && event.world_id !== worldId)) return;
    const tick = refresh.lastSocketTick;
    // The server commits the show's data before broadcasting its tick.
    if (tick === unknownTick || tick > refresh.coveredTick) refreshFromSocket(refresh, tick);
  }, [getRefresh, refreshFromSocket, worldId]);

  const onReconnect = useCallback(() => {
    const refresh = getRefresh();
    if (refresh) refresh.lastSocketTick = unknownTick;
    return requestRefresh(refresh, unknownTick);
  }, [getRefresh, requestRefresh]);

  const advanceDay = useCallback(async (days: number = 1) => {
    const refresh = getRefresh();
    if (!worldId || !refresh) return;
    setAdvancingScope(scope);
    refresh.advancing++;
    try {
      let tick: number;
      try {
        const result = await api.advanceWorld(worldId, days);
        tick = tickNumber(result.current_tick);
      } finally {
        refresh.advancing--;
      }
      const deferredTick = refresh.deferredTick;
      refresh.deferredTick = null;
      await requestRefresh(refresh, Math.max(tick, deferredTick ?? unknownTick));
    } catch (err) {
      if (!refresh.active) return;
      setError(getErrorMessage(err));
      if (!refresh.advancing && refresh.deferredTick !== null) {
        const tick = refresh.deferredTick;
        refresh.deferredTick = null;
        await requestRefresh(refresh, tick);
      }
    } finally {
      if (refresh.active && !refresh.advancing) setAdvancingScope(null);
    }
  }, [worldId, scope, getRefresh, requestRefresh]);

  const signWrestler = useCallback(async (wrestlerId: string) => {
    const refresh = getRefresh();
    if (!worldId || !federationId || !refresh) return;
    try {
      await api.submitAction(worldId, 'sign_wrestler', {
        wrestler_id: wrestlerId,
        federation_id: federationId,
        salary_weekly: 2000,
      });
      if (refresh.active) await advanceDay(1);
    } catch (err) {
      if (refresh.active) setError(getErrorMessage(err));
    }
  }, [worldId, federationId, advanceDay, getRefresh]);

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
    advancing: advancingScope === scope,
    error,
    setError,
    onTick,
    onShowCompleted,
    onReconnect,
    // Actions
    loadData,
    advanceDay,
    signWrestler,
  };
}
