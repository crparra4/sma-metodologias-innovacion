import './pestel.css';

// PESTEL del proyecto, en su forma tradicional: seis factores, cada elemento marcado como
// oportunidad o amenaza y de 3 a 5 priorizados. La vista sigue los cuatro pasos de la ficha
// (`knowledge/tools/Pestel.md`); no añade puntajes ni matrices que la ficha no pide.
// Cada factor es una columna y cada elemento es un post-it igual a los del tablero de
// Post-its: se escribe en la misma hoja emergente y su color dice si es oportunidad o amenaza.

type Kind = '' | 'oportunidad' | 'amenaza';
type Item = { id: string; text: string; kind: Kind; source: string; priority: boolean };
type FactorId = 'politico' | 'economico' | 'social' | 'tecnologico' | 'ecologico' | 'legal';
type Content = { challenge: string } & Record<FactorId, Item[]>;
type Pestel = Content & { version: number; updated_at: number | null };
type Role = 'owner' | 'editor' | 'viewer';
type Request = <T>(path: string, options?: RequestInit) => Promise<T>;
type Links = { ask: (text: string) => void };
type Factor = { id: FactorId; name: string; letter: string; hint: string; example: string };

// Nombre y pregunta de cada factor, con las palabras de la ficha.
const FACTORS: Factor[] = [
  { id: 'politico', name: 'Político', letter: 'P', hint: '¿Qué normativas, políticas públicas o decisiones de gobierno influyen?', example: 'Ej. La alcaldía abrió un programa de becas' },
  { id: 'economico', name: 'Económico', letter: 'E', hint: '¿Qué pasa con los costos, el presupuesto o la economía de tus usuarios?', example: 'Ej. Las familias recortan gastos en cursos' },
  { id: 'social', name: 'Social', letter: 'S', hint: '¿Qué comportamientos, expectativas o necesidades tienen las personas?', example: 'Ej. Los padres buscan actividades después de clase' },
  { id: 'tecnologico', name: 'Tecnológico', letter: 'T', hint: '¿Qué canales digitales, automatización o herramientas hay disponibles?', example: 'Ej. Casi todos los hogares tienen un celular' },
  { id: 'ecologico', name: 'Ecológico', letter: 'E', hint: '¿Qué factores ambientales o de sostenibilidad son relevantes?', example: 'Ej. El colegio exige reducir el uso de papel' },
  { id: 'legal', name: 'Legal', letter: 'L', hint: '¿Qué leyes, regulaciones u obligaciones aplican?', example: 'Ej. Ley de protección de datos de menores' },
];
const MAX_ITEMS = 8;
const MAX_PRIORITY = 5;
const MIN_PRIORITY = 3;
// Mismos colores de papel que los post-its del tablero.
const KIND_COLOR: Record<Kind, string> = { '': 'yellow', oportunidad: 'green', amenaza: 'pink' };
const KIND_LABEL: Record<Kind, string> = { '': 'Sin marcar', oportunidad: 'Oportunidad', amenaza: 'Amenaza' };
const ICON = (name: string) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;

const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = '') => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
const itemId = () => globalThis.crypto?.randomUUID?.() || `p${Date.now()}${Math.random().toString(36).slice(2)}`;
const emptyPestel = (): Pestel => ({ challenge: '', politico: [], economico: [], social: [], tecnologico: [], ecologico: [], legal: [], version: 0, updated_at: null });
const contentOf = (pestel: Pestel): Content => ({
  challenge: pestel.challenge, politico: pestel.politico, economico: pestel.economico, social: pestel.social,
  tecnologico: pestel.tecnologico, ecologico: pestel.ecologico, legal: pestel.legal,
});
const same = (a: string, b: string) => a.trim().toLocaleLowerCase('es') === b.trim().toLocaleLowerCase('es');

export class PestelController {
  private projectId = '';
  private role: Role = 'viewer';
  private draft: Pestel = emptyPestel();
  private saved = JSON.stringify(contentOf(emptyPestel()));
  private saving = false;
  private pendingSave = false;
  private loading = false;
  private loadToken = 0;
  private chatFacts: Record<string, unknown> = {};
  private usedFacts = new Set<string>();
  // Post-it abierto en la hoja: el factor y, si se edita, la nota.
  private editing: { factor: Factor; item: Item | null; fact: string } | null = null;

