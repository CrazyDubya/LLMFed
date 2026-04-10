/**
 * LiveFeed - real-time scrolling event ticker.
 *
 * Shows WebSocket events as they arrive: ticks, show completions,
 * narrative events, etc.  Sits at the bottom or side of any dashboard.
 */

import { type WorldEvent } from '../hooks/useWorldSocket';

interface LiveFeedProps {
  events: WorldEvent[];
  connected: boolean;
  maxItems?: number;
}

function eventIcon(type: string): string {
  switch (type) {
    case 'tick':          return '\u23F1';
    case 'show_completed': return '\u2B50';
    case 'connected':     return '\u2705';
    case 'pong':          return '\u2764';
    default:              return '\u26A1';
  }
}

function eventColor(type: string): string {
  switch (type) {
    case 'tick':           return 'text-cyan-400';
    case 'show_completed': return 'text-amber-400';
    case 'connected':      return 'text-green-400';
    default:               return 'text-gray-400';
  }
}

function formatEvent(ev: WorldEvent): string {
  if (ev.type === 'tick') {
    const events = ev.events || [];
    if (events.length > 0) {
      return `Day ${ev.game_date}: ${events.length} event${events.length === 1 ? '' : 's'}`;
    }
    return `Day ${ev.game_date} — quiet day`;
  }
  if (ev.type === 'show_completed') {
    return ev.description || 'A show has been completed!';
  }
  if (ev.type === 'connected') {
    return 'Connected to live feed';
  }
  return ev.description || ev.type;
}

export default function LiveFeed({ events, connected, maxItems = 50 }: LiveFeedProps) {
  const visible = events.filter(e => e.type !== 'pong').slice(0, maxItems);

  return (
    <div className="bg-[#12121a] border border-gray-800 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#1a1a24] border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-300">Live Feed</span>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
        </div>
        <span className="text-xs text-gray-600">{events.length} events</span>
      </div>

      {/* Events list */}
      <div className="max-h-64 overflow-y-auto">
        {visible.length === 0 ? (
          <div className="px-4 py-6 text-center text-gray-600 text-sm">
            {connected ? 'Waiting for events...' : 'Not connected'}
          </div>
        ) : (
          <div className="divide-y divide-gray-800/50">
            {visible.map((ev, i) => (
              <div key={i} className="px-4 py-2 flex items-start gap-2 hover:bg-[#1a1a24]/50">
                <span className="text-sm mt-0.5">{eventIcon(ev.type)}</span>
                <div className="flex-1 min-w-0">
                  <span className={`text-sm ${eventColor(ev.type)}`}>
                    {formatEvent(ev)}
                  </span>
                  {/* Show sub-events for ticks */}
                  {ev.type === 'tick' && ev.events && ev.events.length > 0 && (
                    <div className="mt-1 space-y-0.5">
                      {ev.events.slice(0, 5).map((e, j) => (
                        <div key={j} className="text-xs text-gray-500 truncate pl-2 border-l border-gray-700">
                          {e}
                        </div>
                      ))}
                      {ev.events.length > 5 && (
                        <div className="text-xs text-gray-600 pl-2">
                          +{ev.events.length - 5} more
                        </div>
                      )}
                    </div>
                  )}
                </div>
                {ev.auto && (
                  <span className="text-[10px] text-gray-600 bg-gray-800 px-1.5 py-0.5 rounded">
                    auto
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
