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
  listStorylines: (worldId: string, status?: string) =>
    request<any[]>(`/worlds/${worldId}/storylines${status ? `?status=${status}` : ''}`),

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
