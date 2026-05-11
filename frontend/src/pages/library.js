import { LitElement, html } from 'lit';
import { api } from '../api.js';
import { getState, subscribe, notify } from '../state.js';
import '../components.js';

export class PageLibrary extends LitElement {
  static properties = {
    _folder: { state: true },
    _files: { state: true },
    _loading: { state: true },
    _playing: { state: true },
  };

  createRenderRoot() { return this; }

  constructor() {
    super();
    this._folder = '';
    this._files = [];
    this._loading = false;
    this._playing = null;
  }

  connectedCallback() {
    super.connectedCallback();
    // Watch state for the moment config becomes available, then auto-fill
    // the folder field once and refresh. We don't unsubscribe early —
    // the previous setTimeout that called this._unsub() twice was a bug
    // that prevented the library page from ever updating.
    this._unsub = subscribe(() => {
      if (!this._folder) {
        const cfg = getState().config;
        if (cfg?.default_output_folder) {
          this._folder = cfg.default_output_folder;
          this._refresh();
          this.requestUpdate();
        }
      }
      this.requestUpdate();
    });
    // If config already loaded before this page mounted, apply now.
    const cfg = getState().config;
    if (cfg?.default_output_folder && !this._folder) {
      this._folder = cfg.default_output_folder;
      this._refresh();
    }
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsub?.();
  }

  async _refresh() {
    if (!this._folder.trim()) return;
    this._loading = true;
    try {
      const r = await api.listOutputFolder(this._folder);
      this._files = r.files || [];
    } catch (e) {
      notify('error', e.detail || e.message);
    } finally {
      this._loading = false;
    }
  }

  render() {
    return html`
      <header class="mb-8">
        <h2 class="text-2xl font-semibold">Library</h2>
        <p class="text-zinc-400 mt-1">Browse rendered videos in an output folder.</p>
      </header>

      <ui-card class="mb-6">
        <div class="flex items-end gap-2">
          <div class="flex-1">
            <ui-input
              label="Output folder"
              .value=${this._folder}
              @input=${(e) => { this._folder = e.detail.value; }}
              placeholder="C:\\Users\\you\\Videos"
            ></ui-input>
          </div>
          <ui-button variant="primary" icon="refresh" @click=${() => this._refresh()} .loading=${this._loading}>
            Load
          </ui-button>
        </div>
      </ui-card>

      ${this._playing ? html`
        <ui-card title=${this._playing.name} class="mb-6">
          <video controls autoplay style="width:100%; max-height:60vh; background:#000; border-radius:8px;"
            src=${api.videoStreamUrl(this._playing.path)}></video>
          <div class="mt-3 flex justify-end">
            <ui-button variant="ghost" size="sm" icon="x" @click=${() => { this._playing = null; }}>Close player</ui-button>
          </div>
        </ui-card>
      ` : ''}

      ${this._files.length === 0 ? html`
        <ui-card><p class="text-sm text-zinc-500">${this._loading ? 'Loading…' : 'No .mp4 files in this folder yet.'}</p></ui-card>
      ` : html`
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          ${this._files.map((f) => html`
            <div class="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden hover:border-indigo-700 transition-colors group">
              <div class="aspect-video bg-zinc-950 flex items-center justify-center cursor-pointer relative"
                   @click=${() => { this._playing = f; window.scrollTo({ top: 0, behavior: 'smooth' }); }}>
                <video class="w-full h-full object-cover" muted preload="metadata"
                  src=${api.videoStreamUrl(f.path) + '#t=1'}></video>
                <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <ui-icon name="play" size="40"></ui-icon>
                </div>
              </div>
              <div class="p-3">
                <p class="font-medium text-sm truncate" title=${f.name}>${f.name}</p>
                <p class="text-xs text-zinc-500 mt-1">${this._fmtSize(f.size_bytes)} · ${this._fmtDate(f.mtime)}</p>
              </div>
            </div>
          `)}
        </div>
      `}
    `;
  }

  _fmtSize(bytes) {
    if (!bytes) return '';
    const mb = bytes / (1024 * 1024);
    return mb > 1 ? `${mb.toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
  }
  _fmtDate(mtime) {
    if (!mtime) return '';
    try { return new Date(mtime * 1000).toLocaleString(); } catch { return ''; }
  }
}
customElements.define('app-page-library', PageLibrary);
