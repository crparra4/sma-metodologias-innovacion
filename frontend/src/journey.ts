import './pestel.css';
import './journey.css';

// Customer Journey Map del proyecto (`knowledge/tools/customer_journey.md`): la persona y el
// escenario a la izquierda y, a la derecha, las etapas del recorrido como columnas en orden.
// Cada etapa tiene lo que pide la ficha: lo que hace, puntos de contacto, emoción, dolores y
// oportunidades de mejora. Las emociones se unen con una línea para ver dónde cae la
// experiencia, y una etapa se puede marcar como crítica.
// Usa los post-its y la hoja emergente del tablero. El agente no llena nada. Ayuda de dos
// maneras: «Preguntarle a Hilo» lleva una etapa al chat y lo que la persona responda allí se
// ofrece como post-it; y «Pegar notas de entrevista» le pide frases de esas notas, que el
// servidor solo devuelve si están literales en el texto. En los dos casos la persona acepta
// cada post-it.

type Note = { id: string; text: string };
type LaneId = 'acciones' | 'contacto' | 'dolores' | 'oportunidades';
type Stage = { id: string; name: string; emotion: number; critical: boolean } & Record<LaneId, Note[]>;
type Content = { user: string; scenario: string; stages: Stage[] };
type Journey = Content & { version: number; updated_at: number | null };
type Role = 'owner' | 'editor' | 'viewer';
type Request = <T>(path: string, options?: RequestInit) => Promise<T>;
type Links = { ask: (text: string) => void };
type Lane = { id: LaneId; name: string; mark: string; question: string; example: string; color: string };
type Proposal = { quote: string; stage_id: string; lane: LaneId; lane_name: string };
type Extraction = { proposals: Proposal[]; model_status: 'ok' | 'ocupado' | 'no_disponible'; discarded: number; elapsed_ms: number };

// Filas de cada etapa, con las palabras de la ficha. El color del papel es el de la fila.
const LANES: Lane[] = [
  { id: 'acciones', name: 'Lo que hace', mark: '👣', question: '¿Qué hace la persona en esta etapa?', example: 'Ej. Marca al número de la EPS', color: 'yellow' },
  { id: 'contacto', name: 'Puntos de contacto', mark: '🤝', question: '¿Con qué o con quién tiene contacto en esta etapa?', example: 'Ej. La línea telefónica de citas', color: 'blue' },
  { id: 'dolores', name: 'Dolores', mark: '⚡', question: '¿Qué le molesta, le cuesta o le preocupa en esta etapa?', example: 'Ej. Espera veinte minutos en la línea', color: 'pink' },
  { id: 'oportunidades', name: 'Oportunidades', mark: '💡', question: '¿Qué se podría mejorar en esta etapa?', example: 'Ej. Devolverle la llamada en vez de dejarlo esperando', color: 'green' },
];
const FACES: { level: number; face: string; label: string }[] = [
  { level: 5, face: '😀', label: 'Muy bien' }, { level: 4, face: '🙂', label: 'Bien' }, { level: 3, face: '😐', label: 'Neutral' },
  { level: 2, face: '🙁', label: 'Mal' }, { level: 1, face: '😣', label: 'Muy mal' },
];
const MAX_STAGES = 8;
const MAX_NOTES = 6;
const MAX_PASTE = 1800;
const ICON = (name: string) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const ASK = 'Quiero seguir con el customer journey';

const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = '') => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
const newId = () => globalThis.crypto?.randomUUID?.() || `j${Date.now()}${Math.random().toString(36).slice(2)}`;
const emptyJourney = (): Journey => ({ user: '', scenario: '', stages: [], version: 0, updated_at: null });
const contentOf = (journey: Journey): Content => ({ user: journey.user, scenario: journey.scenario, stages: journey.stages });
const faceOf = (level: number) => FACES.find(item => item.level === level);

export class JourneyController {
  private projectId = '';
  private role: Role = 'viewer';
  private draft: Journey = emptyJourney();
  private saved = JSON.stringify(contentOf(emptyJourney()));
  private saving = false;
  private pendingSave = false;
  private loading = false;
  private loadToken = 0;
  private editing: { stage: Stage; note: Note | null; lane: LaneId; said: boolean } | null = null;
  // Etapa que se llevó al chat y lo último que la persona respondió allí sobre ella.
  private reading = false;
  private askedStage = '';
  private said: Record<string, { text: string; lane: LaneId }> = {};

