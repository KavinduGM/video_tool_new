/**
 * Tiny hash-based router. No history API needed — the app runs locally,
 * and #routes survive Ctrl+R cleanly. The app-root component listens for
 * hash changes and re-renders.
 */

const ROUTES = [
  { path: '#/',         name: 'dashboard' },
  { path: '#/new',      name: 'new-job' },
  { path: '#/queue',    name: 'queue' },
  { path: '#/library',  name: 'library' },
  { path: '#/styles',   name: 'styles' },
  { path: '#/settings', name: 'settings' },
];

function currentHash() {
  return window.location.hash || '#/';
}

export function currentRoute() {
  const h = currentHash();
  // Allow query params after the path (#/job/abc?tab=log).
  const base = h.split('?')[0];
  return ROUTES.find((r) => r.path === base) || ROUTES[0];
}

export function navigate(name) {
  const r = ROUTES.find((x) => x.name === name);
  if (r) window.location.hash = r.path;
}

export function onRouteChange(cb) {
  window.addEventListener('hashchange', cb);
  // Fire once on mount so the listener sees the initial route.
  setTimeout(cb, 0);
}

export const NAV_ITEMS = [
  { name: 'dashboard', label: 'Dashboard', icon: 'home' },
  { name: 'new-job',   label: 'New job',   icon: 'plus' },
  { name: 'queue',     label: 'Queue',     icon: 'list' },
  { name: 'library',   label: 'Library',   icon: 'film' },
  { name: 'styles',    label: 'Styles',    icon: 'palette' },
  { name: 'settings',  label: 'Settings',  icon: 'gear' },
];
