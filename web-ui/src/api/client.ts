/**
 * API client for LLMFed game backend.
 */

const API_BASE = '/game';

function getToken(): string | null {
  return localStorage.getItem('token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// Auth
export const api = {
  register: (data: { email: string; username: string; password: string; display_name?: string }) =>
    request<{ access_token: string; user: any }>('/auth/register', {
      method: 'POST', body: JSON.stringify(data),
    }),

  login: (data: { username: string; password: string }) =>
    request<{ access_token: string; user: any }>('/auth/login', {
      method: 'POST', body: JSON.stringify(data),
    }),

  getMe: () => request<any>('/auth/me'),

  // Worlds
  createWorld: (data: { name: string; description?: string; is_multiplayer?: boolean }) =>
    request<any>('/worlds', { method: 'POST', body: JSON.stringify(data) }),

  getWorld: (worldId: string) =>
    request<any>(`/worlds/${worldId}`),

  getMyPlayer: (worldId: string) =>
    request<any>(`/worlds/${worldId}/my-player`),

  // Players
  createPlayer: (data: any) =>
    request<any>('/players', { method: 'POST', body: JSON.stringify(data) }),

  // Federations
  listFederations: (worldId: string) =>
    request<any[]>(`/worlds/${worldId}/federations`),

  getFederation: (fedId: string) =>
    request<any>(`/federations/${fedId}`),

  getRoster: (fedId: string) =>
    request<any[]>(`/federations/${fedId}/roster`),

  getChampionships: (fedId: string) =>
    request<any[]>(`/federations/${fedId}/championships`),

  getShows: (fedId: string, limit = 20) =>
    request<any[]>(`/federations/${fedId}/shows?limit=${limit}`),

  // Wrestlers
  listWrestlers: (worldId: string, limit = 100) =>
    request<any[]>(`/worlds/${worldId}/wrestlers?limit=${limit}`),

  listFreeAgents: (worldId: string) =>
    request<any[]>(`/worlds/${worldId}/free-agents`),

  getWrestler: (wrestlerId: string) =>
    request<any>(`/wrestlers/${wrestlerId}`),

  // Actions
  submitAction: (worldId: string, actionType: string, actionData: any) =>
    request<any>(`/worlds/${worldId}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action_type: actionType, action_data: actionData }),
    }),

  listActions: (worldId: string, status?: string) =>
    request<any[]>(`/worlds/${worldId}/actions${status ? `?status=${status}` : ''}`),

  // World tick
  advanceWorld: (worldId: string, days = 1) =>
    request<any>(`/worlds/${worldId}/tick?days=${days}`, { method: 'POST' }),

  // Narrative
  getNarrative: (worldId: string, limit = 50) =>
    request<any[]>(`/worlds/${worldId}/narrative?limit=${limit}`),

  getNews: (worldId: string, limit = 20) =>
    request<any[]>(`/worlds/${worldId}/news?limit=${limit}`),

  // Storylines
  listStorylines: (worldId: string) =>
    request<any[]>(`/worlds/${worldId}/storylines`),

  // Shows - booking
  createShow: (fedId: string, data: {
    name: string; show_type?: string; venue?: string; capacity?: number; game_date: string;
  }) =>
    request<any>(`/federations/${fedId}/shows`, { method: 'POST', body: JSON.stringify(data) }),

  getShowCard: (showId: string) =>
    request<any>(`/shows/${showId}/card`),

  bookMatch: (showId: string, data: {
    participant_ids: string[]; match_type?: string; stipulation?: string;
    is_title_match?: boolean; championship_id?: string;
    planned_winner_id?: string; planned_finish?: string;
    segment_position?: number;
  }) =>
    request<any>(`/shows/${showId}/matches`, { method: 'POST', body: JSON.stringify(data) }),

  getMatch: (matchId: string) =>
    request<any>(`/matches/${matchId}`),

  getPlayByPlay: (matchId: string, highlightsOnly = false) =>
    request<any>(`/matches/${matchId}/play-by-play?highlights_only=${highlightsOnly}`),

  // Promos
  generatePromo: (worldId: string, data: {
    wrestler_id: string; target_wrestler_id?: string;
    promo_type?: string; player_direction?: string; player_content?: string;
  }) =>
    request<any>(`/worlds/${worldId}/promos`, { method: 'POST', body: JSON.stringify(data) }),
};