  constructor(private request: Request, private links: Links) {
    byId('journey-save').addEventListener('click', () => { void this.save(); });
    for (const field of ['user', 'scenario'] as const) {
      const input = byId<HTMLTextAreaElement>(`journey-${field}`);
      input.addEventListener('input', () => { this.draft[field] = input.value; this.updateState(); });
      input.addEventListener('change', () => this.autosave());
    }
    byId('journey-ask').addEventListener('click', () => { void this.ask(); });
    const dialog = byId<HTMLDialogElement>('journey-dialog');
    byId('journey-dialog-cancel').addEventListener('click', () => dialog.close());
    byId<HTMLFormElement>('journey-form').addEventListener('submit', event => { event.preventDefault(); this.applyDialog(); });
    dialog.querySelectorAll<HTMLInputElement>('input[name="journey-lane"]').forEach(radio => radio.addEventListener('change', () => this.paintDialog()));
    dialog.addEventListener('close', () => { this.editing = null; });
    const notes = byId<HTMLDialogElement>('journey-notes-dialog');
    byId('journey-paste').addEventListener('click', () => this.openNotes());
    byId('journey-notes-cancel').addEventListener('click', () => { if (!this.reading) notes.close(); });
    notes.addEventListener('cancel', event => { if (this.reading) event.preventDefault(); });
    byId('journey-notes-again').addEventListener('click', () => this.showNotesInput(true));
    byId<HTMLFormElement>('journey-notes-form').addEventListener('submit', event => { event.preventDefault(); void this.readNotes(); });
    byId<HTMLTextAreaElement>('journey-notes-text').addEventListener('input', () => this.countNotes());
    // La línea de emociones depende de dónde quedó cada cara: se redibuja al cambiar el ancho.
    new ResizeObserver(() => this.drawCurve()).observe(byId('journey-board'));
    document.addEventListener('click', event => {
      if (!(event.target as HTMLElement).closest('.journey-emotion')) this.closeFaces();
    });
    window.addEventListener('beforeunload', event => {
      if (byId('journey-view').hidden || !this.isDirty()) return;
      event.preventDefault();
    });
  }

  isDirty() { return JSON.stringify(contentOf(this.draft)) !== this.saved; }
  canLeave() { return !this.isDirty() || window.confirm('Hay cambios sin guardar en el recorrido. ¿Quieres salir y descartarlos?'); }

  /** Lo que la persona escribe en el chat después de llevar una etapa allí se le ofrece como
   *  post-it de esa etapa. Nada entra al mapa sin que ella lo acepte. */
  noteChatMessage(text: string) {
    const stage = this.draft.stages.find(item => item.id === this.askedStage);
    const clean = text.trim();
    if (!stage || clean.startsWith(ASK) || clean.includes('?') || clean.split(/\s+/).length < 3) return;
    this.said[stage.id] = { text: clean.slice(0, 240), lane: this.askedLane(stage) };
    this.renderSaid(stage);
  }

  /** Fila por la que Hilo acaba de preguntar, según su último mensaje; si no se reconoce,
   *  la primera fila vacía de la etapa. En la hoja se puede cambiar. */
  private askedLane(stage: Stage): LaneId {
    const turns = document.querySelectorAll('#messages .assistant-turn');
    const question = (turns[turns.length - 1]?.textContent || '').toLocaleLowerCase('es');
    if (/dolor|molest|frustr|preocup|dificult|le cuesta/.test(question)) return 'dolores';
    if (/contacto|canal|medio|con qui[eé]n/.test(question)) return 'contacto';
    if (/oportunidad|mejor/.test(question)) return 'oportunidades';
    if (/qu[eé] hace|acci[oó]n|acciones/.test(question)) return 'acciones';
    return LANES.find(item => !stage[item.id].length)?.id || 'acciones';
  }

  async open(projectId: string, role: Role) {
    this.projectId = projectId; this.role = role;
    this.askedStage = ''; this.said = {};
    this.draft = emptyJourney(); this.saved = JSON.stringify(contentOf(this.draft)); this.render();
    await this.load();
  }

  private readOnly() { return this.role === 'viewer'; }

  private async load() {
    const token = ++this.loadToken;
    this.loading = true; this.showError(''); this.updateState();
    try {
      const journey = await this.request<Journey>(`/projects/${encodeURIComponent(this.projectId)}/journey`);
      if (token !== this.loadToken) return;
      this.draft = structuredClone(journey);
      this.saved = JSON.stringify(contentOf(this.draft));
      this.render();
    } catch (error) { if (token === this.loadToken) this.showError((error as Error).message); }
    finally { if (token === this.loadToken) { this.loading = false; this.updateState(); } }
  }

