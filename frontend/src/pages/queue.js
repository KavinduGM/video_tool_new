import { LitElement, html } from 'lit';
import { api } from '../api.js';
import { getState, subscribe, notify, startJobPolling, stopJobPolling, refreshJobs } from '../state.js';
import '../components.js';

const STATUS_LABEL = {
  queued: 'Queued',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
  paused: 'Paused',
};

const STATUS_VARIANT = {
  queued: 'default',
  running: 'info',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
  paused: 'warning',
};

export class PageQueue extends LitElement {
  createRenderRoot() { return this; }
  connectedCallback() {
    super.connectedCallback();
    this._unsub = subscribe(() => this.requestUpdate());
    startJobPolling(2000);  // Live progress.
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsub?.();
    stopJobPolling();
  }

  async _cancel(id) {
    try {
      await api.cancelJob(id);
      notify('info', 'Cancel requested.');
      refreshJobs();
    } catch (e) { notify('error', e.detail || e.message); }
  }

  async _retry(id) {
    try {
      await api.retryJob(id);
      notify('success', 'Re-queued.');
      refreshJobs();
    } catch (e) { notify('error', e.detail || e.message); }
  }

  async _delete(id) {
    if (!confirm('Remove this job from the list? (The video file is not deleted.)')) return;
    try {
      await api.deleteJob(id);
      notify('success', 'Removed.');
      refreshJobs();
    } catch (e) { notify('error', e.detail || e.message); }
  }

  render() {
    const jobs = getState().jobs || [];
    const running = jobs.filter((j) => j.status === 'running');
    const queued  = jobs.filter((j) => j.status === 'queued');
    const done    = jobs.filter((j) => ['completed', 'failed', 'cancelled'].includes(j.status));

    return html`
      <header class="mb-8">
        <h2 class="text-2xl font-semibold">Queue</h2>
        <p class="text-zinc-400 mt-1">Live job progress, pending queue, and history.</p>
      </header>

      ${running.length > 0 ? html`
        <section class="mb-8">
          <h3 class="text-sm font-semibold text-zinc-300 mb-3 uppercase tracking-wide">Running</h3>
          ${running.map((j) => this._renderRunningJob(j))}
        </section>
      ` : ''}

      <section class="mb-8">
        <h3 class="text-sm font-semibold text-zinc-300 mb-3 uppercase tracking-wide">
          Pending (${queued.length})
        </h3>
        ${queued.length === 0 ? html`
          <ui-card><p class="text-sm text-zinc-500">No jobs queued.</p></ui-card>
        ` : html`
          <div class="space-y-3">${queued.map((j) => this._renderQueuedJob(j))}</div>
        `}
      </section>

      <section>
        <h3 class="text-sm font-semibold text-zinc-300 mb-3 uppercase tracking-wide">
          History (${done.length})
        </h3>
        ${done.length === 0 ? html`
          <ui-card><p class="text-sm text-zinc-500">No completed or failed jobs yet.</p></ui-card>
        ` : html`
          <div class="space-y-3">${done.map((j) => this._renderHistoryJob(j))}</div>
        `}
      </section>
    `;
  }

  _renderRunningJob(j) {
    const p = j.progress || {};
    const total = p.total_scenes || 0;
    const cur = p.current_scene || 0;
    const pct = total > 0 ? Math.round((cur / total) * 100) : 0;
    const eta = p.eta_seconds ? this._fmtSeconds(p.eta_seconds) : '—';
    const logTail = (j.log_lines || []).slice(-12);
    return html`
      <ui-card class="mb-4">
        <div class="flex items-start justify-between mb-4">
          <div>
            <h4 class="font-semibold">${j.request.title}</h4>
            <p class="text-xs text-zinc-500 mt-0.5">${j.request.style_key} · ${j.request.canvas_key}</p>
          </div>
          <ui-button variant="danger" size="sm" icon="x" @click=${() => this._cancel(j.id)}>Stop</ui-button>
        </div>
        <div class="mb-3">
          <div class="flex justify-between text-xs text-zinc-400 mb-1">
            <span>${p.current_step || 'Starting…'}</span>
            <span>${cur}/${total} scenes · ETA ${eta}</span>
          </div>
          <div class="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div class="h-full bg-indigo-500 transition-all" style="width: ${pct}%"></div>
          </div>
        </div>
        <details>
          <summary class="cursor-pointer text-xs text-zinc-500 hover:text-zinc-300">Log tail</summary>
          <pre class="mt-2 bg-zinc-950 border border-zinc-800 rounded p-3 text-xs font-mono text-zinc-400 overflow-x-auto">${logTail.join('\n') || '(no log lines yet)'}</pre>
        </details>
      </ui-card>
    `;
  }

  _renderQueuedJob(j) {
    return html`
      <div class="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex items-center justify-between">
        <div class="min-w-0">
          <p class="font-medium truncate">${j.request.title}</p>
          <p class="text-xs text-zinc-500 mt-0.5">
            ${j.request.style_key} · ${j.request.canvas_key} · added ${this._fmtDate(j.created_at)}
          </p>
        </div>
        <ui-button variant="ghost" size="sm" icon="x" @click=${() => this._cancel(j.id)}>Cancel</ui-button>
      </div>
    `;
  }

  _renderHistoryJob(j) {
    const ok = j.status === 'completed';
    return html`
      <div class="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <div class="flex items-center justify-between">
          <div class="min-w-0 flex-1 mr-4">
            <div class="flex items-center gap-2">
              <p class="font-medium truncate">${j.request.title}</p>
              <ui-badge variant=${STATUS_VARIANT[j.status]}>${STATUS_LABEL[j.status]}</ui-badge>
            </div>
            ${ok && j.result_path ? html`
              <p class="text-xs text-zinc-500 mt-1 font-mono truncate">${j.result_path}</p>
            ` : j.error_message ? html`
              <p class="text-xs text-rose-400 mt-1 truncate" title=${j.error_message}>${j.error_message}</p>
            ` : ''}
          </div>
          <div class="flex items-center gap-2">
            ${!ok ? html`
              <ui-button variant="ghost" size="sm" icon="refresh" @click=${() => this._retry(j.id)}>Retry</ui-button>
            ` : ''}
            <ui-button variant="ghost" size="sm" icon="trash" @click=${() => this._delete(j.id)}></ui-button>
          </div>
        </div>
        ${j.error_message ? html`
          <details class="mt-3">
            <summary class="cursor-pointer text-xs text-zinc-500 hover:text-zinc-300">Show details</summary>
            <pre class="mt-2 bg-zinc-950 border border-zinc-800 rounded p-3 text-xs font-mono text-zinc-400 overflow-x-auto whitespace-pre-wrap">${j.error_traceback || j.error_message}</pre>
          </details>
        ` : ''}
      </div>
    `;
  }

  _fmtSeconds(s) {
    if (!s) return '—';
    const min = Math.floor(s / 60);
    const sec = Math.round(s % 60);
    return min > 0 ? `${min}m ${sec}s` : `${sec}s`;
  }

  _fmtDate(iso) {
    if (!iso) return '';
    try { return new Date(iso).toLocaleTimeString(); } catch { return iso; }
  }
}
customElements.define('app-page-queue', PageQueue);
