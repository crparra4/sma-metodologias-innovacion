import './pestel.css';
import './empatia.css';

// Mapa de empatía del proyecto, en su forma tradicional: la persona en el centro y los seis
// bloques de la ficha (`knowledge/tools/mapa_empatia.md`) alrededor. Usa los mismos post-its
// y la misma hoja emergente que el PESTEL y el tablero de Post-its, y las clases de caja,
// pasos y cinta de `pestel.css`.
// Cada nota se marca como observada o supuesta: llenar el mapa con suposiciones es la falla
// más común del método, y la ficha pide anotar «lo que sabes/observas».

type Basis = '' | 'observado' | 'supuesto';
type Item = { id: string; text: string; basis: Basis; source: string };
type BlockId = 'piensa_siente' | 've' | 'oye' | 'dice_hace' | 'dolores' | 'necesidades';
type Content = { user: string } & Record<BlockId, Item[]>;
type EmpathyMap = Content & { version: number; updated_at: number | null };
type Role = 'owner' | 'editor' | 'viewer';
type Request = <T>(path: string, options?: RequestInit) => Promise<T>;
type Links = { ask: (text: string) => void };
// `facts`: campos con los que el agente guarda datos de ese bloque desde el chat.
type Block = { id: BlockId; number: string; name: string; hint: string; example: string; facts: string[] };

// Nombre y pista de cada bloque, con las palabras de la ficha y en su orden.
const BLOCKS: Block[] = [
  { id: 'piensa_siente', number: '1', name: '¿Qué piensa y siente?', hint: 'Sus preocupaciones y aspiraciones.', example: 'Ej. Le da miedo equivocarse y perder plata', facts: ['piensa_siente'] },
  { id: 've', number: '2', name: '¿Qué ve?', hint: 'Su entorno, lo que le rodea.', example: 'Ej. Sus nietos pagan todo desde el celular', facts: ['ve'] },
  { id: 'oye', number: '3', name: '¿Qué oye?', hint: 'Lo que dicen amigos, jefe, influencias.', example: 'Ej. «Eso por internet es para que lo roben»', facts: ['oye'] },
  { id: 'dice_hace', number: '4', name: '¿Qué dice y hace?', hint: 'Su comportamiento y su discurso.', example: 'Ej. Prefiere hacer fila en la oficina', facts: ['dice_hace'] },
  { id: 'dolores', number: '5', name: 'Dolores', hint: 'Frustraciones, miedos, obstáculos.', example: 'Ej. La letra de la aplicación es muy pequeña', facts: ['esfuerzos_1', 'esfuerzos_2', 'esfuerzos_3'] },
  { id: 'necesidades', number: '6', name: 'Necesidades', hint: 'Deseos, metas, qué considera éxito.', example: 'Ej. Pagar un recibo sin pedir ayuda', facts: ['resultados_1', 'resultados_2', 'resultados_3'] },
];
const MAX_ITEMS = 8;
// Mismos colores de papel que los post-its del tablero.
const BASIS_COLOR: Record<Basis, string> = { '': 'yellow', observado: 'green', supuesto: 'orange' };
const BASIS_LABEL: Record<Basis, string> = { '': 'Sin marcar', observado: 'Observado', supuesto: 'Supuesto' };
const ICON = (name: string) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;

const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = '') => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
const itemId = () => globalThis.crypto?.randomUUID?.() || `e${Date.now()}${Math.random().toString(36).slice(2)}`;
const emptyMap = (): EmpathyMap => ({ user: '', piensa_siente: [], ve: [], oye: [], dice_hace: [], dolores: [], necesidades: [], version: 0, updated_at: null });
const contentOf = (map: EmpathyMap): Content => ({
  user: map.user, piensa_siente: map.piensa_siente, ve: map.ve, oye: map.oye,
  dice_hace: map.dice_hace, dolores: map.dolores, necesidades: map.necesidades,
});
const same = (a: string, b: string) => a.trim().toLocaleLowerCase('es') === b.trim().toLocaleLowerCase('es');