  private render() {
    for (const field of ['user', 'scenario'] as const) {
      const input = byId<HTMLTextAreaElement>(`journey-${field}`);
      input.value = this.draft[field]; input.readOnly = this.readOnly();
    }
    const board = byId('journey-board');
    // Etiquetas, una columna por etapa y el botón de agregar; sin etapas, el botón y la ayuda.
    const count = this.draft.stages.length;
    board.style.setProperty('--columnas', count ? `150px repeat(${count},minmax(178px,1fr)) 92px` : '150px 92px minmax(220px,1fr)');
    const labels = make('div', 'journey-labels');
    labels.append(make('span', 'journey-label is-head', 'Etapas'));
    const emotion = make('span', 'journey-label'); emotion.append(this.mark('💗'), make('span', '', 'Cómo se siente'));
    labels.append(emotion);
    for (const lane of LANES) {
      const label = make('span', 'journey-label'); label.dataset.lane = lane.id;
      label.append(this.mark(lane.mark), make('span', '', lane.name));
      labels.append(label);
    }
    labels.append(make('span', 'journey-label is-foot'));
    const curve = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    curve.setAttribute('class', 'journey-curve'); curve.setAttribute('aria-hidden', 'true'); curve.id = 'journey-curve';
    const add = make('button', 'journey-add-stage'); add.type = 'button'; add.id = 'journey-add-stage';
    const plus = make('span', 'pestel-add-plus', '+'); plus.setAttribute('aria-hidden', 'true');
    add.append(plus, make('span', '', 'Nueva etapa'));
    add.addEventListener('click', () => this.addStage());
    const empty = make('p', 'journey-empty', this.readOnly()
      ? 'Este recorrido todavía no tiene etapas.'
      : 'Empieza por la primera etapa: ¿qué es lo primero que hace la persona? Luego agrega las siguientes en orden.');
    empty.hidden = this.draft.stages.length > 0;
    board.replaceChildren(labels, ...this.draft.stages.map((stage, index) => this.stageColumn(stage, index)), add, empty, curve as unknown as HTMLElement);
    this.updateState();
    requestAnimationFrame(() => this.drawCurve());
  }

  private mark(text: string) { const mark = make('span', 'journey-label-mark', text); mark.setAttribute('aria-hidden', 'true'); return mark; }

  private stageColumn(stage: Stage, index: number): HTMLElement {
    const readOnly = this.readOnly();
    const column = make('section', 'journey-stage'); column.dataset.stage = stage.id;
    column.classList.toggle('is-critical', stage.critical);
    column.setAttribute('aria-label', `Etapa ${index + 1}: ${stage.name}`);

    const head = make('header', 'journey-stage-head');
    head.append(make('span', 'journey-stage-number', `Etapa ${index + 1}`));
    const name = make('input', 'journey-stage-name'); name.value = stage.name; name.maxLength = 60; name.readOnly = readOnly;
    name.placeholder = 'Nombre de la etapa'; name.setAttribute('aria-label', `Nombre de la etapa ${index + 1}`);
    name.addEventListener('input', () => { stage.name = name.value; this.updateState(); });
    name.addEventListener('change', () => this.autosave());
    head.append(name);
    const critical = make('button', 'journey-critical', 'Etapa crítica'); critical.type = 'button';
    critical.setAttribute('aria-pressed', String(stage.critical)); critical.disabled = readOnly;
    critical.title = 'Marca las etapas donde más importa mejorar la experiencia';
    critical.addEventListener('click', () => {
      stage.critical = !stage.critical;
      critical.setAttribute('aria-pressed', String(stage.critical)); column.classList.toggle('is-critical', stage.critical);
      this.autosave();
    });
    head.append(critical);
    if (!readOnly) {
      const tools = make('div', 'journey-stage-tools');
      const total = this.draft.stages.length;
      const buttons: [string, string, () => void, boolean][] = [
        ['‹', 'Mover esta etapa antes', () => this.moveStage(stage.id, -1), index === 0],
        ['›', 'Mover esta etapa después', () => this.moveStage(stage.id, 1), index === total - 1],
      ];
      for (const [caption, label, action, disabled] of buttons) {
        const button = make('button', 'journey-tool', caption); button.type = 'button'; button.disabled = disabled;
        button.setAttribute('aria-label', `${label}: ${stage.name}`); button.title = label;
        button.addEventListener('click', action); tools.append(button);
      }
      const remove = make('button', 'journey-tool'); remove.type = 'button'; remove.innerHTML = ICON('trash');
      remove.setAttribute('aria-label', `Quitar la etapa ${stage.name}`); remove.title = 'Quitar esta etapa';
      remove.addEventListener('click', () => {
        const notes = LANES.reduce((sum, lane) => sum + stage[lane.id].length, 0);
        if (notes && !window.confirm(`¿Quitar la etapa «${stage.name}» con sus ${notes} post-its?`)) return;
        this.draft.stages = this.draft.stages.filter(item => item.id !== stage.id);
        this.render(); this.autosave();
      });
      tools.append(remove); head.append(tools);
    }
    column.append(head, this.emotionCell(stage, index));

    for (const lane of LANES) {
      const cell = make('div', 'journey-cell'); cell.dataset.lane = lane.id; cell.dataset.label = lane.name;
      const wall = make('div', 'notes-wall journey-wall'); wall.id = `journey-${stage.id}-${lane.id}`;
      const add = make('button', 'journey-add', '+'); add.type = 'button'; add.dataset.add = `${stage.id}:${lane.id}`;
      add.setAttribute('aria-label', `Nuevo post-it en ${lane.name}, etapa ${stage.name}`); add.title = lane.question;
      add.hidden = readOnly;
      add.addEventListener('click', () => this.openDialog(stage, lane.id));
      cell.append(wall, add); column.append(cell);
    }

    const foot = make('footer', 'journey-stage-foot');
    const said = make('div', 'pestel-suggestion journey-said'); said.id = `journey-${stage.id}-said`; said.hidden = true;
    const ask = make('button', 'journey-ask', 'Preguntarle a Hilo'); ask.type = 'button';
    ask.title = 'Sigue esta etapa en el chat, con una pregunta a la vez';
    ask.addEventListener('click', () => { void this.ask(stage); });
    foot.append(said, ask); column.append(foot);
    queueMicrotask(() => { for (const lane of LANES) this.renderNotes(stage, lane.id); this.renderSaid(stage); });
    return column;
  }

