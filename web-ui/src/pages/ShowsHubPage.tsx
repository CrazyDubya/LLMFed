/**
 * ShowsHub - central page listing all shows across the wrestling world.
 *
 * Updates automatically via WebSocket when shows complete.
 * Shows are sorted by date, with completed shows displaying ratings,
 * attendance, and financials.  Looks like a real wrestling results site.
 */

import { useState } from 'react';
import { skipToken, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api, type ShowStatus } from '../api/client';
import { useGame } from '../context/GameContext';
import { useWorldSocket } from '../hooks/useWorldSocket';
import LiveFeed from '../components/LiveFeed';
import SchedulerControls from '../components/SchedulerControls';
import { getErrorMessage } from '../utils/errors';

const pageSize = 25;
const pageButtonClass = 'rounded border border-gray-800 bg-[#1a1a24] px-3 py-1 text-gray-300 hover:border-gray-600 disabled:opacity-50';

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
  const { worldId } = useGame();
  return <ShowsHub key={worldId} worldId={worldId} />;
}

function ShowsHub({ worldId }: { worldId: string | null }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<ShowStatus>('all');
  const [page, setPage] = useState(0);
  const { data, error, isPending, isPlaceholderData } = useQuery({
    queryKey: ['world-shows', worldId, filter, page],
    queryFn: worldId
      ? ({ signal }) => api.getWorldShowsPage(worldId, filter, pageSize, page * pageSize, signal)
      : skipToken,
    placeholderData: previous => previous,
    retry: false,
  });
  const totalPages = Math.ceil((data?.counts[filter] ?? 0) / pageSize);
  const refreshShows = () => queryClient.invalidateQueries({ queryKey: ['world-shows', worldId] });

  // Auto-refresh when ticks or show completions arrive
  const { connected, eventLog } = useWorldSocket(worldId, {
    onTick: refreshShows,
    onShowCompleted: refreshShows,
  });

  if (isPending) {
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
            {data && error === null && <div className="flex gap-2 mb-4">
              {(['all', 'completed', 'upcoming'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => {
                    if (filter !== f) {
                      setFilter(f);
                      setPage(0);
                    }
                  }}
                  className={`px-4 py-1.5 text-sm rounded transition ${
                    filter === f
                      ? 'bg-amber-800 text-amber-200'
                      : 'bg-[#1a1a24] text-gray-400 hover:text-gray-200 border border-gray-800'
                  }`}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}{' '}
                  <span className="ml-1.5 text-xs opacity-70">
                    {`(${data.counts[f]})`}
                  </span>
                </button>
              ))}
            </div>}

            {error === null && (totalPages > 1 || page > 0) && (
              <nav aria-label="Shows pagination" className="mb-4 flex items-center gap-3 text-sm text-gray-400">
                <button type="button" className={pageButtonClass} disabled={isPlaceholderData || page === 0}
                  onClick={() => setPage(Math.max(0, Math.min(page - 1, totalPages - 1)))}>
                  Previous
                </button>
                <span>{page < totalPages ? `Page ${page + 1} of ${totalPages}` : `${totalPages} pages`}</span>
                <button type="button" className={pageButtonClass} disabled={isPlaceholderData || page + 1 >= totalPages}
                  onClick={() => setPage(page + 1)}>
                  Next
                </button>
              </nav>
            )}

            {/* Shows grid */}
            {error !== null ? (
              <div role="alert" className="rounded-lg border border-red-800/50 bg-red-900/20 p-4 text-sm text-red-400">
                Could not load shows: {getErrorMessage(error)}
              </div>
            ) : isPlaceholderData ? (
              <div role="status" className="py-12 text-center text-gray-400">Loading shows...</div>
            ) : !data?.shows.length ? (
              <div className="text-center text-gray-500 py-12 bg-[#1a1a24] rounded-lg border border-gray-800">
                {page > 0 ? 'This page is no longer available.' : 'No shows found.'}
              </div>
            ) : (
              <div className="space-y-3">
                {data.shows.map(show => (
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