export class EmpathyController {
  private projectId = '';
  private role: Role = 'viewer';
  private draft: EmpathyMap = emptyMap();
  private saved = JSON.stringify(contentOf(emptyMap()));
  private saving = false;
  private pendingSave = false;
  private loading = false;
  private loadToken = 0;
  private chatFacts: Record<string, unknown> = {};
  private usedFacts = new Set<string>();
  private editing: { block: Block; item: Item | null; fact: string } | null = null;

  constructor(private request: Request, private links: Links) {
    byId('empathy-save').addEventListener('click', () => { void this.save(); });
    const user = byId<HTMLTextAreaElement>('empathy-user');
    user.addEventListener('input', () => { this.draft.user = user.value; this.updateState(); });
    user.addEventListener('change', () => this.autosave());
    const dialog = byId<HTMLDialogElement>('empathy-dialog');
    byId('empathy-dialog-cancel').addEventListener('click', () => dialog.close());
    byId<HTMLFormElement>('empathy-form').addEventListener('submit', event => { event.preventDefault(); this.applyDialog(); });
    dialog.querySelectorAll<HTMLInputElement>('input[name="empathy-basis"]').forEach(radio => radio.addEventListener('change', () => this.paintDialog()));
    dialog.addEventListener('close', () => { this.editing = null; });
    window.addEventListener('beforeunload', event => {
      if (byId('empathy-view').hidden || !this.isDirty()) return;
      event.preventDefault();
    });
  }

  isDirty() { return JSON.stringify(contentOf(this.draft)) !== this.saved; }
  canLeave() { return !this.isDirty() || window.confirm('Hay cambios sin guardar en el mapa de empatía. ¿Quieres salir y descartarlos?'); }

  /** Datos que la persona dio en el chat y Hilo verificó; se ofrecen, no se insertan solos. */
  setChatFacts(facts: Record<string, unknown> = {}) {
    this.chatFacts = facts;
    if (!this.projectId) return;
    for (const block of BLOCKS) this.renderSuggestion(block);
  }

  async open(projectId: string, role: Role, chatFacts: Record<string, unknown> = {}) {
    this.projectId = projectId; this.role = role; this.chatFacts = chatFacts;
    this.usedFacts.clear();
    this.draft = emptyMap(); this.saved = JSON.stringify(contentOf(this.draft)); this.render();
    await this.load();
  }

  private async load() {
    const token = ++this.loadToken;
    this.loading = true; this.showError(''); this.updateState();
    try {
      const map = await this.request<EmpathyMap>(`/projects/${encodeURIComponent(this.projectId)}/empathy-map`);
      if (token !== this.loadToken) return;
      this.draft = structuredClone(map);
      this.saved = JSON.stringify(contentOf(this.draft));
      this.render();
    } catch (error) { if (token === this.loadToken) this.showError((error as Error).message); }
    finally { if (token === this.loadToken) { this.loading = false; this.updateState(); } }
  }

  private render() {
    const user = byId<HTMLTextAreaElement>('empathy-user');
    user.value = this.draft.user; user.readOnly = this.role === 'viewer';
    // La persona va en el centro; dolores y necesidades, abajo, como en el mapa de siempre.
    const person = make('div', 'empathy-person'); person.id = 'empathy-person';
    const face = make('span', 'empathy-person-face', '🙂'); face.setAttribute('aria-hidden', 'true');
    const name = make('p', 'empathy-person-name'); name.id = 'empathy-person-name';
    person.append(face, name);
    const bottom = make('div', 'empathy-bottom');
    bottom.append(this.blockPanel(BLOCKS[4]), this.blockPanel(BLOCKS[5]));
    byId('empathy-map').replaceChildren(
      this.blockPanel(BLOCKS[0]), this.blockPanel(BLOCKS[1]), person, this.blockPanel(BLOCKS[2]), this.blockPanel(BLOCKS[3]), bottom,
    );
    for (const block of BLOCKS) { this.renderItems(block); this.renderSuggestion(block); }
    this.updateState();
  }