  constructor(private request: Request, private links: Links) {
    byId('pestel-save').addEventListener('click', () => { void this.save(); });
    byId<HTMLTextAreaElement>('pestel-challenge').addEventListener('input', event => {
      this.draft.challenge = (event.target as HTMLTextAreaElement).value;
      this.updateState();
    });
    // Al salir del reto se guarda solo, igual que al guardar un post-it.
    byId<HTMLTextAreaElement>('pestel-challenge').addEventListener('change', () => this.autosave());
    const dialog = byId<HTMLDialogElement>('pestel-dialog');
    byId('pestel-dialog-cancel').addEventListener('click', () => dialog.close());
    byId<HTMLFormElement>('pestel-form').addEventListener('submit', event => { event.preventDefault(); this.applyDialog(); });
    dialog.querySelectorAll<HTMLInputElement>('input[name="pestel-kind"]').forEach(radio => radio.addEventListener('change', () => this.paintDialog()));
    dialog.addEventListener('close', () => { this.editing = null; });
    window.addEventListener('beforeunload', event => {
      if (byId('pestel-view').hidden || !this.isDirty()) return;
      event.preventDefault();
    });
  }

  isDirty() { return JSON.stringify(contentOf(this.draft)) !== this.saved; }
  canLeave() { return !this.isDirty() || window.confirm('Hay cambios sin guardar en el PESTEL. ¿Quieres salir y descartarlos?'); }

  /** Datos que la persona dio en el chat y Hilo verificó; se ofrecen, no se insertan solos. */
  setChatFacts(facts: Record<string, unknown> = {}) {
    this.chatFacts = facts;
    if (!this.projectId) return;
    for (const factor of FACTORS) this.renderSuggestion(factor);
  }

  async open(projectId: string, role: Role, projectQuestion = '', chatFacts: Record<string, unknown> = {}) {
    this.projectId = projectId; this.role = role; this.chatFacts = chatFacts;
    this.usedFacts.clear();
    this.draft = emptyPestel(); this.saved = JSON.stringify(contentOf(this.draft)); this.render();
    await this.load(projectQuestion);
  }

  private allItems() { return FACTORS.flatMap(factor => this.draft[factor.id]); }
  private priorityCount() { return this.allItems().filter(item => item.priority).length; }

  private async load(projectQuestion = '') {
    const token = ++this.loadToken;
    this.loading = true; this.showError(''); this.updateState();
    try {
      const pestel = await this.request<Pestel>(`/projects/${encodeURIComponent(this.projectId)}/pestel`);
      if (token !== this.loadToken) return;
      this.draft = structuredClone(pestel);
      this.saved = JSON.stringify(contentOf(this.draft));
      const untouched = !pestel.challenge && !this.allItems().length;
      if (untouched && projectQuestion.trim()) this.draft.challenge = projectQuestion.trim().slice(0, 500);
      byId('pestel-subtitle').textContent = untouched && projectQuestion.trim()
        ? 'Copiamos el reto del cuaderno como borrador. Ajústalo si hace falta.'
        : 'Mira el entorno de tu reto desde seis lados.';
      this.render();
    } catch (error) { if (token === this.loadToken) this.showError((error as Error).message); }
    finally { if (token === this.loadToken) { this.loading = false; this.updateState(); } }
  }

  private render() {
    const challenge = byId<HTMLTextAreaElement>('pestel-challenge');
    challenge.value = this.draft.challenge; challenge.readOnly = this.role === 'viewer';
    byId('pestel-grid').replaceChildren(...FACTORS.map(factor => this.factorPanel(factor)));
    for (const factor of FACTORS) { this.renderItems(factor); this.renderSuggestion(factor); }
    this.updateState();
  }

