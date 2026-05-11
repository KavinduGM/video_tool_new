/**
 * App-wide observable state. Pages subscribe with onChange(); when state
 * is mutated via set(), every subscriber re-renders.
 *
 * Why not a full Redux/Zustand thing? This app has maybe 10 pieces of
 * shared state. A 30-line pub/sub is simpler and explicit.
 */

import { api } from './api.js';

const state = {
  config: null,            // AppConfig
  styles: [],              // Style[]
  jobs: [],                // Job[]
  hfStatus: null,          // HyperFramesStatus
  notifications: [],       // [{ id, type, message }]
};

const subscribers = new Set();

export function getState() {
  return state;
}

export function subscribe(cb) {
  subscribers.add(cb);
  return () => subscribers.delete(cb);
}

function emit() {
  for (const cb of subscribers) cb();
}

export function set(partial) {
  Object.assign(state, partial);
  emit();
}

// ─── Notifications (toast-style) ────────────────────────────────────────

export function notify(type, message) {
  const id = Math.random().toString(36).slice(2, 8);
  state.notifications = [...state.notifications, { id, type, message }];
  emit();
  setTimeout(() => {
    state.notifications = state.notifications.filter((n) => n.id !== id);
    emit();
  }, type === 'error' ? 8000 : 4000);
}

// ─── Initial bootstrap ──────────────────────────────────────────────────

export async function bootstrap() {
  try {
    const [config, styles, hfStatus, jobs] = await Promise.all([
      api.getConfig(),
      api.listStyles(),
      api.hfStatus().catch(() => null),
      api.listJobs().catch(() => []),
    ]);
    set({ config, styles, hfStatus, jobs });
  } catch (e) {
    notify('error', `Could not contact backend: ${e.detail || e.message}`);
  }
}

// ─── Polling for queue updates while New Job / Queue page open ──────────

let pollHandle = null;

export function startJobPolling(intervalMs = 2000) {
  stopJobPolling();
  const tick = async () => {
    try {
      const jobs = await api.listJobs();
      set({ jobs });
    } catch {
      // Silent — UI keeps last known state if a poll fails.
    }
  };
  tick();
  pollHandle = setInterval(tick, intervalMs);
}

export function stopJobPolling() {
  if (pollHandle !== null) {
    clearInterval(pollHandle);
    pollHandle = null;
  }
}

// ─── Refresh helpers (call after mutating actions) ──────────────────────

export async function refreshConfig() {
  try { set({ config: await api.getConfig() }); } catch {}
}

export async function refreshStyles() {
  try { set({ styles: await api.listStyles() }); } catch {}
}

export async function refreshHfStatus() {
  try { set({ hfStatus: await api.hfStatus() }); } catch {}
}

export async function refreshJobs() {
  try { set({ jobs: await api.listJobs() }); } catch {}
}
