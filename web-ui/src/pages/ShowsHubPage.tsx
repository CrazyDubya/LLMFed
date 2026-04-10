/**
 * ShowsHub - central page listing all shows across the wrestling world.
 *
 * Updates automatically via WebSocket when shows complete.
 * Shows are sorted by date, with completed shows displaying ratings,
 * attendance, and financials.  Looks like a real wrestling results site.
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../context/GameContext';
import { useWorldSocket } from '../hooks/useWorldSocket';
import LiveFeed from '../components/LiveFeed';
import SchedulerControls from '../components/SchedulerControls';

interface ShowSummary {
  id: string;
  name: string;
  show_type: string;
  venue: string | null;
  capacity: number;
  attendance: number | null;
  game_date: string;
  is_completed: boolean;
  overall_rating: number | null;
  tv_rating: number | null;
  gate_revenue: number | null;
  ppv_buys: number | null;
  federation_id: string;
  federation_name: string;
}

const typeColors: Record<string, string> = {
  weekly:  'bg-blue-900/50 text-blue-300',
  ppv:     'bg-amber-900/50 text-amber-300',
  special: 'bg-purple-900/50 text-purple-300',
};

function ratingStars(rating: number): string {
  const full = Math.floor(rating);
  const half = rating - full >= 0.25;
  return '\u2605'.repeat(full) + (half ? '\u00BD' : '');
}

export default function ShowsHubPage() {
  const navigate = useNavigate();
  const { worldId } = useGame();
  const [shows, setShows] = useState<ShowSummary[]>([]);
  const [filter, setFilter] = useState<'all' | 'completed' | 'upcoming'>('all');
  const [loading, setLoading] = useState(true);

  const loadShows = useCallback(async () => {
    if (!worldId) return;
    try {
      const res = await fetch(`/worlds/${worldId}/shows?limit=100`);
      if (res.ok) {
        setShows(await res.json());
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [worldId]);

  useEffect(() => { loadShows(); }, [loadShows]);

  // Auto-refresh when ticks or show completions arrive
  const { connected, eventLog } = useWorldSocket(worldId, {
    onTick: () => loadShows(),
    onShowCompleted: () => loadShows(),
  });

  const filtered = shows.filter(s => {
    if (filter === 'completed') return s.is_completed;
    if (filter === 'upcoming') return !s.is_completed;
    return true;
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f0f14] flex items-center justify-center text-gray-400">
        Loading shows...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f0f14]">
      {/* Header */}
      <header className="bg-[#1a1a24] border-b border-gray-800 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-amber-400">Shows Hub</h1>
            <p className="text-sm text-gray-500">
              All wrestling shows across the universe
              <span className={`ml-2 inline-flex items-center gap-1 ${connected ? 'text-green-500' : 'text-red-500'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                {connected ? 'LIVE' : 'OFFLINE'}
              </span>
            </p>
          </div>
          <button
            onClick={() => navigate(-1)}
            className="text-gray-500 hover:text-gray-300 text-sm"
          >
            Back
          </button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 mt-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main content */}
          <div className="lg:col-span-3">
            {/* Filters */}
            <div className="flex gap-2 mb-4">
              {(['all', 'completed', 'upcoming'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-4 py-1.5 text-sm rounded transition ${
                    filter === f
                      ? 'bg-amber-800 text-amber-200'
                      : 'bg-[#1a1a24] text-gray-400 hover:text-gray-200 border border-gray-800'
                  }`}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                  <span className="ml-1.5 text-xs opacity-70">
                    ({shows.filter(s =>
                      f === 'all' ? true : f === 'completed' ? s.is_completed : !s.is_completed
                    ).length})
                  </span>
                </button>
              ))}
            </div>

            {/* Shows grid */}
            {filtered.length === 0 ? (
              <div className="text-center text-gray-500 py-12 bg-[#1a1a24] rounded-lg border border-gray-800">
                No shows found.
              </div>
            ) : (
              <div className="space-y-3">
                {filtered.map(show => (
                  <div
                    key={show.id}
                    onClick={() => navigate(`/show/${show.id}`)}
                    className="bg-[#1a1a24] rounded-lg border border-gray-800 hover:border-gray-700 cursor-pointer transition overflow-hidden"
                  >
                    <div className="flex items-center justify-between p-4">
                      {/* Left: show info */}
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            typeColors[show.show_type] || 'bg-gray-800 text-gray-300'
                          }`}>
                            {show.show_type.toUpperCase()}
                          </span>
                          <h3 className="text-lg font-semibold text-white">{show.name}</h3>
                          {show.is_completed && (
                            <span className="px-2 py-0.5 rounded text-xs bg-green-900/50 text-green-300">
                              COMPLETED
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-gray-400">
                          <span>{show.game_date}</span>
                          <span>{show.federation_name}</span>
                          {show.venue && <span>{show.venue}</span>}
                        </div>
                      </div>

                      {/* Right: stats (completed shows only) */}
                      {show.is_completed && (
                        <div className="flex items-center gap-6 text-right">
                          {show.overall_rating != null && (
                            <div>
                              <div className="text-amber-400 text-lg font-bold">
                                {ratingStars(show.overall_rating)}
                              </div>
                              <div className="text-xs text-gray-500">{show.overall_rating.toFixed(1)}</div>
                            </div>
                          )}
                          {show.attendance != null && (
                            <div>
                              <div className="text-white font-semibold">
                                {show.attendance.toLocaleString()}
                              </div>
                              <div className="text-xs text-gray-500">attendance</div>
                            </div>
                          )}
                          {show.gate_revenue != null && (
                            <div>
                              <div className="text-green-400 font-semibold">
                                ${(show.gate_revenue / 1000).toFixed(0)}k
                              </div>
                              <div className="text-xs text-gray-500">gate</div>
                            </div>
                          )}
                          {show.tv_rating != null && (
                            <div>
                              <div className="text-blue-400 font-semibold">
                                {show.tv_rating.toFixed(1)}
                              </div>
                              <div className="text-xs text-gray-500">TV rating</div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            <SchedulerControls />
            <LiveFeed events={eventLog} connected={connected} />
          </div>
        </div>
      </div>
    </div>
  );
}
