import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useGame } from '../context/GameContext';
import { api } from '../api/client';

interface Wrestler {
  id: string;
  name: string;
  popularity: number;
  alignment: string;
  condition: number;
  is_injured: boolean;
}

interface Segment {
  id: string;
  position: number;
  segment_type: string;
  match_id: string | null;
  description: string | null;
  is_completed: boolean;
}

export default function CardBuilderPage() {
  const { showId } = useParams<{ showId: string }>();
  const { worldId, federationId } = useGame();
  const navigate = useNavigate();

  const [show, setShow] = useState<any>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [roster, setRoster] = useState<Wrestler[]>([]);
  const [championships, setChampionships] = useState<any[]>([]);

  // Match booking form
  const [selectedWrestlers, setSelectedWrestlers] = useState<string[]>([]);
  const [matchType, setMatchType] = useState('singles');
  const [plannedWinner, setPlannedWinner] = useState('');
  const [plannedFinish, setPlannedFinish] = useState('pinfall');
  const [stipulation, setStipulation] = useState('');
  const [isTitleMatch, setIsTitleMatch] = useState(false);
  const [selectedChampionship, setSelectedChampionship] = useState('');

  // Promo booking form
  const [promoMode, setPromoMode] = useState(false);
  const [promoWrestler, setPromoWrestler] = useState('');
  const [promoTarget, setPromoTarget] = useState('');

  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadData();
  }, [showId, federationId]);

  const loadData = async () => {
    if (!showId || !federationId) return;
    try {
      setLoading(true);
      const [card, rost, champs] = await Promise.all([
        api.getShowCard(showId),
        api.getRoster(federationId),
        api.getChampionships(federationId),
      ]);
      setShow(card.show);
      setSegments(card.segments);
      setRoster(rost.filter((w: Wrestler) => !w.is_injured));
      setChampionships(champs);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleWrestler = (id: string) => {
    setSelectedWrestlers(prev => {
      if (prev.includes(id)) return prev.filter(w => w !== id);
      if (matchType === 'singles' && prev.length >= 2) return prev;
      if (matchType === 'triple_threat' && prev.length >= 3) return prev;
      if (matchType === 'fatal_four_way' && prev.length >= 4) return prev;
      return [...prev, id];
    });
  };

  const bookMatch = async () => {
    if (!showId || selectedWrestlers.length < 2) return;
    setBooking(true);
    setError('');
    try {
      await api.bookMatch(showId, {
        participant_ids: selectedWrestlers,
        match_type: matchType,
        planned_winner_id: plannedWinner || undefined,
        planned_finish: plannedFinish,
        stipulation: stipulation || undefined,
        is_title_match: isTitleMatch,
        championship_id: isTitleMatch ? selectedChampionship || undefined : undefined,
      });
      // Reset form and reload
      setSelectedWrestlers([]);
      setPlannedWinner('');
      setStipulation('');
      setIsTitleMatch(false);
      await loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBooking(false);
    }
  };

  // Wrestlers already booked on this show — extract from segment participant lists
  const bookedIds = new Set<string>();
  for (const seg of segments) {
    if (seg.participants) {
      for (const p of seg.participants) {
        if (p.wrestler_id) bookedIds.add(p.wrestler_id);
      }
    }
    // Also check match_participants if available in segment data
    if (seg.match_id && seg.match_participants) {
      for (const mp of seg.match_participants) {
        if (mp.wrestler_id) bookedIds.add(mp.wrestler_id);
      }
    }
  }

  const availableRoster = roster.filter(w => !bookedIds.has(w.id));
  const selectedNames = selectedWrestlers
    .map(id => roster.find(w => w.id === id)?.name || '???')
    .join(' vs ');

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f0f14] flex items-center justify-center text-gray-400">
        Loading...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f0f14]">
      <header className="bg-[#1a1a24] border-b border-gray-800 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-amber-400">
              Card Builder: {show?.name || 'Show'}
            </h1>
            <p className="text-sm text-gray-400">
              {show?.game_date} | {show?.venue} | {segments.length} segments booked
            </p>
          </div>
          <div className="flex gap-3">
            {show && (
              <button
                onClick={() => navigate(`/show/${showId}`)}
                className="px-4 py-2 bg-[#1a1a24] border border-gray-700 hover:border-gray-500 text-gray-300 rounded text-sm"
              >
                View Show
              </button>
            )}
            <button
              onClick={() => navigate(-1)}
              className="text-gray-500 hover:text-gray-300 text-sm"
            >
              Back
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="max-w-6xl mx-auto px-6 mt-4">
          <div className="bg-red-900/30 border border-red-800 rounded p-3 text-red-400 text-sm">
            {error}
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto px-6 mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Current Card */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-3">Current Card</h2>
          <div className="space-y-2">
            {segments.length === 0 ? (
              <div className="bg-[#1a1a24] rounded border border-gray-800 p-6 text-center text-gray-500">
                No matches booked yet. Use the form to add matches.
              </div>
            ) : (
              segments.map((seg, idx) => (
                <div
                  key={seg.id}
                  className="bg-[#1a1a24] rounded border border-gray-800 px-4 py-3 flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-gray-600 text-xs font-mono w-6">#{idx + 1}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      seg.segment_type === 'match' ? 'bg-amber-900/50 text-amber-300' :
                      'bg-purple-900/50 text-purple-300'
                    }`}>
                      {seg.segment_type}
                    </span>
                    <span className="text-gray-300 text-sm">
                      {seg.description || (seg.match_id ? 'Match' : seg.segment_type)}
                    </span>
                  </div>
                  {seg.is_completed && (
                    <span className="text-green-400 text-xs">Done</span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Match Booking Form */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-3">Book a Match</h2>
          <div className="bg-[#1a1a24] rounded-lg border border-gray-800 p-4 space-y-4">
            {/* Match Type */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Match Type</label>
              <select
                value={matchType}
                onChange={e => {
                  setMatchType(e.target.value);
                  setSelectedWrestlers([]);
                }}
                className="w-full bg-[#0f0f14] border border-gray-700 rounded p-2 text-white text-sm"
              >
                <option value="singles">Singles</option>
                <option value="tag_team">Tag Team</option>
                <option value="triple_threat">Triple Threat</option>
                <option value="fatal_four_way">Fatal Four Way</option>
              </select>
            </div>

            {/* Wrestler Selection */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Participants ({selectedWrestlers.length} selected)
                {selectedNames && <span className="text-amber-400 ml-2">{selectedNames}</span>}
              </label>
              <div className="max-h-48 overflow-y-auto bg-[#0f0f14] border border-gray-700 rounded">
                {availableRoster.map(w => (
                  <button
                    key={w.id}
                    onClick={() => toggleWrestler(w.id)}
                    className={`w-full text-left px-3 py-2 text-sm border-b border-gray-800 transition-colors ${
                      selectedWrestlers.includes(w.id)
                        ? 'bg-amber-900/30 text-amber-300'
                        : 'text-gray-300 hover:bg-[#1a1a24]'
                    }`}
                  >
                    <span className="font-medium">{w.name}</span>
                    <span className="text-gray-500 ml-2">Pop: {w.popularity}</span>
                    <span className={`ml-2 text-xs px-1 rounded ${
                      w.alignment === 'face' ? 'bg-blue-900/50 text-blue-300' :
                      w.alignment === 'heel' ? 'bg-red-900/50 text-red-300' :
                      'bg-gray-800 text-gray-300'
                    }`}>{w.alignment}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Planned Winner */}
            {selectedWrestlers.length >= 2 && (
              <div>
                <label className="block text-sm text-gray-400 mb-1">Planned Winner</label>
                <select
                  value={plannedWinner}
                  onChange={e => setPlannedWinner(e.target.value)}
                  className="w-full bg-[#0f0f14] border border-gray-700 rounded p-2 text-white text-sm"
                >
                  <option value="">Let it play out</option>
                  {selectedWrestlers.map(id => {
                    const w = roster.find(r => r.id === id);
                    return <option key={id} value={id}>{w?.name || id}</option>;
                  })}
                </select>
              </div>
            )}

            {/* Finish Type */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Planned Finish</label>
              <select
                value={plannedFinish}
                onChange={e => setPlannedFinish(e.target.value)}
                className="w-full bg-[#0f0f14] border border-gray-700 rounded p-2 text-white text-sm"
              >
                <option value="pinfall">Pinfall</option>
                <option value="submission">Submission</option>
                <option value="count_out">Count Out</option>
                <option value="disqualification">Disqualification</option>
              </select>
            </div>

            {/* Stipulation */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Stipulation (optional)</label>
              <input
                type="text"
                value={stipulation}
                onChange={e => setStipulation(e.target.value)}
                placeholder="No DQ, Steel Cage, etc."
                className="w-full bg-[#0f0f14] border border-gray-700 rounded p-2 text-white text-sm"
              />
            </div>

            {/* Title Match */}
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isTitleMatch}
                  onChange={e => setIsTitleMatch(e.target.checked)}
                  className="rounded bg-[#0f0f14] border-gray-700"
                />
                Title Match
              </label>
              {isTitleMatch && championships.length > 0 && (
                <select
                  value={selectedChampionship}
                  onChange={e => setSelectedChampionship(e.target.value)}
                  className="bg-[#0f0f14] border border-gray-700 rounded p-1 text-white text-sm flex-1"
                >
                  <option value="">Select championship</option>
                  {championships.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              )}
            </div>

            {/* Book Button */}
            <button
              onClick={bookMatch}
              disabled={selectedWrestlers.length < 2 || booking}
              className="w-full py-3 bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded font-medium text-sm transition-colors"
            >
              {booking ? 'Booking...' : `Book Match (${selectedWrestlers.length} wrestlers)`}
            </button>

            {/* Promo Segment Section */}
            <div className="mt-6 pt-4 border-t border-gray-800">
              <button
                onClick={() => setPromoMode(!promoMode)}
                className="text-sm text-purple-400 hover:text-purple-300"
              >
                {promoMode ? 'Cancel Promo' : '+ Add Promo Segment'}
              </button>
              {promoMode && (
                <div className="mt-3 space-y-3">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Speaker</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={promoWrestler}
                      onChange={e => setPromoWrestler(e.target.value)}
                    >
                      <option value="">Select wrestler...</option>
                      {roster.map(w => (
                        <option key={w.id} value={w.id}>{w.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Target (optional)</label>
                    <select
                      className="w-full p-2 bg-[#0f0f14] border border-gray-700 rounded text-white text-sm"
                      value={promoTarget}
                      onChange={e => setPromoTarget(e.target.value)}
                    >
                      <option value="">No target</option>
                      {roster.filter(w => w.id !== promoWrestler).map(w => (
                        <option key={w.id} value={w.id}>{w.name}</option>
                      ))}
                    </select>
                  </div>
                  <button
                    onClick={async () => {
                      if (!showId || !promoWrestler) return;
                      try {
                        setBooking(true);
                        await api.bookPromo(showId, promoWrestler, promoTarget || undefined);
                        setPromoWrestler('');
                        setPromoTarget('');
                        setPromoMode(false);
                        await loadData();
                      } catch (err: any) {
                        setError(err.message);
                      } finally {
                        setBooking(false);
                      }
                    }}
                    disabled={!promoWrestler || booking}
                    className="w-full py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded text-sm"
                  >
                    Book Promo
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
