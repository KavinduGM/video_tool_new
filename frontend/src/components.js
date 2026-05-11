/**
 * Shared low-level components used by all pages: Card, Button, Badge,
 * Input, Textarea, Select, Toast, EmptyState, Icon.
 *
 * Each is a Lit element that wraps Tailwind classes. The benefit over
 * raw Tailwind is consistency — buttons everywhere look identical without
 * everyone copying the same long class string.
 */

import { LitElement, html, css, unsafeCSS } from 'lit';

/**
 * COMPONENT RENDERING STRATEGY (matters — read this before changing things):
 *
 * Components that use <slot> for composition (Card, Button, Badge) MUST
 * render into Shadow DOM. Slots only work inside Shadow DOM. We give them
 * their own scoped CSS via `static styles = css`...``.
 *
 * Components that are self-contained (Input, Textarea, Select, Toasts) keep
 * light-DOM rendering via `createRenderRoot() { return this; }` so that
 * Tailwind utility classes on the rendered <input>/<select> are picked up
 * by the global Tailwind scan.
 *
 * The earlier version used <slot> with light-DOM rendering for everything —
 * which silently fails: the slot element renders as an empty <slot> with
 * no content projection, and the user's child elements stay at the wrong
 * position in the document. Don't do that again.
 */

// ─── Inline SVG icon set. Keeps the bundle dependency-free. ────────────

const ICONS = {
  home:    '<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12 12 3l9.75 9M4.5 9.75v9.75A.75.75 0 0 0 5.25 21h4.5v-6h4.5v6h4.5a.75.75 0 0 0 .75-.75V9.75"/>',
  plus:    '<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/>',
  list:    '<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 6.75h12M8.25 12h12M8.25 17.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z"/>',
  film:    '<path stroke-linecap="round" stroke-linejoin="round" d="M3 8.25h18M3 15.75h18M6 4.5v15m6-15v15m6-15v15M3.75 4.5h16.5a.75.75 0 0 1 .75.75v13.5a.75.75 0 0 1-.75.75H3.75a.75.75 0 0 1-.75-.75V5.25a.75.75 0 0 1 .75-.75Z"/>',
  palette: '<path stroke-linecap="round" stroke-linejoin="round" d="M4.098 19.902a3.75 3.75 0 0 0 5.304 0l6.401-6.402M6.75 21A3.75 3.75 0 0 1 3 17.25V4.125C3 3.504 3.504 3 4.125 3h5.25c.621 0 1.125.504 1.125 1.125v4.072M6.75 21a3.75 3.75 0 0 0 3.75-3.75V8.197M6.75 21h13.125c.621 0 1.125-.504 1.125-1.125v-5.25c0-.621-.504-1.125-1.125-1.125h-4.072M10.5 8.197l2.88-2.88c.438-.439 1.15-.439 1.59 0l3.712 3.713c.44.44.44 1.152 0 1.59l-2.879 2.88M6.75 17.25h.008v.008H6.75v-.008Z"/>',
  gear:    '<path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28Z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/>',
  check:   '<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"/>',
  x:       '<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/>',
  refresh: '<path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"/>',
  play:    '<path stroke-linecap="round" stroke-linejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z"/>',
  trash:   '<path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"/>',
  alert:   '<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.732 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"/>',
};

export class IconEl extends LitElement {
  static properties = { name: {}, size: {} };
  createRenderRoot() { return this; }
  render() {
    const sz = this.size || 18;
    const path = ICONS[this.name] || '';
    return html`<svg
      xmlns="http://www.w3.org/2000/svg"
      width="${sz}" height="${sz}"
      viewBox="0 0 24 24" fill="none"
      stroke="currentColor" stroke-width="1.6"
      style="display:inline-block; vertical-align: -3px;"
      .innerHTML=${path}
    ></svg>`;
  }
}
customElements.define('ui-icon', IconEl);

// ─── Card (panel) ──────────────────────────────────────────────────────
// Uses Shadow DOM so <slot> works. Tailwind classes on slotted children
// (in light DOM) still get picked up by the global Tailwind scan.

export class CardEl extends LitElement {
  static properties = { title: {}, subtitle: {} };

  static styles = css`
    :host {
      display: block;
      background: rgb(24 24 27);          /* zinc-900 */
      border: 1px solid rgb(39 39 42);    /* zinc-800 */
      border-radius: 0.75rem;
      padding: 1.25rem;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
      box-sizing: border-box;
    }
    .header {
      margin-bottom: 1rem;
    }
    h3 {
      font-size: 1rem;
      font-weight: 600;
      color: rgb(244 244 245);
      margin: 0;
      line-height: 1.4;
      font-family: inherit;
    }
    .subtitle {
      font-size: 0.875rem;
      color: rgb(161 161 170);
      margin: 0.125rem 0 0;
      font-family: inherit;
    }
  `;