  private blockPanel(block: Block): HTMLElement {
    const panel = make('section', 'empathy-block'); panel.dataset.block = block.id;
    panel.setAttribute('aria-labelledby', `empathy-${block.id}-title`);
    const head = make('header', 'empathy-block-head');
    const number = make('span', 'empathy-block-number', `0${block.number}`); number.setAttribute('aria-hidden', 'true');
    const title = make('h3', '', block.name); title.id = `empathy-${block.id}-title`;
    head.append(number, title);
    const count = make('span', 'pestel-count'); count.id = `empathy-${block.id}-count`; count.setAttribute('role', 'status');
    // Mismo muro que el tablero de Post-its: las notas heredan su aspecto.
    const list = make('div', 'notes-wall pestel-wall empathy-wall'); list.id = `empathy-${block.id}-items`;
    const suggestion = make('div', 'pestel-suggestion'); suggestion.id = `empathy-${block.id}-suggestion`; suggestion.hidden = true;
    const actions = make('div', 'empathy-block-actions');
    const add = make('button', 'pestel-add'); add.type = 'button'; add.id = `empathy-${block.id}-add`;
    const plus = make('span', 'pestel-add-plus', '+'); plus.setAttribute('aria-hidden', 'true');
    add.append(plus, make('span', '', 'Nuevo post-it'));
    add.setAttribute('aria-label', `Nuevo post-it en el bloque ${block.name}`);
    add.addEventListener('click', () => this.openDialog(block));
    const ask = make('button', 'empathy-ask', 'Preguntarle a Hilo'); ask.type = 'button';
    ask.title = 'Sigue este bloque en el chat, con una pregunta a la vez';
    ask.addEventListener('click', () => { void this.ask(block); });
    actions.append(add, ask);
    panel.append(head, count, make('p', 'empathy-block-hint', block.hint), list, suggestion, actions);
    return panel;
  }

  private renderItems(block: Block) {
    byId(`empathy-${block.id}-items`).replaceChildren(...this.draft[block.id].map((item, index) => this.noteCard(block, item, index)));
  }

  /** Un post-it como los del tablero: arriba dice si es observado o supuesto. */
  private noteCard(block: Block, item: Item, index: number): HTMLElement {
    const readOnly = this.role === 'viewer';
    const card = make('article', 'sticky-note pestel-note'); card.dataset.item = item.id; card.dataset.noteColor = BASIS_COLOR[item.basis];
    const name = `post-it ${index + 1} del bloque ${block.name}`;

    const top = make('div', 'note-top');
    const label = make('span', 'note-label'); label.append(make('span', 'note-category', BASIS_LABEL[item.basis]));
    const actions = make('div', 'note-actions');
    const edit = make('button', 'note-action'); edit.type = 'button'; edit.innerHTML = ICON('edit'); edit.setAttribute('aria-label', `Editar ${name}`);
    edit.addEventListener('click', () => this.openDialog(block, item));
    const remove = make('button', 'note-action'); remove.type = 'button'; remove.innerHTML = ICON('trash'); remove.setAttribute('aria-label', `Quitar ${name}`);
    if (!readOnly) actions.append(edit, remove);
    top.append(label, actions);

    const body = make('p', 'note-body', item.text);
    if (!readOnly) {
      body.classList.add('is-editable'); body.title = 'Editar este post-it';
      body.addEventListener('click', () => this.openDialog(block, item));
    }
    const footer = make('div', 'note-footer');
    if (item.source.trim()) {
      const source = make('span', 'note-meta pestel-note-source', 'Con fuente'); source.title = `Fuente: ${item.source.trim()}`;
      footer.append(source);
    }

    const confirmation = make('div', 'note-delete-confirm'); confirmation.hidden = true;
    const yes = make('button', 'note-text-button', 'Quitar'); yes.type = 'button';
    const no = make('button', 'note-text-button', 'Cancelar'); no.type = 'button';
    no.addEventListener('click', () => { confirmation.hidden = true; remove.focus(); });
    remove.addEventListener('click', () => { confirmation.hidden = false; no.focus(); });
    yes.addEventListener('click', () => this.remove(block, item.id));
    confirmation.append(make('p', '', '¿Quitar este post-it?'), yes, no);

    card.append(top, body, footer, confirmation);
    return card;
  }

