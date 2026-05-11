import { LitElement, html } from 'lit';
import { api } from '../api.js';
import { getState, subscribe, notify, refreshStyles } from '../state.js';
import '../components.js';

export class PageStyles extends LitElement {
  static properties = {
    _editing: { state: true },
  };
  createRenderRoot() { return this; }

  constructor() {
    super();
    this._editing = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this._unsub = subscribe(() => this.requestUpdate());
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsub?.();
  }

  _newStyle() {
    this._editing = {
      key: '',
      label: '',
      builtin: false,
      description: '',
      script_guidance: '',
      html_guidance: '',
      scene_range_min: 3,
      scene_range_max: 6,
    };
  }

  _editCustom(s) {
    this._editing = JSON.parse(JSON.stringify(s));
  }

  async _save() {
    const e = this._editing;
    if (!e.key.trim() || !e.label.trim()) {
      notify('warning', 'Style needs a key and label.');
      return;
    }
    if (!/^[a-z][a-z0-9_]*$/.test(e.key)) {
      notify('warning', 'Key must be lowercase snake_case (letters/digits/underscore).');
      return;
    }
    try {
      await api.addStyle(e);
      notify('success', `Saved '${e.label}'`);
      this._editing = null;
      await refreshStyles();
    } catch (err) {
      notify('error', err.detail || err.message);
    }
  }

  async _delete(key) {
    if (!confirm('Delete this custom style?')) return;
    try {
      await api.deleteStyle(key);
      notify('success', 'Deleted.');
      await refreshStyles();
    } catch (err) {
      notify('error', err.detail || err.message);
    }
  }

  render() {
    const styles = getState().styles || [];
    const builtin = styles.filter((s) => s.builtin);
    const custom = styles.filter((s) => !s.builtin);

    return html`
      <header class="mb-8 flex items-start justify-between">
        <div>
          <h2 class="text-2xl font-semibold">Styles</h2>
          <p class="text-zinc-400 mt-1">Visual styles applied during script normalization and HTML generation.</p>
        </div>
        ${!this._editing ? html`
          <ui-button variant="primary" icon="plus" @click=${() => this._newStyle()}>New style</ui-button>
        ` : ''}
      </header>

      ${this._editing ? this._renderEditor() : html`
        <section class="mb-8">
          <h3 class="text-sm font-semibold text-zinc-300 mb-3 uppercase tracking-wide">Built-in (${builtin.length})</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${builtin.map((s) => this._renderStyleCard(s, false))}
          </div>
        </section>

        <section>
          <h3 class="text-sm font-semibold text-zinc-300 mb-3 uppercase tracking-wide">Custom (${custom.length})</h3>
          ${custom.length === 0 ? html`
            <ui-card><p class="text-sm text-zinc-500">No custom styles yet. Click "New style" to add one.</p></ui-card>
          ` : html`
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              ${custom.map((s) => this._renderStyleCard(s, true))}
            </div>
          `}
        </section>
      `}
    `;
  }

  _renderStyleCard(s, editable) {
    return html`
      <div class="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div class="flex items-start justify-between mb-2">
          <div>
            <h4 class="font-semibold">${s.label}</h4>
            <code class="text-xs text-zinc-500">${s.key}</code>
          </div>
          ${s.builtin
            ? html`<ui-badge variant="info">built-in</ui-badge>`
            : html`<ui-badge>custom</ui-badge>`}
        </div>
        ${s.description ? html`<p class="text-sm text-zinc-400 mt-2">${s.description}</p>` : ''}
        <p class="text-xs text-zinc-500 mt-3">Scenes: ${s.scene_range_min}–${s.scene_range_max}</p>
        <div class="mt-4 flex gap-2 justify-end">
          ${editable ? html`
            <ui-button variant="ghost" size="sm" @click=${() => this._editCustom(s)}>Edit</ui-button>
            <ui-button variant="ghost" size="sm" icon="trash" @click=${() => this._delete(s.key)}></ui-button>
          ` : ''}
        </div>
      </div>
    `;
  }

  _renderEditor() {
    const e = this._editing;
    const set = (k, v) => { this._editing = { ...this._editing, [k]: v }; };
    return html`
      <ui-card title=${e.key ? 'Edit style' : 'New style'}>
        <div class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ui-input label="Label" .value=${e.label}
              @input=${(ev) => set('label', ev.detail.value)}
              placeholder="My motion graphic"></ui-input>
            <ui-input label="Key (snake_case)" .value=${e.key}
              @input=${(ev) => set('key', ev.detail.value)}
              hint="Unique identifier, e.g. my_brand_style"></ui-input>
          </div>
          <ui-input label="Description" .value=${e.description}
            @input=${(ev) => set('description', ev.detail.value)}></ui-input>
          <ui-textarea
            label="Script guidance"
            rows="6"
            hint="Told to Claude during freeform→tagged normalization. How should this style structure scenes? What's the tone?"
            .value=${e.script_guidance}
            @input=${(ev) => set('script_guidance', ev.detail.value)}
          ></ui-textarea>
          <ui-textarea
            label="HTML guidance"
            rows="10"
            mono
            hint="Appended to the HTML generator's system prompt. Specify palette, typography, animation grammar, layout rules."
            .value=${e.html_guidance}
            @input=${(ev) => set('html_guidance', ev.detail.value)}
          ></ui-textarea>
          <div class="grid grid-cols-2 gap-4">
            <ui-input label="Min scenes" type="number" .value=${String(e.scene_range_min)}
              @input=${(ev) => set('scene_range_min', parseInt(ev.detail.value) || 3)}></ui-input>
            <ui-input label="Max scenes" type="number" .value=${String(e.scene_range_max)}
              @input=${(ev) => set('scene_range_max', parseInt(ev.detail.value) || 6)}></ui-input>
          </div>
        </div>
        <div class="mt-6 flex justify-end gap-2 pt-4 border-t border-zinc-800">
          <ui-button variant="ghost" @click=${() => { this._editing = null; }}>Cancel</ui-button>
          <ui-button variant="primary" @click=${() => this._save()}>Save style</ui-button>
        </div>
      </ui-card>
    `;
  }
}
customElements.define('app-page-styles', PageStyles);