  render() {
    return html`
      ${this.title ? html`
        <div class="header">
          <h3>${this.title}</h3>
          ${this.subtitle ? html`<p class="subtitle">${this.subtitle}</p>` : ''}
        </div>
      ` : ''}
      <slot></slot>
    `;
  }
}
customElements.define('ui-card', CardEl);

// ─── Button ────────────────────────────────────────────────────────────
// Shadow DOM + self-contained CSS. Variant/size selected via `variant`
// and `size` attributes (reflected so :host([variant=…]) selectors work).

export class ButtonEl extends LitElement {
  static properties = {
    variant: { reflect: true },              // primary | secondary | danger | ghost
    size: { reflect: true },                 // sm | md | lg
    disabled: { type: Boolean, reflect: true },
    loading: { type: Boolean, reflect: true },
    icon: {},
    full: { type: Boolean, reflect: true },
  };

  static styles = css`
    :host { display: inline-block; }
    :host([full]) { display: block; width: 100%; }
    button {
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      border: 1px solid transparent;
      border-radius: 0.375rem;
      font-weight: 500;
      font-family: inherit;
      cursor: pointer;
      transition: background-color 0.15s, border-color 0.15s;
      box-sizing: border-box;
    }
    :host([full]) button {
      width: 100%;
      justify-content: center;
    }
    button[disabled] {
      opacity: 0.5;
      cursor: not-allowed;
    }
    /* sizes */
    .sm { padding: 0.25rem 0.625rem; font-size: 0.75rem; }
    .md { padding: 0.375rem 0.875rem; font-size: 0.875rem; }
    .lg { padding: 0.5rem 1.25rem; font-size: 1rem; }
    /* variants */
    .primary {
      background: rgb(79 70 229); color: white; border-color: rgb(79 70 229);
    }
    .primary:hover:not([disabled]) { background: rgb(99 102 241); }
    .secondary {
      background: rgb(39 39 42); color: rgb(244 244 245); border-color: rgb(63 63 70);
    }
    .secondary:hover:not([disabled]) { background: rgb(63 63 70); }
    .danger {
      background: rgb(225 29 72); color: white; border-color: rgb(225 29 72);
    }
    .danger:hover:not([disabled]) { background: rgb(244 63 94); }
    .ghost {
      background: transparent; color: rgb(212 212 216); border-color: transparent;
    }
    .ghost:hover:not([disabled]) { background: rgb(39 39 42); }
    .spinner {
      width: 0.875rem;
      height: 0.875rem;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: currentColor;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      display: inline-block;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `;

  render() {
    const variant = this.variant || 'secondary';
    const size = this.size || 'md';
    return html`
      <button
        type="button"
        ?disabled=${this.disabled || this.loading}
        class="${variant} ${size}"
        @click=${this._onClick}
      >
        ${this.loading ? html`<span class="spinner"></span>` :
          this.icon ? html`<ui-icon name=${this.icon} size="14"></ui-icon>` : ''}
        <slot></slot>
      </button>
    `;
  }

  _onClick(e) {
    if (this.disabled || this.loading) return;
    // Re-dispatch click on the host so parent listeners with @click=… fire.
    // (The shadow-root button's click bubbles by default, but custom-element
    //  consumers usually expect @click on the host element itself.)
  }
}
customElements.define('ui-button', ButtonEl);

// ─── Badge ─────────────────────────────────────────────────────────────

export class BadgeEl extends LitElement {
  static properties = { variant: { reflect: true } };

  static styles = css`
    :host {
      display: inline-flex;
      align-items: center;
      padding: 0.125rem 0.5rem;
      font-size: 0.75rem;
      font-weight: 500;
      font-family: inherit;
      border: 1px solid rgb(63 63 70);
      border-radius: 0.375rem;
      background: rgb(39 39 42);
      color: rgb(212 212 216);
      line-height: 1.4;
    }
    :host([variant="success"]) {
      background: rgba(6, 78, 59, 0.5);
      color: rgb(110 231 183);
      border-color: rgb(6 95 70);
    }
    :host([variant="warning"]) {
      background: rgba(120, 53, 15, 0.5);
      color: rgb(252 211 77);
      border-color: rgb(146 64 14);
    }
    :host([variant="error"]) {
      background: rgba(127, 29, 29, 0.5);
      color: rgb(252 165 165);
      border-color: rgb(159 18 57);
    }
    :host([variant="info"]) {
      background: rgba(49, 46, 129, 0.5);
      color: rgb(165 180 252);
      border-color: rgb(67 56 202);
    }
  `;

  render() {
    return html`<slot></slot>`;
  }
}
customElements.define('ui-badge', BadgeEl);

// ─── Text inputs ───────────────────────────────────────────────────────