  private renderSuggestion(block: Block) {
    const slot = document.getElementById(`empathy-${block.id}-suggestion`);
    if (!slot) return;
    const full = this.draft[block.id].length >= MAX_ITEMS;
    const text = block.facts
      .map(key => this.chatFacts[key]).map(fact => typeof fact === 'string' ? fact.trim() : '')
      .find(fact => fact && !this.draft[block.id].some(item => same(item.text, fact)) && !this.usedFacts.has(`${block.id}:${fact}`)) || '';
    if (!text || full || this.role === 'viewer') { slot.hidden = true; slot.replaceChildren(); return; }
    const add = make('button', 'pestel-suggestion-add', 'Pasarlo a un post-it'); add.type = 'button';
    add.addEventListener('click', () => this.openDialog(block, undefined, text));
    slot.replaceChildren(make('p', '', `Lo dijiste en el chat: «${text}»`), add); slot.hidden = false;
  }

  /** Abre la hoja de post-it para una nota nueva, una existente o un dato que vino del chat. */
  private openDialog(block: Block, item?: Item, fact = '') {
    if (this.role === 'viewer' || this.loading) return;
    if (!item && this.draft[block.id].length >= MAX_ITEMS) return;
    this.editing = { block, item: item || null, fact };
    const dialog = byId<HTMLDialogElement>('empathy-dialog');
    byId('empathy-dialog-title').textContent = `${item ? 'Editar post-it' : 'Nuevo post-it'} · Mapa de empatía`;
    byId('empathy-dialog-question').textContent = block.name.startsWith('¿') ? block.name : `${block.name}: ${block.hint.toLocaleLowerCase('es')}`;
    byId('empathy-dialog-block').textContent = `Bloque ${block.number} de 6`;
    const text = byId<HTMLTextAreaElement>('empathy-dialog-text');
    text.value = item?.text || fact.slice(0, 240); text.placeholder = block.example; text.removeAttribute('aria-invalid');
    // Lo que la persona le contó a Hilo en el chat ya es algo que sabe: entra como observado.
    const basis = item ? item.basis : fact ? 'observado' : '';
    dialog.querySelectorAll<HTMLInputElement>('input[name="empathy-basis"]').forEach(radio => { radio.checked = radio.value === basis; });
    byId<HTMLInputElement>('empathy-dialog-source').value = item?.source || (fact ? 'Conversación con Hilo' : '');
    byId('empathy-dialog-error').hidden = true;
    this.paintDialog();
    dialog.showModal();
    text.focus(); text.setSelectionRange(text.value.length, text.value.length);
  }

  /** La hoja toma el color del papel según la marca elegida, igual que el post-it. */
  private paintDialog() {
    const dialog = byId<HTMLDialogElement>('empathy-dialog');
    const basis = (dialog.querySelector<HTMLInputElement>('input[name="empathy-basis"]:checked')?.value || '') as Basis;
    dialog.dataset.noteColor = BASIS_COLOR[basis];
  }

  private applyDialog() {
    if (!this.editing) return;
    const { block, item, fact } = this.editing;
    const dialog = byId<HTMLDialogElement>('empathy-dialog');
    const field = byId<HTMLTextAreaElement>('empathy-dialog-text');
    const text = field.value.trim();
    if (!text) {
      const error = byId('empathy-dialog-error');
      error.textContent = 'Escribe algo en el post-it antes de guardarlo.'; error.hidden = false;
      field.setAttribute('aria-invalid', 'true'); field.focus();
      return;
    }
    const values = {
      text,
      basis: (dialog.querySelector<HTMLInputElement>('input[name="empathy-basis"]:checked')?.value || '') as Basis,
      source: byId<HTMLInputElement>('empathy-dialog-source').value.trim(),
    };
    let id = item?.id;
    if (item) Object.assign(item, values);
    else { id = itemId(); this.draft[block.id].push({ id, ...values }); }
    if (fact) this.usedFacts.add(`${block.id}:${fact}`);
    dialog.close();
    this.renderItems(block); this.renderSuggestion(block);
    this.autosave();
    byId(`empathy-${block.id}-items`).querySelector<HTMLElement>(`[data-item="${id}"] .note-action`)?.focus();
  }

