import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';

interface Segment {
  id: string;
  position: number;
  segment_type: string;
  match_id: string | null;
  description: string | null;
  planned_duration_minutes: number;
  actual_duration_minutes: number | null;
  rating: number | null;
  crowd_reaction: string | null;
  is_completed: boolean;
}

interface MatchResult {
  id: string;
  match_type: string;
  stipulation: string | null;
  is_title_match: boolean;
  winner_id: string | null;
  finish_type: string | null;
  finish_description: string | null;
  match_rating: number | null;
  crowd_heat: number;
  duration_minutes: number | null;
  is_completed: boolean;
}

export default function ShowViewerPage() {
  const { showId } = useParams<{ showId: string }>();
  const navigate = useNavigate();
  const [showData, setShowData] = useState<any>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [matchResults, setMatchResults] = useState<Record<string, MatchResult>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!showId) return;
    loadShowData();
  }, [showId]);

  const loadShowData = async () => {
    try {
      setLoading(true);
      const card = await api.getShowCard(showId!);
      setShowData(card.show);
      setSegments(card.segments);

      // Load match results for completed matches
      const results: Record<string, MatchResult> = {};
      for (const seg of card.segments) {
        if (seg.match_id) {
          try {
            results[seg.match_id] = await api.getMatch(seg.match_id);
          } catch { /* match may not exist yet */ }
        }
      }
      setMatchResults(results);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const ratingStars = (rating: number | null) => {
    if (!rating) return '';
    const full = Math.floor(rating);
    const half = rating - full >= 0.25;
    return '*'.repeat(full) + (half ? '1/2' : '') + ` (${rating.toFixed(1)})`;
  };

  const crowdColor = (reaction: string | null) => {
    if (!reaction) return 'text-gray-400';
    if (reaction === 'pop') return 'text-green-400';
    if (reaction === 'heat') return 'text-red-400';
    return 'text-yellow-400';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f0f14] flex items-center justify-center text-gray-400">
        Loading show...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f0f14]">
      <header className="bg-[#1a1a24] border-b border-gray-800 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-amber-400">{showData?.name || 'Show'}</h1>
            <p className="text-sm text-gray-400">
              {showData?.game_date} | {showData?.venue} | {showData?.show_type}
              {showData?.is_completed && (
                <span className="ml-2 text-amber-300">
                  Rating: {showData.overall_rating} | Attendance: {showData.attendance?.toLocaleString()}
                </span>
              )}
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

      {error && (
        <div className="max-w-4xl mx-auto px-6 mt-4">
          <div className="bg-red-900/30 border border-red-800 rounded p-3 text-red-400 text-sm">
            {error}
          </div>
        </div>
      )}

      <div className="max-w-4xl mx-auto px-6 mt-6 space-y-4">
        {segments.length === 0 && (
          <div className="text-center text-gray-500 py-12">
            No segments on this show yet.
          </div>
        )}

        {segments.map((seg, idx) => {
          const match = seg.match_id ? matchResults[seg.match_id] : null;

          return (
            <div
              key={seg.id}
              className="bg-[#1a1a24] rounded-lg border border-gray-800 overflow-hidden"
            >
              {/* Segment header */}
              <div className="flex items-center justify-between px-4 py-3 bg-[#0f0f14]/50 border-b border-gray-800">
                <div className="flex items-center gap-3">
                  <span className="text-gray-600 text-xs font-mono">#{idx + 1}</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    seg.segment_type === 'match' ? 'bg-amber-900/50 text-amber-300' :
                    seg.segment_type === 'promo' ? 'bg-purple-900/50 text-purple-300' :
                    'bg-gray-800 text-gray-300'
                  }`}>
                    {seg.segment_type.toUpperCase()}
                  </span>
                  {match?.is_title_match && (
                    <span className="px-2 py-0.5 rounded text-xs bg-yellow-900/50 text-yellow-300">
                      TITLE MATCH
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-sm">
                  {seg.rating && (
                    <span className="text-amber-400 font-mono">{ratingStars(seg.rating)}</span>
                  )}
                  {seg.actual_duration_minutes && (
                    <span className="text-gray-500">{seg.actual_duration_minutes}min</span>
                  )}
                  {seg.crowd_reaction && (
                    <span className={crowdColor(seg.crowd_reaction)}>
                      {seg.crowd_reaction}
                    </span>
                  )}
                </div>
              </div>

              {/* Segment body */}
              <div className="px-4 py-4">
                {seg.segment_type === 'match' && match ? (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-gray-400 text-sm">{match.match_type} match</span>
                      {match.stipulation && (
                        <span className="text-sm text-purple-400">{match.stipulation}</span>
                      )}
                    </div>

                    {match.is_completed && match.finish_description ? (
                      <div className="mt-2">
                        <p className="text-white text-lg leading-relaxed">
                          {match.finish_description}
                        </p>
                        <div className="flex items-center gap-4 mt-3 text-sm text-gray-400">
                          <span>Finish: {match.finish_type}</span>
                          <span>Duration: {match.duration_minutes}min</span>
                          <span>Crowd Heat: {match.crowd_heat}</span>
                          {match.match_rating && (
                            <span className="text-amber-400">
                              {ratingStars(match.match_rating)}
                            </span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <p className="text-yellow-400">Awaiting simulation...</p>
                    )}
                  </div>
                ) : seg.segment_type === 'promo' ? (
                  <p className="text-gray-300">{seg.description || 'Promo segment'}</p>
                ) : (
                  <p className="text-gray-300">{seg.description || seg.segment_type}</p>
                )}
              </div>
            </div>
          );
        })}

        {/* Show summary */}
        {showData?.is_completed && segments.length > 0 && (
          <div className="bg-[#1a1a24] rounded-lg border border-amber-800/50 p-6 text-center">
            <h3 className="text-amber-400 text-lg font-bold mb-2">Show Complete</h3>
            <div className="flex justify-center gap-8 text-sm">
              <div>
                <span className="text-gray-400">Overall Rating</span>
                <div className="text-2xl text-amber-400 font-bold">{showData.overall_rating}</div>
              </div>
              <div>
                <span className="text-gray-400">Attendance</span>
                <div className="text-2xl text-white font-bold">{showData.attendance?.toLocaleString()}</div>
              </div>
              {showData.gate_revenue && (
                <div>
                  <span className="text-gray-400">Gate Revenue</span>
                  <div className="text-2xl text-green-400 font-bold">
                    ${showData.gate_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </div>
                </div>
              )}
              {showData.tv_rating && (
                <div>
                  <span className="text-gray-400">TV Rating</span>
                  <div className="text-2xl text-blue-400 font-bold">{showData.tv_rating}</div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