  /** Una cara por etapa; su altura en la celda es el nivel, para que la línea suba y baje. */
  private emotionCell(stage: Stage, index: number): HTMLElement {
    const cell = make('div', 'journey-emotion');
    const current = faceOf(stage.emotion);
    const face = make('button', 'journey-face', current ? current.face : '+'); face.type = 'button'; face.dataset.face = stage.id;
    face.style.setProperty('--nivel', String(stage.emotion || 3)); face.classList.toggle('is-empty', !current);
    face.setAttribute('aria-label', `Emoción en la etapa ${index + 1}: ${current ? current.label : 'sin marcar'}`);
    face.setAttribute('aria-haspopup', 'true'); face.setAttribute('aria-expanded', 'false'); face.disabled = this.readOnly();
    face.title = current ? current.label : '¿Cómo se siente la persona en esta etapa?';
    const options = make('div', 'journey-faces'); options.hidden = true; options.setAttribute('role', 'group');
    options.setAttribute('aria-label', '¿Cómo se siente la persona en esta etapa?');
    const choose = (level: number) => {
      stage.emotion = level; this.closeFaces();
      const next = this.emotionCell(stage, index); cell.replaceWith(next);
      this.autosave(); this.drawCurve();
      next.querySelector<HTMLButtonElement>('.journey-face')?.focus();
    };
    for (const item of FACES) {
      const option = make('button', '', item.face); option.type = 'button'; option.title = item.label;
      option.setAttribute('aria-label', item.label); option.setAttribute('aria-pressed', String(stage.emotion === item.level));
      option.addEventListener('click', () => choose(item.level)); options.append(option);
    }
    if (current) {
      const clear = make('button', 'journey-faces-clear', 'Quitar'); clear.type = 'button';
      clear.addEventListener('click', () => choose(0)); options.append(clear);
    }
    face.addEventListener('click', () => {
      const open = options.hidden; this.closeFaces();
      options.hidden = !open; face.setAttribute('aria-expanded', String(open));
    });
    cell.addEventListener('keydown', event => { if (event.key === 'Escape') { this.closeFaces(); face.focus(); } });
    cell.append(face, options);
    return cell;
  }

  private closeFaces() {
    document.querySelectorAll<HTMLElement>('#journey-board .journey-faces').forEach(node => { node.hidden = true; });
    document.querySelectorAll('#journey-board .journey-face').forEach(node => node.setAttribute('aria-expanded', 'false'));
  }