  private remove(block: Block, id: string) {
    if (this.role === 'viewer') return;
    this.draft[block.id] = this.draft[block.id].filter(item => item.id !== id);
    this.renderItems(block); this.renderSuggestion(block);
    this.autosave();
    byId(`empathy-${block.id}-add`).focus();
  }

  /** Lleva el bloque al chat. Antes guarda, para que Hilo lea lo que ya está anotado. */
  private async ask(block: Block) {
    if (this.loading) return;
    if (this.isDirty() && this.role !== 'viewer') { await this.save(); if (this.isDirty()) return; }
    this.links.ask(`Quiero seguir con el mapa de empatía: bloque «${block.name}».`);
  }

  private updateState() {
    const dirty = this.isDirty();
    const needsUser = dirty && !this.draft.user.trim();
    byId('empathy-save-state').textContent = this.loading ? 'Cargando…'
      : this.saving ? 'Guardando…'
        : this.role === 'viewer' ? 'Solo lectura'
          : needsUser ? 'Describe al usuario para guardar'
            : dirty ? 'Cambios sin guardar'
              : this.draft.version ? 'Guardado' : 'Mapa nuevo';
    byId('empathy-view').classList.toggle('is-busy', this.saving);
    byId<HTMLButtonElement>('empathy-save').disabled = this.loading || this.saving || this.role === 'viewer' || !dirty;
    const name = document.getElementById('empathy-person-name');
    if (name) {
      name.textContent = this.draft.user.trim() || 'Tu usuario';
      name.classList.toggle('is-empty', !this.draft.user.trim());
    }
    for (const block of BLOCKS) {
      const total = this.draft[block.id].length;
      const count = document.getElementById(`empathy-${block.id}-count`);
      if (count) count.textContent = total ? `${total}` : '';
      const add = document.getElementById(`empathy-${block.id}-add`) as HTMLButtonElement | null;
      if (add) {
        add.hidden = this.role === 'viewer';
        add.disabled = this.loading || total >= MAX_ITEMS;
        add.title = total >= MAX_ITEMS ? `Este bloque ya tiene ${MAX_ITEMS} post-its, el máximo` : '';
      }
    }
  }

  private showError(message: string) { const error = byId('empathy-error'); error.textContent = message; error.hidden = !message; }

  /** Cada post-it se guarda al cerrarlo. Sin usuario no hay qué guardar: es el primer paso
   *  de la ficha y el servidor lo exige. */
  private autosave() {
    this.updateState();
    if (this.role === 'viewer' || !this.isDirty() || !this.draft.user.trim()) return;
    if (this.saving) { this.pendingSave = true; return; }
    void this.save();
  }

  private async save() {
    if (this.saving || this.loading || this.role === 'viewer' || !this.isDirty()) return;
    if (!this.draft.user.trim()) { this.showError('Describe al usuario antes de guardar: es el primer paso de la ficha.'); byId<HTMLTextAreaElement>('empathy-user').focus(); return; }
    this.saving = true; this.showError(''); this.updateState();
    try {
      const snapshot = structuredClone(contentOf(this.draft));
      const stored = await this.request<EmpathyMap>(`/projects/${encodeURIComponent(this.projectId)}/empathy-map`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...snapshot, version: this.draft.version }),
      });
      this.draft.version = stored.version; this.draft.updated_at = stored.updated_at;
      this.saved = JSON.stringify(snapshot);
    } catch (error) { this.pendingSave = false; this.showError((error as Error).message); }
    finally {
      this.saving = false; this.updateState();
      if (this.pendingSave) { this.pendingSave = false; this.autosave(); }
    }
  }
}