  private factorPanel(factor: Factor): HTMLElement {
    const panel = make('section', 'pestel-factor'); panel.dataset.factor = factor.id;
    panel.setAttribute('aria-labelledby', `pestel-${factor.id}-title`);
    const head = make('header', 'pestel-factor-head');
    const letter = make('span', 'pestel-factor-letter', factor.letter); letter.setAttribute('aria-hidden', 'true');
    const title = make('h3', '', factor.name); title.id = `pestel-${factor.id}-title`;
    head.append(letter, title);
    const count = make('span', 'pestel-count'); count.id = `pestel-${factor.id}-count`; count.setAttribute('role', 'status');
    // Mismo muro que el tablero de Post-its: las notas heredan su aspecto.
    const list = make('div', 'notes-wall pestel-wall'); list.id = `pestel-${factor.id}-items`;
    const suggestion = make('div', 'pestel-suggestion'); suggestion.id = `pestel-${factor.id}-suggestion`; suggestion.hidden = true;
    const add = make('button', 'pestel-add'); add.type = 'button'; add.id = `pestel-${factor.id}-add`;
    const plus = make('span', 'pestel-add-plus', '+'); plus.setAttribute('aria-hidden', 'true');
    add.append(plus, make('span', '', 'Nuevo post-it'));
    add.setAttribute('aria-label', `Nuevo post-it en el factor ${factor.name}`);
    add.addEventListener('click', () => this.openDialog(factor));
    const ask = make('button', 'pestel-ask', 'Preguntarle a Hilo'); ask.type = 'button';
    ask.title = 'Sigue este factor en el chat, con una pregunta a la vez';
    ask.addEventListener('click', () => { void this.ask(factor); });
    panel.append(head, count, make('p', 'pestel-factor-question', factor.hint), list, suggestion, add, ask);
    return panel;
  }

  private renderItems(factor: Factor) {
    const list = byId(`pestel-${factor.id}-items`);
    list.replaceChildren(...this.draft[factor.id].map((item, index) => this.noteCard(factor, item, index)));
  }

  /** Un post-it como los del tablero: categoría arriba, texto, y abajo prioridad y fuente. */
  private noteCard(factor: Factor, item: Item, index: number): HTMLElement {
    const readOnly = this.role === 'viewer';
    const card = make('article', 'sticky-note pestel-note'); card.dataset.item = item.id; card.dataset.noteColor = KIND_COLOR[item.kind];
    card.classList.toggle('is-priority', item.priority);
    const name = `post-it ${index + 1} del factor ${factor.name}`;

    const top = make('div', 'note-top');
    const label = make('span', 'note-label'); label.append(make('span', 'note-category', KIND_LABEL[item.kind]));
    const actions = make('div', 'note-actions');
    const edit = make('button', 'note-action'); edit.type = 'button'; edit.innerHTML = ICON('edit'); edit.setAttribute('aria-label', `Editar ${name}`);
    edit.addEventListener('click', () => this.openDialog(factor, item));
    const remove = make('button', 'note-action'); remove.type = 'button'; remove.innerHTML = ICON('trash'); remove.setAttribute('aria-label', `Quitar ${name}`);
    if (!readOnly) actions.append(edit, remove);
    top.append(label, actions);

    const body = make('p', 'note-body', item.text);
    if (!readOnly) {
      // Tocar el texto abre la hoja, como quien levanta la nota para corregirla.
      body.classList.add('is-editable'); body.title = 'Editar este post-it';
      body.addEventListener('click', () => this.openDialog(factor, item));
    }

    const footer = make('div', 'note-footer');
    const star = make('button', 'pestel-star', '★ Prioritario'); star.type = 'button'; star.dataset.star = item.id;
    star.addEventListener('click', () => {
      if (!item.priority && this.priorityCount() >= MAX_PRIORITY) return;
      item.priority = !item.priority;
      card.classList.toggle('is-priority', item.priority);
      this.autosave();
    });
    footer.append(star);
    if (item.source.trim()) {
      const source = make('span', 'note-meta pestel-note-source', 'Con fuente'); source.title = `Fuente: ${item.source.trim()}`;
      footer.append(source);
    }

    const confirmation = make('div', 'note-delete-confirm'); confirmation.hidden = true;
    const yes = make('button', 'note-text-button', 'Quitar'); yes.type = 'button';
    const no = make('button', 'note-text-button', 'Cancelar'); no.type = 'button';
    no.addEventListener('click', () => { confirmation.hidden = true; remove.focus(); });
    remove.addEventListener('click', () => { confirmation.hidden = false; no.focus(); });
    yes.addEventListener('click', () => this.remove(factor, item.id));
    confirmation.append(make('p', '', '¿Quitar este post-it?'), yes, no);

    card.append(top, body, footer, confirmation);
    return card;
  }