  /** Línea punteada entre las caras de etapas seguidas que ya tienen emoción. */
  private drawCurve() {
    const svg = document.getElementById('journey-curve');
    const board = byId('journey-board');
    if (!svg) return;
    const frame = board.getBoundingClientRect();
    svg.setAttribute('viewBox', `0 0 ${board.scrollWidth} ${board.scrollHeight}`);
    svg.setAttribute('width', String(board.scrollWidth)); svg.setAttribute('height', String(board.scrollHeight));
    const points = this.draft.stages.map(stage => {
      const face = board.querySelector<HTMLElement>(`[data-face="${stage.id}"]`);
      if (!face || !stage.emotion) return null;
      const box = face.getBoundingClientRect();
      return { x: box.left - frame.left + board.scrollLeft + box.width / 2, y: box.top - frame.top + board.scrollTop + box.height / 2 };
    });
    let path = '';
    points.forEach((point, index) => {
      if (!point) return;
      path += `${index && points[index - 1] ? 'L' : 'M'}${point.x.toFixed(1)} ${point.y.toFixed(1)} `;
    });
    svg.innerHTML = path ? `<path d="${path}"/>` : '';
  }

  private renderNotes(stage: Stage, laneId: LaneId) {
    const wall = document.getElementById(`journey-${stage.id}-${laneId}`);
    if (!wall) return;
    const lane = LANES.find(item => item.id === laneId)!;
    wall.replaceChildren(...stage[laneId].map((note, index) => this.noteCard(stage, lane, note, index)));
    this.drawCurve();
  }

  /** Un post-it del tablero, en pequeño: la fila ya dice qué es. */
  private noteCard(stage: Stage, lane: Lane, note: Note, index: number): HTMLElement {
    const readOnly = this.readOnly();
    const card = make('article', 'sticky-note journey-note'); card.dataset.item = note.id; card.dataset.noteColor = lane.color;
    const name = `post-it ${index + 1} de ${lane.name}, etapa ${stage.name}`;
    const top = make('div', 'note-top');
    const actions = make('div', 'note-actions');
    const edit = make('button', 'note-action'); edit.type = 'button'; edit.innerHTML = ICON('edit'); edit.setAttribute('aria-label', `Editar ${name}`);
    edit.addEventListener('click', () => this.openDialog(stage, lane.id, note));
    const remove = make('button', 'note-action'); remove.type = 'button'; remove.innerHTML = ICON('trash'); remove.setAttribute('aria-label', `Quitar ${name}`);
    if (!readOnly) actions.append(edit, remove);
    top.append(actions);
    const body = make('p', 'note-body', note.text);
    if (!readOnly) {
      body.classList.add('is-editable'); body.title = 'Editar este post-it';
      body.addEventListener('click', () => this.openDialog(stage, lane.id, note));
    }
    const confirmation = make('div', 'note-delete-confirm'); confirmation.hidden = true;
    const yes = make('button', 'note-text-button', 'Quitar'); yes.type = 'button';
    const no = make('button', 'note-text-button', 'Cancelar'); no.type = 'button';
    no.addEventListener('click', () => { confirmation.hidden = true; remove.focus(); });
    remove.addEventListener('click', () => { confirmation.hidden = false; no.focus(); });
    yes.addEventListener('click', () => {
      stage[lane.id] = stage[lane.id].filter(item => item.id !== note.id);
      this.renderNotes(stage, lane.id); this.autosave();
      document.querySelector<HTMLElement>(`[data-add="${stage.id}:${lane.id}"]`)?.focus();
    });
    confirmation.append(make('p', '', '¿Quitar?'), yes, no);
    card.append(top, body, confirmation);
    return card;
  }

  private renderSaid(stage: Stage) {
    const slot = document.getElementById(`journey-${stage.id}-said`);
    if (!slot) return;
    const said = this.said[stage.id];
    if (!said || this.readOnly()) { slot.hidden = true; slot.replaceChildren(); return; }
    const text = said.text;
    const add = make('button', 'pestel-suggestion-add', 'Pasarlo a un post-it'); add.type = 'button';
    add.addEventListener('click', () => this.openDialog(stage, said.lane, undefined, text));
    const skip = make('button', 'journey-said-skip', 'Descartar'); skip.type = 'button';
    skip.addEventListener('click', () => { delete this.said[stage.id]; this.renderSaid(stage); });
    const actions = make('div', 'journey-said-actions'); actions.append(add, skip);
    slot.replaceChildren(make('p', '', `Lo dijiste en el chat: «${text}»`), actions); slot.hidden = false;
  }

