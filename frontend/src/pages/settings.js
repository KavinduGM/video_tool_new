import { LitElement, html } from 'lit';
import { api } from '../api.js';
import { getState, subscribe, notify, refreshConfig, refreshHfStatus } from '../state.js';
import '../components.js';

export class PageSettings extends LitElement {
  static properties = {
    _draft: { state: true },
    _newProfile: { state: true },
    _ttsHealthByProfile: { state: true },
    _busy: { state: true },
  };
  createRenderRoot() { return this; }

  constructor() {
    super();
    this._draft = null;
    this._newProfile = this._blankProfile();
    this._ttsHealthByProfile = {};
    this._busy = false;
  }

  _blankProfile() {
    return {
      id: '',
      name: '',
      server_url: 'http://127.0.0.1:8000',
      api_key: '',
      voice_id: '',
      description: '',
    };
  }

  connectedCallback() {
    super.connectedCallback();
    this._unsub = subscribe(() => {
      if (!this._draft && getState().config) {
        this._draft = JSON.parse(JSON.stringify(getState().config));
      }
      this.requestUpdate();
    });
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsub?.();
  }

  async _save() {
    this._busy = true;
    try {
      await api.putConfig(this._draft);
      notify('success', 'Settings saved.');
      await refreshConfig();
    } catch (e) {
      notify('error', e.detail || e.message);
    } finally {
      this._busy = false;
    }
  }

  async _addProfile() {
    if (!this._newProfile.name || !this._newProfile.api_key || !this._newProfile.voice_id) {
      notify('warning', 'Profile needs name, API key, and voice ID.');
      return;
    }
    this._newProfile.id = this._newProfile.id || Math.random().toString(36).slice(2, 10);
    try {
      await api.addVoiceProfile(this._newProfile);
      notify('success', `Added '${this._newProfile.name}'`);
      this._newProfile = this._blankProfile();
      await refreshConfig();
    } catch (e) {
      notify('error', e.detail || e.message);
    }
  }

  async _testProfile(id) {
    try {
      const h = await api.ttsHealth(id);
      this._ttsHealthByProfile = { ...this._ttsHealthByProfile, [id]: h };
      if (h.reachable && h.status === 'ok') {
        notify('success', `TTS reachable · ${h.device || ''} · ${h.voices || 0} voices`);
      } else if (h.reachable) {
        notify('warning', `TTS reachable but status: ${h.status}`);
      } else {
        notify('error', `TTS unreachable: ${h.error || 'unknown error'}`);
      }
    } catch (e) {
      notify('error', e.detail || e.message);
    }
  }

  async _removeProfile(id) {
    if (!confirm('Remove this voice profile? (Jobs using it will fail.)')) return;
    try {
      await api.deleteVoiceProfile(id);
      notify('success', 'Removed.');
      await refreshConfig();
    } catch (e) {
      notify('error', e.detail || e.message);
    }
  }

  async _runSmokeTest() {
    notify('info', 'Smoke-testing HyperFrames render…');
    try {
      const r = await api.hfSmokeTest();
      if (r.passed) notify('success', 'HyperFrames render works.');
      else notify('error', `Smoke test failed: ${r.error}`);
      await refreshHfStatus();
    } catch (e) {
      notify('error', e.detail || e.message);
    }
  }

  async _browseDefaultFolder() {
    try {
      const r = await api.pickFolder();
      if (r.path) {
        this._draft.default_output_folder = r.path;
        this.requestUpdate();
      }
    } catch (e) {
      notify('error', `Folder picker failed: ${e.detail || e.message}`);
    }
  }

  async _updateHyperFrames() {
    if (!confirm('Update HyperFrames to the latest npm version?')) return;
    notify('info', 'Updating HyperFrames (npm install -g hyperframes@latest)…');
    try {
      const r = await api.hfUpdate();
      notify('success', `Updated to ${r.installed_version}`);
      await refreshHfStatus();
    } catch (e) {
      notify('error', e.detail || e.message);
    }
  }

