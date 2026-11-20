/**
 * SchedulerControls - UI for the auto-ticker scheduler.
 *
 * Start/stop the auto-ticker and configure its interval.
 */

import { useState, useEffect, useCallback } from 'react';
import { api, type SchedulerStatus } from '../api/client';
import { getErrorMessage } from '../utils/errors';

const actionErrors = {
  refresh: 'Could not load auto-ticker status',
  start: 'Could not start auto-tick',
  stop: 'Could not stop auto-tick',
};

type Action = keyof typeof actionErrors;

export default function SchedulerControls() {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [interval, setInterval_] = useState(60);
  const [pending, setPending] = useState<Action | null>('refresh');
  const [error, setError] = useState<string | null>(null);

  const updateStatus = useCallback(async (
    action: Action,
    request: () => Promise<SchedulerStatus>,
    signal?: AbortSignal,
  ) => {
    try {
      const nextStatus = await request();
      if (!signal?.aborted) setStatus(nextStatus);
    } catch (err) {
      if (!signal?.aborted) setError(`${actionErrors[action]}: ${getErrorMessage(err)}`);
    } finally {
      if (!signal?.aborted) setPending(null);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    updateStatus('refresh', () => api.getSchedulerStatus(controller.signal), controller.signal);
    return () => controller.abort();
  }, [updateStatus]);

  const runAction = (action: Action, request: () => Promise<SchedulerStatus>) => {
    setPending(action);
    setError(null);
    void updateStatus(action, request);
  };

  const statusLabel = status ? (status.running ? 'Running' : 'Stopped') : (pending ? 'Checking...' : 'Unknown');

  return (
    <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300">Auto-Ticker</h3>
        <span className={`flex items-center gap-1.5 text-xs ${
          status?.running ? 'text-green-400' : 'text-gray-500'
        }`}>
          <span className={`w-2 h-2 rounded-full ${
            status?.running ? 'bg-green-500 animate-pulse' : 'bg-gray-600'
          }`} />
          {statusLabel}
        </span>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <label className="text-xs text-gray-500">Interval (sec):</label>
        <input
          type="number"
          min={10}
          max={3600}
          value={interval}
          onChange={e => setInterval_(Number(e.target.value))}
          className="w-20 bg-[#0f0f14] border border-gray-700 rounded px-2 py-1 text-sm text-gray-300"
        />
      </div>

      <div className="flex gap-2">
        {!status?.running ? (
          <button
            onClick={() => runAction('start', () => api.startScheduler(interval))}
            disabled={pending !== null}
            className="flex-1 px-3 py-1.5 bg-green-800 hover:bg-green-700 text-green-200 text-sm rounded transition disabled:opacity-50"
          >
            {pending === 'start' ? 'Starting...' : 'Start Auto-Tick'}
          </button>
        ) : (
          <button
            onClick={() => runAction('stop', api.stopScheduler)}
            disabled={pending !== null}
            className="flex-1 px-3 py-1.5 bg-red-900 hover:bg-red-800 text-red-200 text-sm rounded transition disabled:opacity-50"
          >
            {pending === 'stop' ? 'Stopping...' : 'Stop Auto-Tick'}
          </button>
        )}
        <button
          onClick={() => runAction('refresh', api.getSchedulerStatus)}
          disabled={pending !== null}
          className="px-3 py-1.5 border border-gray-700 text-gray-400 hover:text-gray-200 text-sm rounded transition disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div role="alert" className="mt-2 p-2 bg-red-900/20 border border-red-800/50 rounded text-xs text-red-400">
          {error}
        </div>
      )}

      {status && status.ticks_completed > 0 && (
        <div className="mt-3 text-xs text-gray-500">
          {status.ticks_completed} ticks completed
          {status.last_tick_at && (
            <span> | Last: {new Date(status.last_tick_at).toLocaleTimeString()}</span>
          )}
        </div>
      )}

      {status?.recent_errors && status.recent_errors.length > 0 && (
        <div className="mt-2 p-2 bg-red-900/20 border border-red-800/50 rounded text-xs text-red-400">
          {status.recent_errors[status.recent_errors.length - 1]}
        </div>
      )}
    </div>
  );
}
