/**
 * React hook for WebSocket connection to a game world.
 *
 * Provides:
 *  - Real-time event stream from the server (ticks, show completions, etc.)
 *  - Auto-reconnect with exponential backoff
 *  - Callback-based event handling so consumers can react to specific event types
 */

import { useEffect, useRef, useState, useCallback } from 'react';

export interface WorldEvent {
  type: string;
  world_id?: string;
  game_date?: string;
  tick?: number;
  events?: string[];
  description?: string;
  auto?: boolean;
  [key: string]: unknown;
}

interface UseWorldSocketOptions {
  /** Called on every incoming message */
  onMessage?: (event: WorldEvent) => void;
  /** Called specifically on tick events */
  onTick?: (event: WorldEvent) => void;
  /** Called when a show completes */
  onShowCompleted?: (event: WorldEvent) => void;
  /** Auto-reconnect (default true) */
  reconnect?: boolean;
}

export function useWorldSocket(worldId: string | null, options: UseWorldSocketOptions = {}) {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WorldEvent | null>(null);
  const [eventLog, setEventLog] = useState<WorldEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const retryCount = useRef(0);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const connect = useCallback(() => {
    if (!worldId) return;

    // Build WebSocket URL relative to current host
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/${worldId}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      retryCount.current = 0;
    };

    ws.onmessage = (e) => {
      try {
        const data: WorldEvent = JSON.parse(e.data);
        setLastEvent(data);
        setEventLog(prev => [data, ...prev].slice(0, 200));

        // Dispatch to callbacks
        optionsRef.current.onMessage?.(data);

        if (data.type === 'tick') {
          optionsRef.current.onTick?.(data);
        } else if (data.type === 'show_completed') {
          optionsRef.current.onShowCompleted?.(data);
        }
      } catch {
        // ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;

      if (optionsRef.current.reconnect !== false) {
        const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
        retryCount.current++;
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [worldId]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [connect]);

  const send = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { connected, lastEvent, eventLog, send };
}
