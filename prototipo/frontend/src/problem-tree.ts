import './problem-tree.css';

type TreeNode = { id: string; text: string; source: string; parent: string };
type Lane = 'causes' | 'effects';
type Tree = { problem: string; problem_source: string; causes: TreeNode[]; effects: TreeNode[]; version: number; updated_at: number | null };
type Request = <T>(path: string, options?: RequestInit) => Promise<T>;

const MAX_NODES = 30;
const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const emptyTree = (): Tree => ({ problem: '', problem_source: '', causes: [], effects: [], version: 0, updated_at: null });
const contentOf = (tree: Tree) => ({ problem: tree.problem, problem_source: tree.problem_source, causes: tree.causes, effects: tree.effects });
const nodeId = () => globalThis.crypto?.randomUUID?.() || `n${Date.now()}${Math.random().toString(36).slice(2)}`;
const normalize = (nodes: TreeNode[] = []): TreeNode[] => nodes.map(node => ({ ...node, parent: node.parent || '' }));
const addButtonId = (lane: Lane) => `problem-tree-add-${lane === 'causes' ? 'cause' : 'effect'}`;

type Finding = { code: string; layer: 'regla' | 'contenido'; severity: 'alta' | 'media' | 'baja'; target: string; message: string };
type Diagnosis = { version: number; findings: Finding[]; model_status: 'ok' | 'ocupado' | 'no_disponible'; discarded: number; elapsed_ms: number };
const FINDING_LABELS: Record<string, string> = {
  problema_como_solucion: 'Describe una solución', falta_de_solucion: 'Nombra lo que falta',
  sin_fuente: 'Sin fuente', sin_causa_de_fondo: 'Sin causa de fondo',
  carril_vacio: 'Vacío', repetida: 'Repetida', muy_breve: 'Muy breve',
};
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export class ProblemTreeController {
  private projectId = '';
  private projectName = '';
  private role: 'owner' | 'editor' | 'viewer' = 'viewer';
  private draft: Tree = emptyTree();
  private saved = JSON.stringify(contentOf(emptyTree()));
  private saving = false;
  private loading = false;
  private loadToken = 0;
  private diagnosis: Diagnosis | null = null;
  private diagnosing = false;

  constructor(private request: Request) {
    byId('problem-tree-save').addEventListener('click', () => { void this.save(); });
    byId('problem-tree-diagnose').addEventListener('click', () => { void this.diagnose(); });
    byId('problem-tree-add-cause').addEventListener('click', () => this.add('causes'));
    byId('problem-tree-add-effect').addEventListener('click', () => this.add('effects'));
    byId<HTMLTextAreaElement>('problem-tree-problem').addEventListener('input', event => {
      this.draft.problem = (event.target as HTMLTextAreaElement).value;
      this.updateState();
    });
    byId<HTMLInputElement>('problem-tree-problem-source').addEventListener('input', event => {
      this.draft.problem_source = (event.target as HTMLInputElement).value;
      this.updateState();
    });
    for (const lane of ['causes', 'effects'] as const) {
      const list = byId(`problem-tree-${lane}`);
      list.addEventListener('dragover', event => { event.preventDefault(); list.classList.add('drop-target'); });
      list.addEventListener('dragleave', event => { if (!list.contains(event.relatedTarget as Node)) list.classList.remove('drop-target'); });
      list.addEventListener('drop', event => {
        event.preventDefault(); list.classList.remove('drop-target');
        const id = event.dataTransfer?.getData('text/plain');
        if (id) this.moveTo(id, lane, (event.target as HTMLElement).closest<HTMLElement>('[data-tree-node]')?.dataset.treeNode);
      });
    }
    window.addEventListener('beforeunload', event => {
      if (byId('problem-tree-view').hidden || !this.isDirty()) return;
      event.preventDefault();
    });
  }

  isDirty() { return JSON.stringify(contentOf(this.draft)) !== this.saved; }
  canLeave() { return !this.isDirty() || window.confirm('Hay cambios sin guardar en el árbol. ¿Quieres salir y descartarlos?'); }

  private locked() { return this.role === 'viewer' || this.saving; }
  private childrenOf(lane: Lane, id: string) { return this.draft[lane].filter(node => node.parent === id); }

  private rootsOf(lane: Lane) {
    const ids = new Set(this.draft[lane].map(node => node.id));
    return this.draft[lane].filter(node => !node.parent || !ids.has(node.parent));
  }

  private laneOf(id: string): Lane | undefined {
    return this.draft.causes.some(node => node.id === id) ? 'causes'
      : this.draft.effects.some(node => node.id === id) ? 'effects' : undefined;
  }

  async open(projectId: string, role: 'owner' | 'editor' | 'viewer', projectQuestion = '', projectName = '') {
    this.projectId = projectId;
    this.projectName = projectName;
    this.role = role;
    this.diagnosis = null;
    this.draft = emptyTree(); this.saved = JSON.stringify(contentOf(this.draft)); this.render();
    await this.load(projectQuestion);
  }

  private async load(projectQuestion = '') {
    if (!this.projectId) return;
    const token = ++this.loadToken;
    this.loading = true; this.showError(''); this.updateState();
    try {
      const tree = await this.request<Tree>(`/projects/${encodeURIComponent(this.projectId)}/problem-tree`);
      if (token !== this.loadToken) return;
      const clean: Tree = { ...structuredClone(tree), causes: normalize(tree.causes), effects: normalize(tree.effects) };
      this.draft = clean;
      this.saved = JSON.stringify(contentOf(clean));
      if (!clean.problem && !clean.causes.length && !clean.effects.length && projectQuestion.trim()) {
        this.draft.problem = projectQuestion.trim();
        byId('problem-tree-subtitle').textContent = 'Copiamos el reto como borrador. Ajústalo hasta expresar una situación concreta.';
      } else {
        byId('problem-tree-subtitle').textContent = 'Conecta lo que ocurre con sus posibles causas y consecuencias.';
      }
      this.render();
    } catch (error) { if (token === this.loadToken) this.showError((error as Error).message); }
    finally { if (token === this.loadToken) { this.loading = false; this.updateState(); } }
  }

  private add(lane: Lane) {
    if (this.locked() || this.draft[lane].length >= MAX_NODES) return;
    const id = nodeId();
    this.draft[lane].push({ id, text: '', source: '', parent: '' });
    this.render();
    byId(`problem-tree-${lane}`).querySelector<HTMLTextAreaElement>(`[data-tree-node="${id}"] textarea`)?.focus();
  }

  /** Anida la tarjeta bajo la raíz anterior de su carril: pasa a ser una causa de fondo. */
  private nest(lane: Lane, id: string) {
    if (this.locked()) return;
    const roots = this.rootsOf(lane);
    const position = roots.findIndex(node => node.id === id);
    if (position < 1 || this.childrenOf(lane, id).length) return;
    const node = this.draft[lane].find(item => item.id === id);
    const parent = roots[position - 1];
    if (!node || !parent) return;
    node.parent = parent.id;
    this.draft[lane] = this.draft[lane].filter(item => item.id !== id);
    const siblings = this.draft[lane].map(item => item.parent === parent.id);
    const lastSibling = siblings.lastIndexOf(true);
    const anchor = lastSibling >= 0 ? lastSibling : this.draft[lane].findIndex(item => item.id === parent.id);
    this.draft[lane].splice(anchor + 1, 0, node);
    this.render();
    this.focusNode(lane, id, '.tree-unnest');
  }

  private unnest(lane: Lane, id: string) {
    if (this.locked()) return;
    const node = this.draft[lane].find(item => item.id === id);
    if (!node || !node.parent) return;
    node.parent = '';
    this.render();
    this.focusNode(lane, id, '.tree-nest');
  }

  private moveTo(id: string, lane: Lane, beforeId?: string) {
    if (this.locked() || beforeId === id) return;
    const from = this.laneOf(id);
    if (!from) return;
    const node = this.draft[from].find(item => item.id === id);
    if (!node) return;
    const kids = this.childrenOf(from, id);
    if (from !== lane && this.draft[lane].length + 1 + kids.length > MAX_NODES) return;
    const moving = [node, ...kids];
    this.draft[from] = this.draft[from].filter(item => !moving.includes(item));
    const target = beforeId ? this.draft[lane].find(item => item.id === beforeId) : undefined;
    // Una tarjeta con otras debajo no puede colgar de nadie: el árbol admite dos niveles.
    node.parent = target && !kids.length ? target.parent : '';
    const destination = target ? this.draft[lane].indexOf(target) : -1;
    this.draft[lane].splice(destination < 0 ? this.draft[lane].length : destination, 0, ...moving);
    this.render();
  }

  private reorder(lane: Lane, id: string, delta: number) {
    if (this.locked()) return;
    const nodes = this.draft[lane];
    const node = nodes.find(item => item.id === id);
    if (!node) return;
    const siblings = node.parent ? this.childrenOf(lane, node.parent) : this.rootsOf(lane);
    const target = siblings[siblings.findIndex(item => item.id === id) + delta];
    if (!target) return;
    const origin = nodes.indexOf(node), destination = nodes.indexOf(target);
    [nodes[origin], nodes[destination]] = [nodes[destination], nodes[origin]];
    this.render();
    this.focusNode(lane, id, `.tree-move-${delta < 0 ? 'up' : 'down'}`);
  }

  /** Al quitar una raíz, sus tarjetas de fondo suben de nivel en lugar de perderse. */
  private remove(lane: Lane, id: string) {
    if (this.locked()) return;
    for (const child of this.childrenOf(lane, id)) child.parent = '';
    this.draft[lane] = this.draft[lane].filter(item => item.id !== id);
    this.render();
    byId(addButtonId(lane)).focus();
  }

  private focusNode(lane: Lane, id: string, selector: string) {
    byId(`problem-tree-${lane}`).querySelector<HTMLElement>(`[data-tree-node="${id}"] ${selector}`)?.focus();
  }

  private render() {
    const readOnly = this.locked();
    const problem = byId<HTMLTextAreaElement>('problem-tree-problem');
    problem.value = this.draft.problem; problem.readOnly = readOnly;
    const source = byId<HTMLInputElement>('problem-tree-problem-source');
    source.value = this.draft.problem_source; source.readOnly = readOnly;
    for (const lane of ['causes', 'effects'] as const) {
      const list = byId(`problem-tree-${lane}`);
      list.replaceChildren();
      if (!this.draft[lane].length) {
        const empty = document.createElement('p'); empty.className = 'problem-tree-empty';
        empty.textContent = lane === 'causes'
          ? 'Todavía no hay causas. Empieza con una posible explicación.'
          : 'Todavía no hay efectos. Anota una consecuencia observable.';
        list.append(empty);
      }
      const roots = this.rootsOf(lane);
      roots.forEach((root, index) => {
        const branch = document.createElement('div'); branch.className = 'problem-tree-branch';
        branch.append(this.card(root, lane, `${index + 1}`, roots, index));
        const kids = this.childrenOf(lane, root.id);
        if (kids.length) {
          const nested = document.createElement('div'); nested.className = 'problem-tree-children';
          kids.forEach((kid, position) => nested.append(this.card(kid, lane, `${index + 1}.${position + 1}`, kids, position)));
          branch.append(nested);
        }
        list.append(branch);
      });
    }
    this.renderDiagnosis();
    this.updateState();
  }

  private card(node: TreeNode, lane: Lane, numbering: string, siblings: TreeNode[], index: number): HTMLElement {
    const nested = !!node.parent;
    const noun = lane === 'causes' ? 'causa' : 'efecto';
    const Noun = lane === 'causes' ? 'Causa' : 'Efecto';
    const card = document.createElement('article');
    card.className = `problem-tree-card${nested ? ' is-child' : ''}`;
    card.dataset.treeNode = node.id; card.draggable = !this.locked();
    card.addEventListener('dragstart', event => { event.dataTransfer?.setData('text/plain', node.id); card.classList.add('dragging'); });
    card.addEventListener('dragend', () => card.classList.remove('dragging'));
    const head = document.createElement('div'); head.className = 'problem-tree-card-head';
    const label = document.createElement('span');
    label.textContent = nested ? `${Noun} de fondo ${numbering}` : `${Noun} ${numbering}`;
    const badge = document.createElement('span'); badge.className = `problem-tree-evidence ${node.source.trim() ? 'has-source' : ''}`;
    badge.textContent = node.source.trim() ? 'Fuente registrada' : 'Por contrastar';
    head.append(label, badge);
    const textLabel = document.createElement('label'); textLabel.className = 'sr-only'; textLabel.htmlFor = `tree-text-${node.id}`;
    textLabel.textContent = `Texto de ${noun} ${numbering}`;
    const text = document.createElement('textarea'); text.id = textLabel.htmlFor; text.rows = 2; text.maxLength = 240;
    text.placeholder = nested ? '¿Y por qué ocurre eso?' : lane === 'causes' ? '¿Por qué ocurre?' : '¿Qué consecuencia produce?';
    text.value = node.text; text.readOnly = this.locked();
    text.addEventListener('input', () => { node.text = text.value; this.updateState(); });
    const sourceLabel = document.createElement('label'); sourceLabel.htmlFor = `tree-source-${node.id}`;
    sourceLabel.textContent = 'Origen de esta relación';
    const source = document.createElement('input'); source.id = sourceLabel.htmlFor; source.maxLength = 500;
    source.placeholder = 'Ej. Entrevista, observación o documento'; source.value = node.source; source.readOnly = this.locked();
    source.addEventListener('input', () => {
      node.source = source.value;
      badge.textContent = node.source.trim() ? 'Fuente registrada' : 'Por contrastar';
      badge.classList.toggle('has-source', !!node.source.trim());
      this.updateState();
    });
    // La observación va junto al texto al que se refiere: evita la atención dividida.
    card.append(head, textLabel, text, ...this.notesFor(node.id), sourceLabel, source);
    if (this.role !== 'viewer') card.append(this.actions(node, lane, noun, nested, siblings, index));
    return card;
  }

  private actions(node: TreeNode, lane: Lane, noun: string, nested: boolean, siblings: TreeNode[], index: number): HTMLElement {
    const actions = document.createElement('div'); actions.className = 'problem-tree-card-actions';
    const hasKids = this.childrenOf(lane, node.id).length > 0;
    const buttons: [string, string, () => void, boolean, string][] = [
      ['Subir', 'tree-move-up', () => this.reorder(lane, node.id, -1), index === 0, `Mueve esta ${noun} antes de la anterior`],
      ['Bajar', 'tree-move-down', () => this.reorder(lane, node.id, 1), index === siblings.length - 1, `Mueve esta ${noun} después de la siguiente`],
    ];
    if (nested) {
      buttons.push(['Subir de nivel', 'tree-unnest', () => this.unnest(lane, node.id), false,
        `Deja de depender de otra ${noun}`]);
    } else {
      buttons.push(['Anidar', 'tree-nest', () => this.nest(lane, node.id), index === 0 || hasKids,
        hasKids ? 'El árbol admite dos niveles: esta tarjeta ya tiene otras debajo'
          : index === 0 ? `No hay una ${noun} anterior de la que pueda depender`
            : `Convierte esta tarjeta en ${noun} de fondo de la anterior`]);
    }
    buttons.push(
      [lane === 'causes' ? 'Pasar a efecto' : 'Pasar a causa', 'tree-change-lane',
        () => this.moveTo(node.id, lane === 'causes' ? 'effects' : 'causes'), false,
        'Mueve la tarjeta al otro lado del árbol'],
      ['Quitar', 'tree-remove', () => this.remove(lane, node.id), false,
        hasKids ? 'Quita esta tarjeta; las de fondo suben de nivel' : 'Quita esta tarjeta'],
    );
    for (const [caption, className, callback, disabled, hint] of buttons) {
      const button = document.createElement('button'); button.type = 'button'; button.className = className;
      button.textContent = caption; button.disabled = disabled || this.saving; button.title = hint;
      button.addEventListener('click', callback); actions.append(button);
    }
    return actions;
  }

  private counter(lane: Lane): HTMLElement {
    const id = `problem-tree-count-${lane}`;
    const existing = document.getElementById(id);
    if (existing) return existing;
    const span = document.createElement('span'); span.id = id; span.className = 'problem-tree-count';
    span.setAttribute('role', 'status');
    byId(addButtonId(lane)).insertAdjacentElement('beforebegin', span);
    return span;
  }

  private updateState() {
    const dirty = this.isDirty();
    const status = byId('problem-tree-save-state');
    status.textContent = this.loading ? 'Cargando…'
      : this.saving ? 'Guardando…'
        : this.role === 'viewer' ? 'Solo lectura'
          : dirty ? 'Cambios sin guardar'
            : this.draft.version ? 'Guardado' : 'Árbol nuevo';
    byId('problem-tree-view').classList.toggle('is-busy', this.saving);
    byId('problem-tree-view').classList.toggle('diagnosis-stale', this.isStale());
    const diagnose = byId<HTMLButtonElement>('problem-tree-diagnose');
    diagnose.disabled = this.loading || this.saving || this.diagnosing || dirty || !this.draft.version;
    diagnose.textContent = this.diagnosing ? 'Diagnosticando…' : 'Diagnosticar';
    diagnose.title = dirty ? 'Guarda el árbol antes de diagnosticarlo'
      : !this.draft.version ? 'Guarda el árbol para poder diagnosticarlo'
        : 'Revisa la estructura y el contenido del árbol';
    byId<HTMLButtonElement>('problem-tree-save').disabled = this.loading || this.saving || this.role === 'viewer' || !dirty;
    for (const lane of ['causes', 'effects'] as const) {
      const total = this.draft[lane].length;
      byId<HTMLButtonElement>(addButtonId(lane)).disabled = this.loading || this.locked() || total >= MAX_NODES;
      const counter = this.counter(lane);
      counter.textContent = total >= MAX_NODES ? `${total} de ${MAX_NODES} · límite alcanzado` : `${total} de ${MAX_NODES}`;
      counter.classList.toggle('at-limit', total >= MAX_NODES);
    }
  }

  private isStale() {
    return !!this.diagnosis && (this.isDirty() || this.diagnosis.version !== this.draft.version);
  }

  private notesFor(target: string): HTMLElement[] {
    return (this.diagnosis?.findings || []).filter(item => item.target === target).map(item => {
      const note = document.createElement('div');
      note.className = `problem-tree-finding sev-${item.severity}`;
      const label = document.createElement('span'); label.className = 'finding-label';
      label.textContent = FINDING_LABELS[item.code] || item.code;
      const text = document.createElement('p'); text.textContent = item.message;
      note.append(label, text);
      return note;
    });
  }

  private slot(id: string, anchor: HTMLElement, where: InsertPosition, className: string): HTMLElement {
    let node = document.getElementById(id);
    if (!node) {
      node = document.createElement('div'); node.id = id; node.className = className;
      anchor.insertAdjacentElement(where, node);
    }
    return node;
  }

  private statusText(diagnosis: Diagnosis) {
    if (diagnosis.model_status === 'ocupado') return 'Hilo está respondiendo en el chat; por ahora solo se aplicaron las reglas.';
    if (diagnosis.model_status === 'no_disponible') return 'El modelo local no respondió; por ahora solo se aplicaron las reglas.';
    const seconds = Math.max(1, Math.round(diagnosis.elapsed_ms / 1000));
    const dropped = diagnosis.discarded ? ' Descartó una observación que no citaba el árbol.' : '';
    return `Hilo revisó el problema central en ${seconds} s.${dropped}`;
  }

  private renderDiagnosis() {
    this.slot('problem-tree-problem-findings', byId('problem-tree-problem'), 'afterend', 'problem-tree-target-findings')
      .replaceChildren(...this.notesFor('problem'));
    for (const lane of ['causes', 'effects'] as const) {
      this.slot(`problem-tree-lane-findings-${lane}`, byId(`problem-tree-${lane}`), 'beforebegin', 'problem-tree-lane-findings')
        .replaceChildren(...this.notesFor(lane));
    }
    const panel = byId('problem-tree-diagnosis');
    panel.hidden = !this.diagnosis;
    if (!this.diagnosis) { panel.replaceChildren(); return; }
    const diagnosis = this.diagnosis;
    const total = diagnosis.findings.length;
    const title = document.createElement('h3');
    const heading = document.createElement('span');
    heading.textContent = total ? `Diagnóstico · ${plural(total, 'observación', 'observaciones')}` : 'Diagnóstico · sin observaciones';
    const close = document.createElement('button'); close.type = 'button'; close.className = 'diagnosis-close'; close.textContent = 'Ocultar';
    close.addEventListener('click', () => { this.diagnosis = null; this.render(); });
    title.append(heading, close);
    const stale = document.createElement('p'); stale.className = 'diagnosis-stale-note';
    stale.textContent = 'El árbol cambió desde este diagnóstico. Guarda y vuelve a diagnosticar.';
    const parts: HTMLElement[] = [title, stale];
    const general = diagnosis.findings.filter(item => item.target === 'tree');
    if (general.length) {
      const list = document.createElement('ul');
      for (const item of general) { const li = document.createElement('li'); li.textContent = item.message; list.append(li); }
      parts.push(list);
    }
    const placed = total - general.length;
    const summary = document.createElement('p'); summary.className = 'diagnosis-status';
    summary.textContent = [
      placed ? `${plural(placed, 'observación está', 'observaciones están')} junto a lo que señalan: en el tronco, en un carril o en su tarjeta.` : '',
      !total && diagnosis.model_status === 'ok' ? 'El árbol cumple los criterios revisados.' : '',
      this.statusText(diagnosis),
    ].filter(Boolean).join(' ');
    parts.push(summary);
    panel.replaceChildren(...parts);
  }

  private async diagnose() {
    if (this.diagnosing || this.loading || this.saving || this.isDirty() || !this.draft.version) return;
    this.diagnosing = true; this.showError(''); this.updateState();
    try {
      this.diagnosis = await this.request<Diagnosis>(
        `/projects/${encodeURIComponent(this.projectId)}/problem-tree/diagnosis`, { method: 'POST' },
      );
      this.render();
    } catch (error) { this.showError((error as Error).message); }
    finally { this.diagnosing = false; this.updateState(); }
  }

  private showError(message: string) { const error = byId('problem-tree-error'); error.textContent = message; error.hidden = !message; }

  private async save() {
    if (this.saving || this.loading || this.role === 'viewer' || !this.isDirty()) return;
    const blanks = [...this.draft.causes, ...this.draft.effects].filter(node => !node.text.trim());
    if (blanks.length) { this.showError('Completa el texto de cada tarjeta o quita las que estén vacías.'); return; }
    if (!this.draft.problem.trim()) { this.showError('Escribe el problema central antes de guardar.'); byId<HTMLTextAreaElement>('problem-tree-problem').focus(); return; }
    this.saving = true; this.showError(''); this.render();
    try {
      const snapshot = structuredClone(contentOf(this.draft));
      const tree = await this.request<Tree>(`/projects/${encodeURIComponent(this.projectId)}/problem-tree`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...snapshot, version: this.draft.version }),
      });
      this.draft.version = tree.version; this.draft.updated_at = tree.updated_at;
      this.saved = JSON.stringify(snapshot);
      this.showError('');
    } catch (error) { this.showError((error as Error).message); }
    finally { this.saving = false; this.render(); }
  }
}
