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

  constructor(url: string) {
    this.url = url;
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
  it('sends the signed-in token with the handshake', () => {
    auth.token = 'a.b+c';
    renderHook(() => useWorldSocket('world'));
    expect(MockWebSocket.instances[0].url).toBe('ws://localhost:3000/ws/world?token=a.b%2Bc');
  });

  it('does not connect when signed out', () => {
    auth.token = null;
    renderHook(() => useWorldSocket('world'));
    act(() => vi.advanceTimersByTime(60000));
    expect(MockWebSocket.instances).toHaveLength(0);
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