  private addStage() {
    if (this.readOnly() || this.loading || this.draft.stages.length >= MAX_STAGES) return;
    const stage: Stage = { id: newId(), name: `Etapa ${this.draft.stages.length + 1}`, emotion: 0, critical: false, acciones: [], contacto: [], dolores: [], oportunidades: [] };
    this.draft.stages.push(stage);
    this.render(); this.autosave();
    // El nombre queda seleccionado: escribir lo reemplaza.
    const name = byId('journey-board').querySelector<HTMLInputElement>(`[data-stage="${stage.id}"] .journey-stage-name`);
    name?.focus(); name?.select();
    name?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  private moveStage(id: string, delta: number) {
    const stages = this.draft.stages;
    const from = stages.findIndex(item => item.id === id); const to = from + delta;
    if (this.readOnly() || from < 0 || to < 0 || to >= stages.length) return;
    [stages[from], stages[to]] = [stages[to], stages[from]];
    this.render(); this.autosave();
    byId('journey-board').querySelector<HTMLElement>(`[data-stage="${id}"] .journey-tool:not(:disabled)`)?.focus();
  }

  /** Abre la hoja de post-it para una nota nueva, una existente o algo dicho en el chat. */
  private openDialog(stage: Stage, laneId: LaneId, note?: Note, saidText = '') {
    if (this.readOnly() || this.loading) return;
    if (!note && stage[laneId].length >= MAX_NOTES) { this.showError(`Esa fila ya tiene ${MAX_NOTES} post-its, el máximo.`); return; }
    this.editing = { stage, note: note || null, lane: laneId, said: !!saidText };
    const dialog = byId<HTMLDialogElement>('journey-dialog');
    byId('journey-dialog-title').textContent = `${note ? 'Editar post-it' : 'Nuevo post-it'} · Customer Journey`;
    byId('journey-dialog-stage').textContent = `Etapa ${this.draft.stages.indexOf(stage) + 1} · ${stage.name}`;
    const text = byId<HTMLTextAreaElement>('journey-dialog-text');
    text.value = note?.text || saidText; text.removeAttribute('aria-invalid');
    dialog.querySelectorAll<HTMLInputElement>('input[name="journey-lane"]').forEach(radio => { radio.checked = radio.value === laneId; });
    byId('journey-dialog-error').hidden = true;
    this.paintDialog();
    dialog.showModal();
    text.focus(); text.setSelectionRange(text.value.length, text.value.length);
  }

  /** La hoja toma la pregunta y el color de la fila elegida. */
  private paintDialog() {
    const dialog = byId<HTMLDialogElement>('journey-dialog');
    const laneId = dialog.querySelector<HTMLInputElement>('input[name="journey-lane"]:checked')?.value as LaneId;
    const lane = LANES.find(item => item.id === laneId) || LANES[0];
    dialog.dataset.noteColor = lane.color;
    byId('journey-dialog-question').textContent = lane.question;
    byId<HTMLTextAreaElement>('journey-dialog-text').placeholder = lane.example;
  }

  private applyDialog() {
    if (!this.editing) return;
    const { stage, note, lane: from, said } = this.editing;
    const dialog = byId<HTMLDialogElement>('journey-dialog');
    const field = byId<HTMLTextAreaElement>('journey-dialog-text');
    const text = field.value.trim();
    const error = byId('journey-dialog-error');
    if (!text) {
      error.textContent = 'Escribe algo en el post-it antes de guardarlo.'; error.hidden = false;
      field.setAttribute('aria-invalid', 'true'); field.focus();
      return;
    }
    const to = (dialog.querySelector<HTMLInputElement>('input[name="journey-lane"]:checked')?.value || from) as LaneId;
    if ((!note || to !== from) && stage[to].length >= MAX_NOTES) {
      error.textContent = `Esa fila ya tiene ${MAX_NOTES} post-its, el máximo. Elige otra o quita uno.`; error.hidden = false;
      return;
    }
    let id = note?.id;
    if (note) {
      note.text = text;
      if (to !== from) { stage[from] = stage[from].filter(item => item.id !== note.id); stage[to].push(note); this.renderNotes(stage, from); }
    } else { id = newId(); stage[to].push({ id, text }); }
    if (said) { delete this.said[stage.id]; this.renderSaid(stage); }
    dialog.close();
    this.renderNotes(stage, to);
    this.autosave();
    byId('journey-board').querySelector<HTMLElement>(`[data-item="${id}"] .note-action`)?.focus();
  }

  // ---------- Notas de entrevista ----------

  private openNotes() {
    if (this.readOnly() || this.loading || !this.draft.stages.length) return;
    this.showNotesInput(false);
    byId<HTMLDialogElement>('journey-notes-dialog').showModal();
    byId<HTMLTextAreaElement>('journey-notes-text').focus();
  }

  private showNotesInput(clear: boolean) {
    const text = byId<HTMLTextAreaElement>('journey-notes-text');
    if (clear) text.value = '';
    byId('journey-notes-input').hidden = false; byId('journey-notes-results').hidden = true;
    byId('journey-notes-submit').hidden = false; byId('journey-notes-again').hidden = true;
    byId('journey-notes-progress').textContent = ''; byId('journey-notes-error').hidden = true;
    this.countNotes();
    if (clear) text.focus();
  }

  private countNotes() {
    const length = byId<HTMLTextAreaElement>('journey-notes-text').value.length;
    byId('journey-notes-count').textContent = `${length.toLocaleString('es-CO')} de ${MAX_PASTE.toLocaleString('es-CO')}`;
  }

  private notesError(message: string) { const error = byId('journey-notes-error'); error.textContent = message; error.hidden = !message; }

  /** Envía el trozo pegado. El servidor devuelve solo frases literales; aquí se revisan. */
  private async readNotes() {
    if (this.reading) return;
    const field = byId<HTMLTextAreaElement>('journey-notes-text');
    const text = field.value.trim();
    if (text.length < 20) { this.notesError('Pega al menos un par de frases de tus notas.'); field.focus(); return; }
    // El servidor lee el recorrido guardado: las etapas nuevas tienen que estar allá.
    if (this.isDirty()) { await this.save(); if (this.isDirty()) { this.notesError('Guarda el recorrido antes de leer notas.'); return; } }
    const submit = byId<HTMLButtonElement>('journey-notes-submit');
    this.reading = true; this.notesError(''); submit.disabled = true; submit.textContent = 'Hilo está leyendo…';
    byId('journey-notes-progress').textContent = 'Suele tardar unos segundos';
    try {
      const result = await this.request<Extraction>(`/projects/${encodeURIComponent(this.projectId)}/journey/extract`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }),
      });
      if (result.model_status === 'ocupado') this.notesError('Hilo está respondiendo en el chat. Espera a que termine y vuelve a intentarlo.');
      else if (result.model_status === 'no_disponible') this.notesError('El modelo local no respondió. Comprueba que esté iniciado y vuelve a intentarlo.');
      else this.showProposals(result);
    } catch (error) { this.notesError((error as Error).message); }
    finally {
      this.reading = false; submit.disabled = false; submit.textContent = 'Buscar post-its';
      if (byId('journey-notes-results').hidden) byId('journey-notes-progress').textContent = '';
    }
  }

  private showProposals(result: Extraction) {
    const total = result.proposals.length;
    const dropped = result.discarded
      ? ` Descarté ${result.discarded} que no ${result.discarded === 1 ? 'estaba' : 'estaban'} tal cual en tus notas.` : '';
    byId('journey-notes-status').textContent = total
      ? `Encontré ${total} ${total === 1 ? 'frase' : 'frases'} en tus notas. Revisa dónde va cada una y agrega las que sirvan.${dropped}`
      : `No encontré frases para el recorrido en este trozo.${dropped} Prueba con otro.`;
    byId('journey-proposals').replaceChildren(...result.proposals.map(item => this.proposalRow(item)));
    byId('journey-notes-input').hidden = true; byId('journey-notes-results').hidden = false;
    byId('journey-notes-submit').hidden = true; byId('journey-notes-again').hidden = false;
    this.countProposals();
  }

  private countProposals() {
    const rows = [...byId('journey-proposals').children];
    const added = rows.filter(row => row.classList.contains('is-added')).length;
    byId('journey-notes-progress').textContent = rows.length ? `${added} de ${rows.length} agregadas` : '';
  }

  /** Una frase propuesta: se puede cambiar de etapa y de fila antes de agregarla. */
  private proposalRow(item: Proposal): HTMLElement {
    const row = make('li', 'journey-proposal'); row.dataset.noteColor = LANES.find(lane => lane.id === item.lane)?.color || 'yellow';
    const quote = make('blockquote', '', `«${item.quote}»`);
    const stage = make('select'); stage.setAttribute('aria-label', 'Etapa de esta frase');
    this.draft.stages.forEach((option, index) => {
      const choice = make('option', '', `${index + 1}. ${option.name}`); choice.value = option.id; choice.selected = option.id === item.stage_id;
      stage.append(choice);
    });
    const lane = make('select'); lane.setAttribute('aria-label', 'Fila de esta frase');
    for (const option of LANES) {
      const choice = make('option', '', option.name); choice.value = option.id; choice.selected = option.id === item.lane;
      lane.append(choice);
    }
    lane.addEventListener('change', () => { row.dataset.noteColor = LANES.find(option => option.id === lane.value)?.color || 'yellow'; });
    const add = make('button', 'journey-proposal-add', 'Agregar'); add.type = 'button';
    const skip = make('button', 'journey-proposal-skip', 'Descartar'); skip.type = 'button';
    const controls = make('div', 'journey-proposal-controls'); controls.append(stage, lane, add, skip);
    skip.addEventListener('click', () => { row.remove(); this.countProposals(); });
    add.addEventListener('click', () => {
      const target = this.draft.stages.find(option => option.id === stage.value);
      const laneId = lane.value as LaneId;
      if (!target) return;
      if (target[laneId].length >= MAX_NOTES) { this.notesError(`Esa fila de «${target.name}» ya tiene ${MAX_NOTES} post-its, el máximo. Elige otra.`); return; }
      this.notesError('');
      target[laneId].push({ id: newId(), text: item.quote });
      this.renderNotes(target, laneId); this.autosave();
      row.classList.add('is-added');
      controls.replaceChildren(make('span', 'journey-proposal-done', `✓ Agregado a «${target.name}» · ${LANES.find(option => option.id === laneId)!.name}`));
      this.countProposals();
    });
    row.append(quote, controls);
    return row;
  }

  /** Lleva una etapa (o el recorrido entero) al chat. Antes guarda, para que Hilo lea lo
   *  anotado y pregunte por lo que falta. */
  private async ask(stage?: Stage) {
    if (this.loading) return;
    if (this.isDirty() && !this.readOnly()) { await this.save(); if (this.isDirty()) return; }
    this.askedStage = stage?.id || '';
    this.links.ask(stage ? `${ASK}: etapa «${stage.name}».` : `${ASK}.`);
  }

  private blocker(): string {
    if (!this.draft.user.trim()) return 'Describe al usuario para guardar';
    if (this.draft.stages.some(stage => !stage.name.trim())) return 'Ponle nombre a cada etapa para guardar';
    return '';
  }

  private updateState() {
    const dirty = this.isDirty();
    const blocker = dirty ? this.blocker() : '';
    byId('journey-save-state').textContent = this.loading ? 'Cargando…'
      : this.saving ? 'Guardando…'
        : this.readOnly() ? 'Solo lectura'
          : blocker || (dirty ? 'Cambios sin guardar' : this.draft.version ? 'Guardado' : 'Recorrido nuevo');
    byId('journey-view').classList.toggle('is-busy', this.saving);
    byId<HTMLButtonElement>('journey-save').disabled = this.loading || this.saving || this.readOnly() || !dirty;
    const add = document.getElementById('journey-add-stage') as HTMLButtonElement | null;
    if (add) {
      const full = this.draft.stages.length >= MAX_STAGES;
      add.hidden = this.readOnly(); add.disabled = this.loading || full;
      add.title = full ? `El recorrido ya tiene ${MAX_STAGES} etapas, el máximo` : 'Agrega la siguiente etapa del recorrido';
    }
    const paste = byId<HTMLButtonElement>('journey-paste');
    paste.hidden = this.readOnly(); paste.disabled = this.loading || !this.draft.stages.length;
    paste.title = this.draft.stages.length ? 'Hilo busca en tus notas frases para el recorrido' : 'Agrega primero las etapas del recorrido';
    for (const stage of this.draft.stages) for (const lane of LANES) {
      const button = document.querySelector<HTMLButtonElement>(`[data-add="${stage.id}:${lane.id}"]`);
      if (button) button.disabled = this.loading || stage[lane.id].length >= MAX_NOTES;
    }
  }

  private showError(message: string) { const error = byId('journey-error'); error.textContent = message; error.hidden = !message; }

  /** Cada cambio se guarda solo, como en el tablero. Sin usuario no hay qué guardar: es el
   *  primer paso de la ficha y el servidor lo exige. */
  private autosave() {
    this.updateState();
    if (this.readOnly() || !this.isDirty() || this.blocker()) return;
    if (this.saving) { this.pendingSave = true; return; }
    void this.save();
  }

  private async save() {
    if (this.saving || this.loading || this.readOnly() || !this.isDirty()) return;
    const blocker = this.blocker();
    if (blocker) { this.showError(`${blocker}.`); if (!this.draft.user.trim()) byId<HTMLTextAreaElement>('journey-user').focus(); return; }
    this.saving = true; this.showError(''); this.updateState();
    try {
      const snapshot = structuredClone(contentOf(this.draft));
      const stored = await this.request<Journey>(`/projects/${encodeURIComponent(this.projectId)}/journey`, {
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
