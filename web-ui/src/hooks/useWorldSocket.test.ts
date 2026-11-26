// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorldSocket } from './useWorldSocket';

const auth = vi.hoisted(() => ({ token: 'jwt' as string | null }));
vi.mock('../context/AuthContext', () => ({ useAuth: () => auth }));

class MockWebSocket {
  static OPEN = 1;
  static instances: MockWebSocket[] = [];
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => { this.readyState = 3; });

  url: string;
  protocols?: string[];

  constructor(url: string, protocols?: string[]) {
    this.url = url;
    this.protocols = protocols;
    MockWebSocket.instances.push(this);
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  MockWebSocket.instances = [];
  auth.token = 'jwt';
  vi.stubGlobal('WebSocket', MockWebSocket);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('world feed auth', () => {
  it('sends the signed-in token as a subprotocol, not in the URL', () => {
    auth.token = 'header.payload.signature';
    renderHook(() => useWorldSocket('world'));
    expect(MockWebSocket.instances[0].url).toBe('ws://localhost:3000/ws/world');
    expect(MockWebSocket.instances[0].protocols).toEqual(['bearer', 'header.payload.signature']);
  });

  it('does not connect when signed out', () => {
    auth.token = null;
    renderHook(() => useWorldSocket('world'));
    act(() => vi.advanceTimersByTime(60000));
    expect(MockWebSocket.instances).toHaveLength(0);
  });
});

describe('world feed reconnect', () => {
  it('notifies only after a retry opens, not during failed retries or on a new world', () => {
    const onReconnect = vi.fn();
    const { rerender } = renderHook(({ world }) => useWorldSocket(world, { onReconnect }), {
      initialProps: { world: 'first' },
    });
    act(() => MockWebSocket.instances[0].open());
    act(() => MockWebSocket.instances[0].onclose?.());
    act(() => vi.advanceTimersByTime(1000));
    act(() => MockWebSocket.instances[1].onclose?.());
    act(() => vi.advanceTimersByTime(2000));
    expect(onReconnect).not.toHaveBeenCalled();

    act(() => MockWebSocket.instances[2].open());
    expect(onReconnect).toHaveBeenCalledTimes(1);

    rerender({ world: 'next' });
    act(() => MockWebSocket.instances[3].open());
    expect(onReconnect).toHaveBeenCalledTimes(1);
  });
});

describe('world feed heartbeat', () => {
  it('sends recurring pings before the 60-second timeout only after opening', () => {
    renderHook(() => useWorldSocket('world'));
    const ws = MockWebSocket.instances[0];
    act(() => vi.advanceTimersByTime(60000));
    expect(ws.send).not.toHaveBeenCalled();
    act(() => ws.open());
    act(() => vi.advanceTimersByTime(25000));
    expect(ws.send).toHaveBeenCalledExactlyOnceWith('{"type":"ping"}');
    act(() => vi.advanceTimersByTime(25000));
    expect(ws.send).toHaveBeenCalledTimes(2);
  });

  it('does not connect or start a timer without a world', () => {
    renderHook(() => useWorldSocket(null));
    act(() => vi.advanceTimersByTime(60000));
    expect(MockWebSocket.instances).toHaveLength(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('keeps heartbeat replies out of the event log without evicting real events', () => {
    const onTick = vi.fn();
    const { result } = renderHook(() => useWorldSocket('world', { onTick }));
    const ws = MockWebSocket.instances[0];
    const tick = { type: 'tick', tick: 1 };
    act(() => {
      ws.open();
      ws.onmessage?.({ data: JSON.stringify(tick) });
      for (let i = 0; i < 200; i++) {
        ws.onmessage?.({ data: '{"type":"pong"}' });
      }
    });

    expect(result.current.eventLog).toHaveLength(1);
    expect(result.current.eventLog).toEqual([tick]);
    expect(result.current.lastEvent).toEqual(tick);
    expect(onTick).toHaveBeenCalledExactlyOnceWith(tick);
    expect(result.current.connected).toBe(true);
  });

  it.each(['close', 'error', 'unmount'] as const)('clears the heartbeat on %s', (event) => {
    const { unmount } = renderHook(() => useWorldSocket('world', { reconnect: false }));
    const ws = MockWebSocket.instances[0];
    act(() => ws.open());
    act(() => vi.advanceTimersByTime(25000));
    expect(ws.send).toHaveBeenCalledTimes(1);
    act(() => {
      if (event === 'unmount') unmount();
      else if (event === 'close') ws.onclose?.();
      else ws.onerror?.();
    });
    expect(vi.getTimerCount()).toBe(0);
    act(() => vi.advanceTimersByTime(60000));
    expect(ws.send).toHaveBeenCalledTimes(1);
  });

  it('does not send while the transport is closing', () => {
    renderHook(() => useWorldSocket('world'));
    const ws = MockWebSocket.instances[0];
    act(() => ws.open());
    ws.readyState = 2;
    act(() => vi.advanceTimersByTime(60000));
    expect(ws.send).not.toHaveBeenCalled();
  });

  it('restarts a single heartbeat on reconnect and clears it when the world changes', () => {
    const { rerender } = renderHook(({ world }) => useWorldSocket(world), { initialProps: { world: 'first' } });
    const first = MockWebSocket.instances[0];
    act(() => first.open());
    act(() => first.onclose?.());
    act(() => vi.advanceTimersByTime(1000));
    const second = MockWebSocket.instances[1];
    act(() => second.open());
    act(() => vi.advanceTimersByTime(25000));
    expect(first.send).not.toHaveBeenCalled();
    expect(second.send).toHaveBeenCalledTimes(1);
    rerender({ world: 'next' });
    expect(second.close).toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    const third = MockWebSocket.instances[2];
    act(() => third.open());
    act(() => vi.advanceTimersByTime(25000));
    expect(second.send).toHaveBeenCalledTimes(1);
    expect(third.send).toHaveBeenCalledTimes(1);
  });
});