  private renderSuggestion(factor: Factor) {
    const slot = document.getElementById(`pestel-${factor.id}-suggestion`);
    if (!slot) return;
    const fact = this.chatFacts[factor.id];
    const text = typeof fact === 'string' ? fact.trim() : '';
    const taken = this.draft[factor.id].some(item => same(item.text, text));
    const full = this.draft[factor.id].length >= MAX_ITEMS;
    if (!text || taken || full || this.role === 'viewer' || this.usedFacts.has(`${factor.id}:${text}`)) {
      slot.hidden = true; slot.replaceChildren(); return;
    }
    const add = make('button', 'pestel-suggestion-add', 'Pasarlo a un post-it'); add.type = 'button';
    add.addEventListener('click', () => this.openDialog(factor, undefined, text));
    slot.replaceChildren(make('p', '', `Lo dijiste en el chat: «${text}»`), add); slot.hidden = false;
  }

  /** Abre la hoja de post-it para una nota nueva, una existente o un dato que vino del chat. */
  private openDialog(factor: Factor, item?: Item, fact = '') {
    if (this.role === 'viewer' || this.loading) return;
    if (!item && this.draft[factor.id].length >= MAX_ITEMS) return;
    this.editing = { factor, item: item || null, fact };
    const dialog = byId<HTMLDialogElement>('pestel-dialog');
    byId('pestel-dialog-title').textContent = `${item ? 'Editar post-it' : 'Nuevo post-it'} · ${factor.name}`;
    byId('pestel-dialog-question').textContent = factor.hint;
    byId('pestel-dialog-factor').textContent = `Factor ${factor.name}`;
    const text = byId<HTMLTextAreaElement>('pestel-dialog-text');
    text.value = item?.text || fact.slice(0, 240); text.placeholder = factor.example; text.removeAttribute('aria-invalid');
    const kind = item?.kind || '';
    dialog.querySelectorAll<HTMLInputElement>('input[name="pestel-kind"]').forEach(radio => { radio.checked = radio.value === kind; });
    byId<HTMLInputElement>('pestel-dialog-source').value = item?.source || (fact ? 'Conversación con Hilo' : '');
    const priority = byId<HTMLInputElement>('pestel-dialog-priority');
    const blocked = !item?.priority && this.priorityCount() >= MAX_PRIORITY;
    priority.checked = !!item?.priority; priority.disabled = blocked;
    byId('pestel-dialog-priority-hint').textContent = blocked
      ? 'Ya elegiste 5, el máximo. Quita la estrella de otro post-it para marcar este.'
      : 'La ficha pide elegir entre 3 y 5 en total.';
    byId('pestel-dialog-error').hidden = true;
    this.paintDialog();
    dialog.showModal();
    text.focus(); text.setSelectionRange(text.value.length, text.value.length);
  }

  /** La hoja toma el color del papel según la marca elegida, igual que el post-it. */
  private paintDialog() {
    const dialog = byId<HTMLDialogElement>('pestel-dialog');
    const kind = (dialog.querySelector<HTMLInputElement>('input[name="pestel-kind"]:checked')?.value || '') as Kind;
    dialog.dataset.noteColor = KIND_COLOR[kind];
  }

