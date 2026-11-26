/**
 * API client for LLMFed game backend.
 */

export interface User {
  id: string;
  username: string;
  email: string;
  display_name?: string;
}

export interface World {
  id: string;
  name: string;
  description?: string | null;
  is_multiplayer: boolean;
  max_players: number;
  current_game_date: string;
  current_tick: number;
  is_active: boolean;
}

export interface WorldNewsArticle {
  id: string;
  headline: string;
  body: string;
  category: string;
  game_date: string;
  is_kayfabe: boolean;
  source: string;
}

export interface Player {
  id: string;
  player_type: 'promoter' | 'wrestler';
  federation_id?: string;
  wrestler_id?: string;
}

export interface PlayerCreateData {
  world_id: string;
  player_type: 'promoter' | 'wrestler';
  federation_name?: string;
  federation_description?: string;
  wrestler_name?: string;
  wrestler_gimmick?: string;
  wrestler_alignment?: string;
  wrestler_style?: string;
}

export interface ShowSummary {
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

export type ShowStatus = 'all' | 'completed' | 'upcoming';

interface WorldShowsPage {
  shows: ShowSummary[];
  counts: Record<ShowStatus, number>;
}

export interface SchedulerStatus {
  running: boolean;
  interval_seconds: number;
  ticks_completed: number;
  last_tick_at: string | null;
  paused_worlds: string[];
  recent_errors: string[];
}

const API_BASE = '/game';

function getToken(): string | null {
  return localStorage.getItem('token');
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(path, { ...options, headers });

  if (!res.ok) {
    const body: { detail?: unknown; message?: unknown } | null = await res.json().catch(() => null);
    const message = [body?.detail, body?.message, res.statusText]
      .find((value): value is string => typeof value === 'string' && value.length > 0);
    throw new Error(message || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

function request<T>(path: string, options?: RequestInit): Promise<T> {
  return requestJson<T>(`${API_BASE}${path}`, options);
}

// Auth
export const api = {
  register: (data: { email: string; username: string; password: string; display_name?: string }) =>
    request<{ access_token: string; user: User }>('/auth/register', {
      method: 'POST', body: JSON.stringify(data),
    }),

  login: (data: { username: string; password: string }) =>
    request<{ access_token: string; user: User }>('/auth/login', {
      method: 'POST', body: JSON.stringify(data),
    }),

  getMe: () => request<User>('/auth/me'),

  // Worlds
  createWorld: (data: { name: string; description?: string; is_multiplayer?: boolean }) =>
    request<World>('/worlds', { method: 'POST', body: JSON.stringify(data) }),

  getWorld: (worldId: string) =>
    request<World>(`/worlds/${worldId}`),

  getMyPlayer: (worldId: string) =>
    request<Player>(`/worlds/${worldId}/my-player`),

  // Players
  createPlayer: (data: PlayerCreateData) =>
    request<Player>('/players', { method: 'POST', body: JSON.stringify(data) }),

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

  getWorldShows: (worldId: string, limit: number) =>
    requestJson<ShowSummary[]>(`/worlds/${worldId}/shows?limit=${limit}`),

  getWorldShowsPage: (worldId: string, status: ShowStatus, limit: number, offset: number, signal?: AbortSignal) => {
    const params = new URLSearchParams({ status, limit: String(limit), offset: String(offset), include_counts: 'true' });
    return requestJson<WorldShowsPage>(`/worlds/${worldId}/shows?${params}`, { signal });
  },

  // Auto-ticker
  getSchedulerStatus: (signal?: AbortSignal) =>
    requestJson<SchedulerStatus>('/scheduler/status', { signal }),

  startScheduler: (interval: number) =>
    requestJson<SchedulerStatus>('/scheduler/start', {
      method: 'POST', body: JSON.stringify({ interval_seconds: interval }),
    }),

  stopScheduler: () =>
    requestJson<SchedulerStatus>('/scheduler/stop', { method: 'POST' }),

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
    request<WorldNewsArticle[]>(`/worlds/${worldId}/news?limit=${limit}`),

  // Storylines
  listStorylines: (worldId: string, status?: string, federationId?: string) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (federationId) params.set('federation_id', federationId);
    const query = params.toString();
    return request<any[]>(`/worlds/${worldId}/storylines${query ? `?${query}` : ''}`);
  },

  createStoryline: (worldId: string, data: {
    wrestler_ids: string[]; storyline_type?: string;
    name?: string; description?: string; federation_id?: string;
  }) =>
    request<any>(`/worlds/${worldId}/storylines`, {
      method: 'POST', body: JSON.stringify(data),
    }),

  advanceStoryline: (storylineId: string, data: { status?: string; heat_boost?: number }) =>
    request<any>(`/storylines/${storylineId}`, {
      method: 'PATCH', body: JSON.stringify(data),
    }),

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

  bookPromo: (showId: string, wrestlerId: string, targetId?: string, promoType?: string) =>
    request<any>(`/shows/${showId}/promos?wrestler_id=${wrestlerId}${targetId ? `&target_wrestler_id=${targetId}` : ''}${promoType ? `&promo_type=${promoType}` : ''}`, {
      method: 'POST',
    }),

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

  // Managers & Valets
  listManagers: (worldId: string, federationId?: string) =>
    request<any[]>(`/worlds/${worldId}/managers${federationId ? `?federation_id=${federationId}` : ''}`),

  createManager: (worldId: string, data: {
    name: string; alignment?: string; archetype?: string;
    real_name?: string; gender?: string; catchphrase?: string;
    personality_traits?: string[];
  }, federationId?: string) =>
    request<any>(`/worlds/${worldId}/managers${federationId ? `?federation_id=${federationId}` : ''}`, {
      method: 'POST', body: JSON.stringify(data),
    }),

  listManagerBonds: (worldId: string) =>
    request<any[]>(`/worlds/${worldId}/manager-bonds`),

  assignManager: (worldId: string, data: {
    manager_id: string; client_wrestler_id: string;
    role?: string; specialization?: string;
  }) =>
    request<any>(`/worlds/${worldId}/manager-bonds`, {
      method: 'POST', body: JSON.stringify(data),
    }),

  removeManagerBond: (bondId: string) =>
    request<void>(`/manager-bonds/${bondId}`, { method: 'DELETE' }),

  getWrestlerManager: (wrestlerId: string) =>
    request<any>(`/wrestlers/${wrestlerId}/manager`),

  generateManagerPromo: (managerId: string, clientId: string, targetId?: string) =>
    request<any>(`/managers/${managerId}/promo?client_wrestler_id=${clientId}${targetId ? `&target_wrestler_id=${targetId}` : ''}`),

  // Stables / Factions
  listStables: (worldId: string, federationId?: string) =>
    request<any[]>(`/worlds/${worldId}/stables${federationId ? `?federation_id=${federationId}` : ''}`),

  createStable: (worldId: string, data: {
    name: string; leader_id: string; founding_member_ids: string[];
    alignment?: string; short_name?: string; catchphrase?: string;
    group_finisher_name?: string; manager_id?: string;
  }) =>
    request<any>(`/worlds/${worldId}/stables`, {
      method: 'POST', body: JSON.stringify(data),
    }),

  getStable: (stableId: string) =>
    request<any>(`/stables/${stableId}`),

  addStableMember: (stableId: string, data: { wrestler_id: string; role?: string }) =>
    request<any>(`/stables/${stableId}/members`, {
      method: 'POST', body: JSON.stringify(data),
    }),

  removeStableMember: (stableId: string, wrestlerId: string) =>
    request<void>(`/stables/${stableId}/members/${wrestlerId}`, { method: 'DELETE' }),

  getWrestlerStable: (wrestlerId: string) =>
    request<any>(`/wrestlers/${wrestlerId}/stable`),
};
