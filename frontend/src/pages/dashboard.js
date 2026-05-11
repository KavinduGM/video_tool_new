import { LitElement, html } from 'lit';
import { getState, subscribe } from '../state.js';
import { navigate } from '../router.js';
import '../components.js';

export class PageDashboard extends LitElement {
  createRenderRoot() { return this; }
  connectedCallback() {
    super.connectedCallback();
    this._unsub = subscribe(() => this.requestUpdate());
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsub?.();
  }

  render() {
    const s = getState();
    const cfg = s.config;
    const jobs = s.jobs || [];
    const running = jobs.filter((j) => j.status === 'running');
    const queued = jobs.filter((j) => j.status === 'queued');
    const completed = jobs.filter((j) => j.status === 'completed');
    const failed = jobs.filter((j) => j.status === 'failed');
    const recent = completed.slice(0, 5);

    const profiles = cfg?.voice_profiles || [];
    const needsSetup = !cfg?.anthropic_api_key || profiles.length === 0;

    return html`
      <header class="mb-8">
        <h2 class="text-2xl font-semibold">Dashboard</h2>
        <p class="text-zinc-400 mt-1">Overview of your video generation pipeline.</p>
      </header>

      ${needsSetup ? html`
        <ui-card class="mb-6">
          <div class="flex items-start gap-3">
            <div class="text-amber-400 mt-0.5"><ui-icon name="alert" size="20"></ui-icon></div>
            <div class="flex-1">
              <h3 class="font-semibold mb-1">Quick setup</h3>
              <p class="text-sm text-zinc-400 mb-3">
                You're a couple of steps away from rendering your first video.
              </p>
              <ul class="text-sm space-y-1 text-zinc-300">
                ${!cfg?.anthropic_api_key ? html`
                  <li>• Add your Anthropic API key in <a href="#" @click=${(e) => { e.preventDefault(); navigate('settings'); }} class="text-indigo-400 hover:underline">Settings</a></li>
                ` : ''}
                ${profiles.length === 0 ? html`
                  <li>• Add a voice profile (TTS server) in <a href="#" @click=${(e) => { e.preventDefault(); navigate('settings'); }} class="text-indigo-400 hover:underline">Settings</a></li>
                ` : ''}
              </ul>
            </div>
          </div>
        </ui-card>
      ` : ''}

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        ${this._statCard('Running',   running.length,   'indigo')}
        ${this._statCard('Queued',    queued.length,    'amber')}
        ${this._statCard('Completed', completed.length, 'emerald')}
        ${this._statCard('Failed',    failed.length,    'rose')}
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ui-card title="Recent videos">
          ${recent.length === 0 ? html`
            <p class="text-sm text-zinc-500">No videos generated yet.</p>
          ` : html`
            <ul class="divide-y divide-zinc-800">
              ${recent.map((j) => html`
                <li class="py-3 flex items-center justify-between">
                  <div class="min-w-0">
                    <p class="text-sm font-medium truncate">${j.request.title}</p>
                    <p class="text-xs text-zinc-500 mt-0.5">${j.progress.total_scenes} scene(s) · ${this._fmtDate(j.completed_at)}</p>
                  </div>
                  <ui-badge variant="success">done</ui-badge>
                </li>
              `)}
            </ul>
            <div class="mt-4">
              <ui-button variant="ghost" size="sm" @click=${() => navigate('library')}>View library →</ui-button>
            </div>
          `}
        </ui-card>

        <ui-card title="Quick actions">
          <div class="space-y-2">
            <ui-button full variant="primary" icon="plus" @click=${() => navigate('new-job')}>
              New video
            </ui-button>
            <ui-button full variant="secondary" icon="list" @click=${() => navigate('queue')}>
              View queue
            </ui-button>
            <ui-button full variant="ghost" icon="gear" @click=${() => navigate('settings')}>
              Settings
            </ui-button>
          </div>
        </ui-card>
      </div>
    `;
  }

  _statCard(label, value, color) {
    const colorCls = {
      indigo: 'text-indigo-400',
      amber: 'text-amber-400',
      emerald: 'text-emerald-400',
      rose: 'text-rose-400',
    }[color];
    return html`
      <div class="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <p class="text-xs uppercase tracking-wide text-zinc-500 font-medium">${label}</p>
        <p class="text-3xl font-semibold mt-2 ${colorCls}">${value}</p>
      </div>
    `;
  }

  _fmtDate(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch { return iso; }
  }
}
customElements.define('app-page-dashboard', PageDashboard);