  private applyDialog() {
    if (!this.editing) return;
    const { factor, item, fact } = this.editing;
    const dialog = byId<HTMLDialogElement>('pestel-dialog');
    const field = byId<HTMLTextAreaElement>('pestel-dialog-text');
    const text = field.value.trim();
    if (!text) {
      const error = byId('pestel-dialog-error');
      error.textContent = 'Escribe algo en el post-it antes de guardarlo.'; error.hidden = false;
      field.setAttribute('aria-invalid', 'true'); field.focus();
      return;
    }
    const values = {
      text,
      kind: (dialog.querySelector<HTMLInputElement>('input[name="pestel-kind"]:checked')?.value || '') as Kind,
      source: byId<HTMLInputElement>('pestel-dialog-source').value.trim(),
      priority: byId<HTMLInputElement>('pestel-dialog-priority').checked,
    };
    let id = item?.id;
    if (item) Object.assign(item, values);
    else { id = itemId(); this.draft[factor.id].push({ id, ...values }); }
    if (fact) this.usedFacts.add(`${factor.id}:${fact}`);
    dialog.close();
    this.renderItems(factor); this.renderSuggestion(factor);
    this.autosave();
    byId(`pestel-${factor.id}-items`).querySelector<HTMLElement>(`[data-item="${id}"] .note-action`)?.focus();
  }

  private remove(factor: Factor, id: string) {
    if (this.role === 'viewer') return;
    this.draft[factor.id] = this.draft[factor.id].filter(item => item.id !== id);
    this.renderItems(factor); this.renderSuggestion(factor);
    this.autosave();
    byId(`pestel-${factor.id}-add`).focus();
  }

  /** Lleva el factor al chat. Antes guarda, para que Hilo lea lo que ya está anotado. */
  private async ask(factor: Factor) {
    if (this.loading) return;
    if (this.isDirty() && this.role !== 'viewer') { await this.save(); if (this.isDirty()) return; }
    this.links.ask(`Quiero seguir con el PESTEL: factor ${factor.name}.`);
  }

  private steps(): { label: string; detail: string; done: boolean }[] {
    const items = this.allItems();
    const filled = FACTORS.filter(factor => this.draft[factor.id].length).length;
    const marked = items.filter(item => item.kind).length;
    const priority = this.priorityCount();
    return [
      { label: 'Define el reto', detail: this.draft.challenge.trim() ? 'Listo' : 'Falta escribirlo', done: !!this.draft.challenge.trim() },
      { label: 'Identifica elementos', detail: `${filled} de 6 factores`, done: filled === FACTORS.length },
      { label: 'Marca oportunidad o amenaza', detail: items.length ? `${marked} de ${items.length}` : 'Aún no hay post-its', done: items.length > 0 && marked === items.length },
      { label: 'Prioriza de 3 a 5', detail: `${priority} elegido${priority === 1 ? '' : 's'}`, done: priority >= MIN_PRIORITY && priority <= MAX_PRIORITY },
    ];
  }

  private renderSteps() {
    byId('pestel-steps').replaceChildren(...this.steps().map((step, index) => {
      const row = make('li', `pestel-step${step.done ? ' is-done' : ''}`);
      const number = make('span', 'pestel-step-number', step.done ? '✓' : `0${index + 1}`); number.setAttribute('aria-hidden', 'true');
      const body = make('span', 'pestel-step-body');
      body.append(make('strong', '', step.label), make('small', '', step.detail));
      row.append(number, body);
      return row;
    }));
  }

  private renderPriority() {
    const panel = byId('pestel-priority');
    const chosen = FACTORS.flatMap(factor => this.draft[factor.id].filter(item => item.priority).map(item => ({ factor, item })));
    const title = make('h3', '', 'Lo más relevante para tu reto'); title.id = 'pestel-priority-title';
    const help = make('p', 'pestel-priority-help', !chosen.length
      ? 'Marca con ★ los 3 a 5 post-its que más pesan. Aparecerán aquí.'
      : chosen.length < MIN_PRIORITY ? `Llevas ${chosen.length}. La ficha pide entre 3 y 5.`
        : chosen.length === MAX_PRIORITY ? 'Ya elegiste 5, el máximo. Quita uno para cambiarlo.'
          : `Elegiste ${chosen.length}. Puedes llegar hasta 5.`);
    const list = make('ol', 'pestel-priority-list');
    chosen.forEach(({ factor, item }, index) => {
      const row = make('li', 'pestel-priority-item'); row.dataset.kind = item.kind; row.dataset.factor = factor.id;
      const badge = make('span', 'pestel-priority-number', `0${index + 1}`); badge.setAttribute('aria-hidden', 'true');
      const body = make('span', 'pestel-priority-body');
      body.append(make('span', 'pestel-priority-factor', factor.name), make('span', 'pestel-priority-text', item.text));
      row.append(badge, body, make('span', 'pestel-priority-kind', KIND_LABEL[item.kind]));
      list.append(row);
    });
    panel.replaceChildren(title, help, ...(chosen.length ? [list] : []));
  }