export class InputEl extends LitElement {
  static properties = {
    label: {},
    type: {},
    value: {},
    placeholder: {},
    hint: {},
    error: {},
    disabled: { type: Boolean },
  };
  createRenderRoot() { return this; }
  _onInput(e) {
    // STOP the native 'input' event from bubbling up to the parent.
    // Otherwise the parent's @input listener — written assuming the
    // custom-event shape (e.detail.value) — receives the native event
    // first, throws on `e.detail.value`, and Chrome stops processing
    // events on this input. Result: user can't type.
    e.stopPropagation();
    this.value = e.target.value;
    this.dispatchEvent(new CustomEvent('input', {
      detail: { value: e.target.value }, bubbles: false,
    }));
  }
  render() {
    const errorCls = this.error ? 'border-rose-700 focus-visible:outline-rose-500' : 'border-zinc-700';
    return html`
      <label class="block">
        ${this.label ? html`
          <span class="text-sm font-medium text-zinc-300 block mb-1.5">${this.label}</span>
        ` : ''}
        <input
          type=${this.type || 'text'}
          .value=${this.value || ''}
          placeholder=${this.placeholder || ''}
          ?disabled=${this.disabled}
          @input=${this._onInput}
          class="w-full bg-zinc-950 border ${errorCls} rounded-md px-3 py-2 text-sm
                 placeholder-zinc-600 focus:border-indigo-600
                 disabled:opacity-50 disabled:cursor-not-allowed"
        />
        ${this.error ? html`<p class="text-xs text-rose-400 mt-1">${this.error}</p>` :
          this.hint ? html`<p class="text-xs text-zinc-500 mt-1">${this.hint}</p>` : ''}
      </label>
    `;
  }
}
customElements.define('ui-input', InputEl);

export class TextareaEl extends LitElement {
  static properties = {
    label: {}, value: {}, placeholder: {}, rows: {}, hint: {},
    disabled: { type: Boolean }, mono: { type: Boolean },
  };
  createRenderRoot() { return this; }
  _onInput(e) {
    e.stopPropagation();   // see InputEl._onInput for the why
    this.value = e.target.value;
    this.dispatchEvent(new CustomEvent('input', {
      detail: { value: e.target.value }, bubbles: false,
    }));
  }
  render() {
    return html`
      <label class="block">
        ${this.label ? html`
          <span class="text-sm font-medium text-zinc-300 block mb-1.5">${this.label}</span>
        ` : ''}
        <textarea
          rows=${this.rows || 6}
          placeholder=${this.placeholder || ''}
          .value=${this.value || ''}
          ?disabled=${this.disabled}
          @input=${this._onInput}
          class="w-full bg-zinc-950 border border-zinc-700 rounded-md px-3 py-2 text-sm
                 placeholder-zinc-600 focus:border-indigo-600
                 disabled:opacity-50 disabled:cursor-not-allowed
                 ${this.mono ? 'font-mono' : ''}"
        ></textarea>
        ${this.hint ? html`<p class="text-xs text-zinc-500 mt-1">${this.hint}</p>` : ''}
      </label>
    `;
  }
}
customElements.define('ui-textarea', TextareaEl);

export class SelectEl extends LitElement {
  static properties = {
    label: {}, value: {}, options: { type: Array }, hint: {},
    disabled: { type: Boolean },
  };
  createRenderRoot() { return this; }
  _onChange(e) {
    e.stopPropagation();   // see InputEl._onInput for the why
    this.value = e.target.value;
    this.dispatchEvent(new CustomEvent('change', {
      detail: { value: e.target.value }, bubbles: false,
    }));
  }
  render() {
    return html`
      <label class="block">
        ${this.label ? html`
          <span class="text-sm font-medium text-zinc-300 block mb-1.5">${this.label}</span>
        ` : ''}
        <select
          .value=${this.value || ''}
          ?disabled=${this.disabled}
          @change=${this._onChange}
          class="w-full bg-zinc-950 border border-zinc-700 rounded-md px-3 py-2 text-sm
                 focus:border-indigo-600
                 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ${(this.options || []).map((o) => html`
            <option value=${o.value} ?selected=${o.value === this.value}>${o.label}</option>
          `)}
        </select>
        ${this.hint ? html`<p class="text-xs text-zinc-500 mt-1">${this.hint}</p>` : ''}
      </label>
    `;
  }
}
customElements.define('ui-select', SelectEl);

// ─── Toasts container ──────────────────────────────────────────────────

import { getState, subscribe } from './state.js';

export class ToastsEl extends LitElement {
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
    const items = getState().notifications;
    const colors = {
      info:    'bg-indigo-900/80 border-indigo-700 text-indigo-100',
      success: 'bg-emerald-900/80 border-emerald-700 text-emerald-100',
      warning: 'bg-amber-900/80 border-amber-700 text-amber-100',
      error:   'bg-rose-900/80 border-rose-700 text-rose-100',
    };
    return html`
      <div class="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-md">
        ${items.map((n) => html`
          <div class="border rounded-md px-4 py-3 text-sm shadow-lg backdrop-blur
                      ${colors[n.type] || colors.info}">${n.message}</div>
        `)}
      </div>
    `;
  }
}
customElements.define('ui-toasts', ToastsEl);
