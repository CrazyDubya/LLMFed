/**
 * SchedulerControls - UI for the auto-ticker scheduler.
 *
 * Start/stop the auto-ticker and configure its interval.
 */

import { useState, useEffect } from 'react';

interface SchedulerStatus {
  running: boolean;
  interval_seconds: number;
  ticks_completed: number;
  last_tick_at: string | null;
  paused_worlds: string[];
  recent_errors: string[];
}

async function fetchStatus(): Promise<SchedulerStatus> {
  const res = await fetch('/scheduler/status');
  return res.json();
}

async function startScheduler(interval: number): Promise<SchedulerStatus> {
  const res = await fetch('/scheduler/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ interval_seconds: interval }),
  });
  return res.json();
}

async function stopScheduler(): Promise<SchedulerStatus> {
  const res = await fetch('/scheduler/stop', { method: 'POST' });
  return res.json();
}

export default function SchedulerControls() {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [interval, setInterval_] = useState(60);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    try {
      setStatus(await fetchStatus());
    } catch { /* ignore */ }
  };

  useEffect(() => { refresh(); }, []);

  const handleStart = async () => {
    setLoading(true);
    try {
      setStatus(await startScheduler(interval));
    } catch { /* ignore */ }
    setLoading(false);
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      setStatus(await stopScheduler());
    } catch { /* ignore */ }
    setLoading(false);
  };

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
          {status?.running ? 'Running' : 'Stopped'}
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
            onClick={handleStart}
            disabled={loading}
            className="flex-1 px-3 py-1.5 bg-green-800 hover:bg-green-700 text-green-200 text-sm rounded transition disabled:opacity-50"
          >
            {loading ? 'Starting...' : 'Start Auto-Tick'}
          </button>
        ) : (
          <button
            onClick={handleStop}
            disabled={loading}
            className="flex-1 px-3 py-1.5 bg-red-900 hover:bg-red-800 text-red-200 text-sm rounded transition disabled:opacity-50"
          >
            {loading ? 'Stopping...' : 'Stop Auto-Tick'}
          </button>
        )}
        <button
          onClick={refresh}
          className="px-3 py-1.5 border border-gray-700 text-gray-400 hover:text-gray-200 text-sm rounded transition"
        >
          Refresh
        </button>
      </div>

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