  private updateState() {
    const dirty = this.isDirty();
    const needsChallenge = dirty && !this.draft.challenge.trim();
    byId('pestel-save-state').textContent = this.loading ? 'Cargando…'
      : this.saving ? 'Guardando…'
        : this.role === 'viewer' ? 'Solo lectura'
          : needsChallenge ? 'Escribe el reto para guardar'
            : dirty ? 'Cambios sin guardar'
              : this.draft.version ? 'Guardado' : 'PESTEL nuevo';
    byId('pestel-view').classList.toggle('is-busy', this.saving);
    byId<HTMLButtonElement>('pestel-save').disabled = this.loading || this.saving || this.role === 'viewer' || !dirty;
    const atLimit = this.priorityCount() >= MAX_PRIORITY;
    for (const factor of FACTORS) {
      const total = this.draft[factor.id].length;
      const count = document.getElementById(`pestel-${factor.id}-count`);
      if (count) count.textContent = total ? `${total}` : '';
      const add = document.getElementById(`pestel-${factor.id}-add`) as HTMLButtonElement | null;
      if (add) {
        add.hidden = this.role === 'viewer';
        add.disabled = this.loading || total >= MAX_ITEMS;
        add.title = total >= MAX_ITEMS ? `Este factor ya tiene ${MAX_ITEMS} post-its, el máximo` : '';
      }
      for (const item of this.draft[factor.id]) {
        const star = document.querySelector<HTMLButtonElement>(`#pestel-grid [data-star="${item.id}"]`);
        if (!star) continue;
        star.setAttribute('aria-pressed', String(item.priority));
        star.disabled = this.role === 'viewer' || (!item.priority && atLimit);
        star.title = item.priority ? 'Quitar de los prioritarios'
          : atLimit ? 'Ya elegiste 5. Quita uno para elegir otro.' : 'Marcar como uno de los más relevantes';
      }
    }
    this.renderSteps(); this.renderPriority();
  }

  private showError(message: string) { const error = byId('pestel-error'); error.textContent = message; error.hidden = !message; }

  /** Cada post-it se guarda al cerrarlo, como en el tablero. Sin reto no hay qué guardar:
   *  es el primer paso de la ficha y el servidor lo exige. */
  private autosave() {
    this.updateState();
    if (this.role === 'viewer' || !this.isDirty() || !this.draft.challenge.trim()) return;
    if (this.saving) { this.pendingSave = true; return; }
    void this.save();
  }

  private async save() {
    if (this.saving || this.loading || this.role === 'viewer' || !this.isDirty()) return;
    if (!this.draft.challenge.trim()) { this.showError('Escribe el reto antes de guardar: es el primer paso de la ficha.'); byId<HTMLTextAreaElement>('pestel-challenge').focus(); return; }
    this.saving = true; this.showError(''); this.updateState();
    try {
      const snapshot = structuredClone(contentOf(this.draft));
      const stored = await this.request<Pestel>(`/projects/${encodeURIComponent(this.projectId)}/pestel`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...snapshot, version: this.draft.version }),
      });
      this.draft.version = stored.version; this.draft.updated_at = stored.updated_at;
      this.saved = JSON.stringify(snapshot);
    } catch (error) { this.pendingSave = false; this.showError((error as Error).message); }
    finally {
      this.saving = false; this.updateState();
      // Si se movió algo mientras se guardaba, se guarda otra vez con la versión nueva.
      if (this.pendingSave) { this.pendingSave = false; this.autosave(); }
    }
  }
}
