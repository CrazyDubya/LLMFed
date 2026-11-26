import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { getErrorMessage } from '../utils/errors';
import type { WorldEvent } from './useWorldSocket';

const unknownTick = -Infinity;
const tickNumber = (tick: unknown) => typeof tick === 'number' && Number.isFinite(tick) ? tick : unknownTick;

type Scope = { worldId: string | null; wrestlerId: string | null };

function createRefresh(scope: Scope) {
  return {
    scope,
    active: true,
    running: null as Promise<void> | null,
    queuedTick: null as number | null,
    inFlightTick: unknownTick,
    coveredTick: unknownTick,
    lastSocketTick: unknownTick,
    timeline: 0,
    advancing: 0,
    deferredTick: null as number | null,
  };
}

type Refresh = ReturnType<typeof createRefresh>;

function resetCoverage(refresh: Refresh) {
  refresh.timeline++;
  refresh.coveredTick = refresh.inFlightTick = unknownTick;
  if (refresh.queuedTick !== null) refresh.queuedTick = unknownTick;
  if (refresh.deferredTick !== null) refresh.deferredTick = unknownTick;
}

export function useWrestlerRefresh(
  worldId: string | null,
  wrestlerId: string | null,
  loadData: (worldId: string, wrestlerId: string) => Promise<() => void>,
  setError: (message: string) => void,
) {
  const scope = useMemo(() => ({ worldId, wrestlerId }), [worldId, wrestlerId]);
  const refreshRef = useRef<Refresh | null>(null);
  const [advancingScope, setAdvancingScope] = useState<Scope | null>(null);
  const getRefresh = useCallback(() => {
    const refresh = refreshRef.current;
    return refresh?.scope === scope ? refresh : null;
  }, [scope]);

  const requestRefresh = useCallback((refresh: Refresh | null, tick: number) => {
    const worldId = refresh?.scope.worldId;
    const wrestlerId = refresh?.scope.wrestlerId;
    if (!refresh?.active || !worldId || !wrestlerId) return;
    refresh.queuedTick = Math.max(refresh.queuedTick ?? unknownTick, tick);
    return refresh.running ??= Promise.resolve().then(async () => {
      try {
        while (refresh.active && refresh.queuedTick !== null) {
          const { timeline, queuedTick } = refresh;
          refresh.inFlightTick = queuedTick;
          refresh.queuedTick = null;
          try {
            const applyData = await loadData(worldId, wrestlerId);
            if (refresh.active && refresh.timeline === timeline) {
              applyData();
              refresh.coveredTick = Math.max(refresh.coveredTick, queuedTick);
            }
          } catch (err) {
            if (refresh.active && refresh.timeline === timeline) setError(getErrorMessage(err));
          } finally {
            refresh.inFlightTick = unknownTick;
          }
        }
      } finally {
        refresh.running = null;
      }
    });
  }, [loadData, setError]);

  useEffect(() => {
    const refresh = createRefresh(scope);
    refreshRef.current = refresh;
    requestRefresh(refresh, unknownTick);
    return () => {
      refresh.active = false;
      refreshRef.current = null;
    };
  }, [requestRefresh, scope]);

  const refreshFromSocket = useCallback((refresh: Refresh, tick: number) => {
    if (tick !== unknownTick && tick <= Math.max(refresh.coveredTick, refresh.inFlightTick)) return;
    if (refresh.advancing) refresh.deferredTick = Math.max(refresh.deferredTick ?? unknownTick, tick);
    else requestRefresh(refresh, tick);
  }, [requestRefresh]);

  const onTick = useCallback((event: WorldEvent) => {
    const refresh = getRefresh();
    if (!refresh || (event.world_id && event.world_id !== worldId)) return;
    const tick = tickNumber(event.tick);
    if (tick !== unknownTick && tick <= refresh.lastSocketTick) resetCoverage(refresh);
    refresh.lastSocketTick = tick;
    refreshFromSocket(refresh, tick);
  }, [getRefresh, refreshFromSocket, worldId]);

  const onShowCompleted = useCallback((event: WorldEvent) => {
    const refresh = getRefresh();
    if (!refresh || (event.world_id && event.world_id !== worldId)) return;
    // The tick is broadcast after show data commits and before show notifications.
    refreshFromSocket(refresh, refresh.lastSocketTick);
  }, [getRefresh, refreshFromSocket, worldId]);

  const onReconnect = useCallback(() => {
    const refresh = getRefresh();
    if (refresh) {
      resetCoverage(refresh);
      refresh.lastSocketTick = unknownTick;
    }
    return requestRefresh(refresh, unknownTick);
  }, [getRefresh, requestRefresh]);

  const advanceDay = useCallback(async (days = 1) => {
    const refresh = getRefresh();
    if (!worldId || !refresh) return;
    const { timeline } = refresh;
    setAdvancingScope(scope);
    refresh.advancing++;
    try {
      let tick: number;
      try {
        const result = await api.advanceWorld(worldId, days);
        tick = timeline === refresh.timeline ? tickNumber(result.current_tick) : unknownTick;
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
  }, [getRefresh, requestRefresh, scope, setError, worldId]);

  return { advancing: advancingScope === scope, advanceDay, onTick, onShowCompleted, onReconnect };
}
