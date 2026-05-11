import { LitElement, html } from 'lit';
import { api } from '../api.js';
import { getState, subscribe, notify, refreshJobs } from '../state.js';
import { navigate } from '../router.js';
import '../components.js';

const CANVAS_OPTIONS = [
  { value: 'shorts',    label: '9:16 Shorts/Reels (1080×1920)' },
  { value: 'landscape', label: '16:9 Landscape (1920×1080)' },
  { value: 'square',    label: '1:1 Square (1080×1080)' },
];

const MODEL_OPTIONS = [
  { value: 'claude-opus-4-7',         label: 'Claude Opus 4.7' },
  { value: 'claude-sonnet-4-6',       label: 'Claude Sonnet 4.6' },
  { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5' },
];

const TRANSITION_OPTIONS = [
  'fade', 'fadeblack', 'fadewhite',
  'slideleft', 'slideright', 'slideup', 'slidedown',
  'circleopen', 'circleclose', 'radial', 'smoothleft', 'smoothright',
].map((n) => ({ value: n, label: n }));

export class PageNewJob extends LitElement {
  static properties = {
    _form: { state: true },
    _detectedFormat: { state: true },
    _submitting: { state: true },
  };

  createRenderRoot() { return this; }

  constructor() {
    super();
    this._form = {
      title: '',
      script: '',
      output_folder: '',
      style_key: 'motion_graphic',
      canvas_key: 'shorts',
      voice_profile_id: '',
      narration_speed: 1.0,
      transition_seconds: 0.5,
      transition_name: 'fade',
      anthropic_model: 'claude-opus-4-7',
    };
    this._detectedFormat = null;
    this._submitting = false;
  }

  connectedCallback() {
    super.connectedCallback();
    // Apply config defaults exactly once, the first time config is
    // available. Doing this in `updated()` was wrong — it fired on every
    // render and re-applied the same defaults (even when nothing actually
    // changed), which set `changed=true` and triggered another render.
    // Result: infinite render loop, page-unresponsive.
    this._defaultsApplied = false;
    this._unsub = subscribe(() => {
      if (!this._defaultsApplied && getState().config) {
        this._defaultsApplied = true;
        this._applyConfigDefaults();
      }
      this.requestUpdate();
    });
    // If state was already loaded before this page mounted, apply now.
    if (!this._defaultsApplied && getState().config) {
      this._defaultsApplied = true;
      this._applyConfigDefaults();
    }
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsub?.();
  }

  _applyConfigDefaults() {
    const cfg = getState().config;
    if (!cfg) return;
    // Build a new _form object by copying current values then overlaying
    // config defaults — but ONLY where a meaningful change would happen.
    // Comparing before assigning prevents the no-op-then-requestUpdate loop.
    const next = { ...this._form };
    let dirty = false;
    if (!next.output_folder && cfg.default_output_folder) {
      next.output_folder = cfg.default_output_folder;
      dirty = true;
    }
    if (cfg.default_style_key && next.style_key !== cfg.default_style_key) {
      next.style_key = cfg.default_style_key;
      dirty = true;
    }
    if (cfg.default_canvas_key && next.canvas_key !== cfg.default_canvas_key) {
      next.canvas_key = cfg.default_canvas_key;
      dirty = true;
    }
    if (!next.voice_profile_id && cfg.default_voice_profile_id) {
      next.voice_profile_id = cfg.default_voice_profile_id;
      dirty = true;
    }
    if (dirty) {
      // Assigning the property (not mutating in place) triggers Lit's
      // reactive update naturally — no manual requestUpdate needed.
      this._form = next;
    }
  }

  _set(k, v) {
    this._form = { ...this._form, [k]: v };
    if (k === 'script') this._detectFormat(v);
  }

  _detectFormat(text) {
    // Lightweight client-side guess; server has the real parser. We surface
    // a badge so the user knows what'll happen.
    if (/\[SCENE\s+\d+/i.test(text) && /\[NARRATION\]/i.test(text) && /\[VISUAL\]/i.test(text)) {
      this._detectedFormat = 'tagged';
    } else if (/^\s*Point\s+\d+\s*[:.]/im.test(text) && /VOICEOVER\s*:/i.test(text)) {
      this._detectedFormat = 'whiteboard';
    } else if (text.trim().length > 20) {
      this._detectedFormat = 'freeform';
    } else {
      this._detectedFormat = null;
    }
  }

  async _submit() {
    const errors = [];
    if (!this._form.title.trim()) errors.push('title');
    if (!this._form.script.trim()) errors.push('script');
    if (!this._form.output_folder.trim()) errors.push('output folder');
    if (!this._form.voice_profile_id) errors.push('voice profile');
    if (errors.length) {
      notify('warning', `Missing: ${errors.join(', ')}`);
      return;
    }
    this._submitting = true;
    try {
      const job = await api.enqueueJob(this._form);
      notify('success', `Queued '${job.request.title}'`);
      refreshJobs();
      navigate('queue');
    } catch (e) {
      notify('error', e.detail || e.message);
    } finally {
      this._submitting = false;
    }
  }

  render() {
    const s = getState();
    const styleOptions = (s.styles || []).map((st) => ({ value: st.key, label: st.label }));
    const voiceOptions = (s.config?.voice_profiles || []).map((p) => ({
      value: p.id, label: `${p.name}${p.description ? ' — ' + p.description : ''}`,
    }));

    return html`
      <header class="mb-8">
        <h2 class="text-2xl font-semibold">New job</h2>
        <p class="text-zinc-400 mt-1">Submit a script. The system will queue it and render when its turn comes.</p>
      </header>

      <div class="space-y-6">
        <ui-card title="Title & output">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ui-input
              label="Video title"
              hint="Used as the saved filename. Auto-suffixed if it already exists."
              .value=${this._form.title}
              @input=${(e) => this._set('title', e.detail.value)}
              placeholder="e.g. Rapid Tranquillisation"
            ></ui-input>
            <ui-input
              label="Output folder"
              hint="Where the .mp4 lands. Windows path: C:\\Users\\you\\Videos"
              .value=${this._form.output_folder}
              @input=${(e) => this._set('output_folder', e.detail.value)}
              placeholder="C:\\Users\\you\\Videos"
            ></ui-input>
          </div>
        </ui-card>

        <ui-card title="Script">
          <div class="mb-3 flex items-center gap-2">
            <span class="text-xs text-zinc-500">Format:</span>
            ${this._detectedFormat === 'tagged' ? html`<ui-badge variant="success">Tagged · ready</ui-badge>` :
              this._detectedFormat === 'whiteboard' ? html`<ui-badge variant="info">Whiteboard · mechanical parse</ui-badge>` :
              this._detectedFormat === 'freeform' ? html`<ui-badge variant="warning">Freeform · Claude will normalize</ui-badge>` :
              html`<ui-badge>—</ui-badge>`}
          </div>
          <ui-textarea
            mono
            rows="14"
            placeholder="[SCENE 1]\n[NARRATION]\nYour narration here.\n[/NARRATION]\n[VISUAL]\nStep 1: …\n[/VISUAL]\n[/SCENE]"
            .value=${this._form.script}
            @input=${(e) => this._set('script', e.detail.value)}
          ></ui-textarea>
        </ui-card>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <ui-card title="Style & canvas">
            <div class="space-y-4">
              <ui-select
                label="Style"
                .value=${this._form.style_key}
                .options=${styleOptions}
                @change=${(e) => this._set('style_key', e.detail.value)}
              ></ui-select>
              <ui-select
                label="Aspect ratio"
                .value=${this._form.canvas_key}
                .options=${CANVAS_OPTIONS}
                @change=${(e) => this._set('canvas_key', e.detail.value)}
              ></ui-select>
            </div>
          </ui-card>

          <ui-card title="Voice">
            ${voiceOptions.length === 0 ? html`
              <p class="text-sm text-zinc-500">No voice profiles yet.
              <a href="#" @click=${(e) => { e.preventDefault(); navigate('settings'); }} class="text-indigo-400 hover:underline">Add one in Settings →</a></p>
            ` : html`
              <ui-select
                label="Voice profile"
                .value=${this._form.voice_profile_id}
                .options=${[{ value: '', label: '— pick a voice —' }, ...voiceOptions]}
                @change=${(e) => this._set('voice_profile_id', e.detail.value)}
              ></ui-select>
            `}
          </ui-card>
        </div>

        <details>
          <summary class="cursor-pointer text-sm text-zinc-400 hover:text-zinc-200 py-2">Advanced options</summary>
          <ui-card class="mt-2">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <ui-input
                type="number"
                label="Narration speed (0.5–2.0)"
                .value=${String(this._form.narration_speed)}
                @input=${(e) => this._set('narration_speed', parseFloat(e.detail.value) || 1.0)}
              ></ui-input>
              <ui-input
                type="number"
                label="Transition duration (s)"
                .value=${String(this._form.transition_seconds)}
                @input=${(e) => this._set('transition_seconds', parseFloat(e.detail.value) || 0.0)}
              ></ui-input>
              <ui-select
                label="Transition style"
                .value=${this._form.transition_name}
                .options=${TRANSITION_OPTIONS}
                @change=${(e) => this._set('transition_name', e.detail.value)}
              ></ui-select>
              <ui-select
                label="Claude model"
                .value=${this._form.anthropic_model}
                .options=${MODEL_OPTIONS}
                @change=${(e) => this._set('anthropic_model', e.detail.value)}
              ></ui-select>
            </div>
          </ui-card>
        </details>

        <div class="flex justify-end pt-2">
          <ui-button
            variant="primary"
            size="lg"
            icon="plus"
            .loading=${this._submitting}
            @click=${() => this._submit()}
          >
            Add to queue
          </ui-button>
        </div>
      </div>
    `;
  }
}
customElements.define('app-page-new-job', PageNewJob);
