/**
 * Backend API client. All page components route HTTP through here so the
 * URL prefix + error handling stays in one place.
 *
 * The backend is same-origin in production (FastAPI serves the frontend),
 * so a relative URL works. In dev mode where you might run vite separately,
 * you can override via VIDEO_GEN_API_BASE on window.
 */

const API_BASE = window.VIDEO_GEN_API_BASE || '';

class ApiError extends Error {
  constructor(status, detail) {
    super(`HTTP ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(`${API_BASE}${path}`, opts);
  if (!r.ok) {
    let detail;
    try {
      const j = await r.json();
      detail = j.detail || JSON.stringify(j);
    } catch {
      detail = await r.text();
    }
    throw new ApiError(r.status, detail);
  }
  if (r.status === 204) return null;
  const ct = r.headers.get('content-type') || '';
  return ct.includes('application/json') ? r.json() : r.text();
}

export const api = {
  // Generic getters
  health: () => request('GET', '/api/health'),

  // Config
  getConfig: () => request('GET', '/api/config'),
  putConfig: (cfg) => request('PUT', '/api/config', cfg),
  addVoiceProfile: (profile) => request('POST', '/api/config/voice-profiles', profile),
  deleteVoiceProfile: (id) => request('DELETE', `/api/config/voice-profiles/${id}`),

  // TTS
  ttsHealth: (profileId) => request('GET', `/api/tts/health?profile_id=${encodeURIComponent(profileId)}`),
  ttsVoices: (profileId) => request('GET', `/api/tts/voices?profile_id=${encodeURIComponent(profileId)}`),

  // Styles
  listStyles: () => request('GET', '/api/styles'),
  addStyle: (style) => request('POST', '/api/styles', style),
  deleteStyle: (key) => request('DELETE', `/api/styles/${encodeURIComponent(key)}`),

  // HyperFrames
  hfStatus: () => request('GET', '/api/hyperframes/status'),
  hfUpdate: () => request('POST', '/api/hyperframes/update'),
  hfSmokeTest: () => request('POST', '/api/hyperframes/smoke-test'),

  // Jobs
  enqueueJob: (req) => request('POST', '/api/jobs', req),
  listJobs: () => request('GET', '/api/jobs'),
  getJob: (id) => request('GET', `/api/jobs/${id}`),
  cancelJob: (id) => request('POST', `/api/jobs/${id}/cancel`),
  retryJob: (id) => request('POST', `/api/jobs/${id}/retry`),
  deleteJob: (id) => request('DELETE', `/api/jobs/${id}`),

  // Files / library
  listOutputFolder: (folder) => request('GET', `/api/files/output?folder=${encodeURIComponent(folder)}`),
  videoStreamUrl: (path) => `${API_BASE}/api/files/stream?path=${encodeURIComponent(path)}`,
};

export { ApiError };
