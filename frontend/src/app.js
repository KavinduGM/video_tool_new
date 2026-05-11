/**
 * Root component: sidebar + main content area + toasts.
 *
 * Listens to hash-route changes and renders the right page component.
 */

import { LitElement, html } from 'lit';
import { currentRoute, onRouteChange, navigate, NAV_ITEMS } from './router.js';
import { subscribe, getState } from './state.js';
import './components.js';

export class AppRoot extends LitElement {
  createRenderRoot() { return this; }

  connectedCallback() {
    super.connectedCallback();
    this._unsub = subscribe(() => this.requestUpdate());
    onRouteChange(() => this.requestUpdate());
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsub?.();
  }

  _renderNavItem(item) {
    const route = currentRoute();
    const isActive = route.name === item.name;
    const cls = isActive
      ? 'bg-zinc-800/80 text-zinc-100 border-l-2 border-indigo-500'
      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border-l-2 border-transparent';
    return html`
      <a href="#"
         @click=${(e) => { e.preventDefault(); navigate(item.name); }}
         class="flex items-center gap-3 px-4 py-2.5 text-sm font-medium ${cls} transition-colors">
        <ui-icon name=${item.icon} size="16"></ui-icon>
        <span>${item.label}</span>
      </a>
    `;
  }

  _renderStatusFooter() {
    const s = getState();
    const hf = s.hfStatus;
    const running = (s.jobs || []).filter((j) => j.status === 'running').length;
    const queued = (s.jobs || []).filter((j) => j.status === 'queued').length;
    return html`
      <div class="px-4 py-3 border-t border-zinc-800 space-y-1.5 text-xs text-zinc-500">
        <div class="flex items-center justify-between">
          <span>HyperFrames</span>
          ${hf ? (hf.is_outdated
            ? html`<ui-badge variant="warning">${hf.installed_version} → ${hf.latest_version}</ui-badge>`
            : hf.installed_version
              ? html`<ui-badge variant="success">${hf.installed_version}</ui-badge>`
              : html`<ui-badge variant="error">missing</ui-badge>`
          ) : html`<span class="text-zinc-600">…</span>`}
        </div>
        <div class="flex items-center justify-between">
          <span>Queue</span>
          <span>${running} running · ${queued} queued</span>
        </div>
      </div>
    `;
  }

  _renderPage() {
    const route = currentRoute();
    switch (route.name) {
      case 'dashboard': return html`<app-page-dashboard></app-page-dashboard>`;
      case 'new-job':   return html`<app-page-new-job></app-page-new-job>`;
      case 'queue':     return html`<app-page-queue></app-page-queue>`;
      case 'library':   return html`<app-page-library></app-page-library>`;
      case 'styles':    return html`<app-page-styles></app-page-styles>`;
      case 'settings':  return html`<app-page-settings></app-page-settings>`;
      default:          return html`<app-page-dashboard></app-page-dashboard>`;
    }
  }

  render() {
    return html`
      <div class="flex min-h-screen">
        <!-- Sidebar -->
        <aside class="w-60 shrink-0 bg-zinc-950 border-r border-zinc-800 flex flex-col">
          <div class="px-5 py-5 border-b border-zinc-800">
            <h1 class="text-base font-semibold text-zinc-100">Video Generator</h1>
            <p class="text-xs text-zinc-500 mt-0.5">v2.0</p>
          </div>
          <nav class="flex-1 py-3">
            ${NAV_ITEMS.map((n) => this._renderNavItem(n))}
          </nav>
          ${this._renderStatusFooter()}
        </aside>

        <!-- Main content -->
        <main class="flex-1 overflow-y-auto">
          <div class="max-w-6xl mx-auto px-8 py-8">
            ${this._renderPage()}
          </div>
        </main>

        <ui-toasts></ui-toasts>
      </div>
    `;
  }
}
customElements.define('app-root', AppRoot);