  render() {
    if (!this._draft) return html`<p class="text-zinc-500">Loading…</p>`;
    const d = this._draft;
    const hf = getState().hfStatus;
    return html`
      <header class="mb-8">
        <h2 class="text-2xl font-semibold">Settings</h2>
        <p class="text-zinc-400 mt-1">API keys, voice profiles, and defaults.</p>
      </header>

      <div class="space-y-6">
        <ui-card title="API keys">
          <ui-input
            label="Anthropic API key"
            type="password"
            .value=${d.anthropic_api_key || ''}
            @input=${(e) => { d.anthropic_api_key = e.detail.value; this.requestUpdate(); }}
            placeholder="sk-ant-…"
            hint="Used for script normalization and per-scene HTML generation."
          ></ui-input>
        </ui-card>

        <ui-card title="Voice profiles" subtitle="Saved configurations for your local TTS server.">
          ${d.voice_profiles.length === 0 ? html`
            <p class="text-sm text-zinc-500 mb-4">No voice profiles yet.</p>
          ` : html`
            <ul class="divide-y divide-zinc-800 mb-4">
              ${d.voice_profiles.map((p) => html`
                <li class="py-3 flex items-center justify-between">
                  <div class="min-w-0 flex-1 mr-3">
                    <p class="font-medium text-sm">${p.name}</p>
                    <p class="text-xs text-zinc-500 mt-0.5 font-mono">${p.server_url} · voice ${p.voice_id}</p>
                    ${this._ttsHealthByProfile[p.id] ? html`
                      <div class="mt-1">
                        ${this._ttsHealthByProfile[p.id].reachable
                          ? html`<ui-badge variant="success">${this._ttsHealthByProfile[p.id].status}</ui-badge>`
                          : html`<ui-badge variant="error">unreachable</ui-badge>`}
                      </div>
                    ` : ''}
                  </div>
                  <div class="flex gap-1">
                    <ui-button variant="ghost" size="sm" @click=${() => this._testProfile(p.id)}>Test</ui-button>
                    <ui-button variant="ghost" size="sm" icon="trash" @click=${() => this._removeProfile(p.id)}></ui-button>
                  </div>
                </li>
              `)}
            </ul>
          `}

          <div class="border-t border-zinc-800 pt-4">
            <p class="text-sm font-medium mb-3">Add new profile</p>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <ui-input label="Name"      .value=${this._newProfile.name}
                @input=${(e) => { this._newProfile = { ...this._newProfile, name: e.detail.value }; }}></ui-input>
              <ui-input label="Server URL" .value=${this._newProfile.server_url}
                @input=${(e) => { this._newProfile = { ...this._newProfile, server_url: e.detail.value }; }}></ui-input>
              <ui-input label="API key" type="password" .value=${this._newProfile.api_key}
                @input=${(e) => { this._newProfile = { ...this._newProfile, api_key: e.detail.value }; }}
                placeholder="vct_…"></ui-input>
              <ui-input label="Voice ID" .value=${this._newProfile.voice_id}
                @input=${(e) => { this._newProfile = { ...this._newProfile, voice_id: e.detail.value }; }}
                placeholder="e6f31a8c4d92"></ui-input>
              <div class="md:col-span-2">
                <ui-input label="Description (optional)" .value=${this._newProfile.description}
                  @input=${(e) => { this._newProfile = { ...this._newProfile, description: e.detail.value }; }}></ui-input>
              </div>
            </div>
            <div class="mt-3 flex justify-end">
              <ui-button variant="primary" icon="plus" @click=${() => this._addProfile()}>Add profile</ui-button>
            </div>
          </div>
        </ui-card>

        <ui-card title="Defaults" subtitle="Prefills for new jobs.">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="flex items-end gap-2">
              <div class="flex-1">
                <ui-input label="Default output folder" .value=${d.default_output_folder || ''}
                  @input=${(e) => { d.default_output_folder = e.detail.value; this.requestUpdate(); }}
                  placeholder="C:\\Users\\you\\Videos"></ui-input>
              </div>
              <ui-button variant="secondary" @click=${() => this._browseDefaultFolder()}>Browse…</ui-button>
            </div>
            <ui-select label="Default canvas" .value=${d.default_canvas_key}
              .options=${[
                { value: 'shorts', label: '9:16 Shorts' },
                { value: 'landscape', label: '16:9 Landscape' },
                { value: 'square', label: '1:1 Square' },
              ]}
              @change=${(e) => { d.default_canvas_key = e.detail.value; this.requestUpdate(); }}
            ></ui-select>
            <ui-select label="Default style" .value=${d.default_style_key}
              .options=${(getState().styles || []).map((s) => ({ value: s.key, label: s.label }))}
              @change=${(e) => { d.default_style_key = e.detail.value; this.requestUpdate(); }}
            ></ui-select>
            <ui-select label="Default voice profile" .value=${d.default_voice_profile_id || ''}
              .options=${[{ value: '', label: '— none —' }, ...d.voice_profiles.map((p) => ({ value: p.id, label: p.name }))]}
              @change=${(e) => { d.default_voice_profile_id = e.detail.value; this.requestUpdate(); }}
            ></ui-select>
          </div>
        </ui-card>

        <ui-card title="HyperFrames">
          <div class="flex items-center justify-between mb-4">
            <div>
              <p class="text-sm">
                Installed:
                ${hf?.installed_version ? html`<code class="text-zinc-200">${hf.installed_version}</code>` : html`<span class="text-rose-400">not installed</span>`}
                ${hf?.latest_version && hf.latest_version !== hf.installed_version
                  ? html`· latest: <code class="text-amber-300">${hf.latest_version}</code>`
                  : ''}
              </p>
              ${hf?.last_smoke_test_passed === false ? html`
                <p class="text-xs text-rose-400 mt-1">Last smoke test failed: ${hf.last_smoke_test_error}</p>
              ` : ''}
            </div>
            <div class="flex gap-2">
              <ui-button variant="ghost" size="sm" @click=${() => this._runSmokeTest()}>Smoke test</ui-button>
              ${hf?.is_outdated || !hf?.installed_version ? html`
                <ui-button variant="primary" size="sm" icon="refresh" @click=${() => this._updateHyperFrames()}>Update</ui-button>
              ` : ''}
            </div>
          </div>
        </ui-card>

        <div class="flex justify-end pt-4 border-t border-zinc-800">
          <ui-button variant="primary" size="lg" .loading=${this._busy} @click=${() => this._save()}>Save settings</ui-button>
        </div>
      </div>
    `;
  }
}
customElements.define('app-page-settings', PageSettings);
