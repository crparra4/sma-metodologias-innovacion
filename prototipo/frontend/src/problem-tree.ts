import './problem-tree.css';

type TreeNode = { id: string; text: string; source: string };
type Lane = 'causes' | 'effects';
type Tree = { problem: string; problem_source: string; causes: TreeNode[]; effects: TreeNode[]; version: number; updated_at: number | null };
type Request = <T>(path: string, options?: RequestInit) => Promise<T>;

const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const emptyTree = (): Tree => ({ problem: '', problem_source: '', causes: [], effects: [], version: 0, updated_at: null });
const contentOf = (tree: Tree) => ({ problem: tree.problem, problem_source: tree.problem_source, causes: tree.causes, effects: tree.effects });
const nodeId = () => globalThis.crypto?.randomUUID?.() || `n${Date.now()}${Math.random().toString(36).slice(2)}`;

export class ProblemTreeController {
  private projectId = '';
  private projectName = '';
  private role: 'owner' | 'editor' | 'viewer' = 'viewer';
  private draft: Tree = emptyTree();
  private saved = JSON.stringify(contentOf(emptyTree()));
  private saving = false;
  private loading = false;
  private loadToken = 0;

  constructor(private request: Request, private onBack: () => void, private onAsk: () => void) {
    byId('problem-tree-back').addEventListener('click', () => { if (this.canLeave()) this.onBack(); });
    byId('problem-tree-ask').addEventListener('click', () => { if (this.canLeave()) this.onAsk(); });
    byId('problem-tree-save').addEventListener('click', () => { void this.save(); });
    byId('problem-tree-reload').addEventListener('click', () => { if (this.canLeave()) void this.load(); });
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

  async open(projectId: string, role: 'owner' | 'editor' | 'viewer', projectQuestion = '', projectName = '') {
    this.projectId = projectId;
    this.projectName = projectName;
    this.role = role;
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
      this.draft = structuredClone(tree);
      this.saved = JSON.stringify(contentOf(tree));
      if (!tree.problem && !tree.causes.length && !tree.effects.length && projectQuestion.trim()) {
        this.draft.problem = projectQuestion.trim();
        byId('problem-tree-subtitle').textContent = `${this.projectName} · Copiamos el reto como borrador. Ajústalo hasta expresar una situación concreta.`;
      } else {
        byId('problem-tree-subtitle').textContent = `${this.projectName} · Conecta lo que ocurre con sus posibles causas y consecuencias.`;
      }
      this.render();
    } catch (error) { if (token === this.loadToken) this.showError((error as Error).message); }
    finally { if (token === this.loadToken) { this.loading = false; this.updateState(); } }
  }

  private add(lane: Lane) {
    if (this.role === 'viewer' || this.draft[lane].length >= 30) return;
    const id = nodeId();
    this.draft[lane].push({ id, text: '', source: '' });
    this.render(); this.updateState();
    byId(`problem-tree-${lane}`).querySelector<HTMLTextAreaElement>(`[data-tree-node="${id}"] textarea`)?.focus();
  }

  private moveTo(id: string, lane: Lane, beforeId?: string) {
    if (this.role === 'viewer') return;
    const from: Lane | undefined = this.draft.causes.some(node => node.id === id) ? 'causes' : this.draft.effects.some(node => node.id === id) ? 'effects' : undefined;
    if (!from || (from !== lane && this.draft[lane].length >= 30)) return;
    const index = this.draft[from].findIndex(node => node.id === id);
    const [node] = this.draft[from].splice(index, 1);
    const destination = beforeId ? this.draft[lane].findIndex(item => item.id === beforeId) : -1;
    this.draft[lane].splice(destination < 0 ? this.draft[lane].length : destination, 0, node);
    this.render(); this.updateState();
  }

  private reorder(lane: Lane, id: string, delta: number) {
    const index = this.draft[lane].findIndex(node => node.id === id);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= this.draft[lane].length) return;
    [this.draft[lane][index], this.draft[lane][target]] = [this.draft[lane][target], this.draft[lane][index]];
    this.render(); this.updateState();
    byId(`problem-tree-${lane}`).querySelector<HTMLButtonElement>(`[data-tree-node="${id}"] .tree-move-${delta < 0 ? 'up' : 'down'}`)?.focus();
  }

  private render() {
    const readOnly = this.role === 'viewer';
    const problem = byId<HTMLTextAreaElement>('problem-tree-problem');
    problem.value = this.draft.problem; problem.readOnly = readOnly;
    const source = byId<HTMLInputElement>('problem-tree-problem-source');
    source.value = this.draft.problem_source; source.readOnly = readOnly;
    for (const lane of ['causes', 'effects'] as const) {
      const list = byId(`problem-tree-${lane}`);
      list.replaceChildren();
      if (!this.draft[lane].length) {
        const empty = document.createElement('p'); empty.className = 'problem-tree-empty';
        empty.textContent = lane === 'causes' ? 'Todavía no hay causas. Empieza con una posible explicación.' : 'Todavía no hay efectos. Anota una consecuencia observable.';
        list.append(empty);
      }
      this.draft[lane].forEach((node, index) => list.append(this.card(node, lane, index)));
    }
    this.updateState();
  }

  private card(node: TreeNode, lane: Lane, index: number): HTMLElement {
    const card = document.createElement('article'); card.className = 'problem-tree-card'; card.dataset.treeNode = node.id; card.draggable = this.role !== 'viewer';
    card.addEventListener('dragstart', event => { event.dataTransfer?.setData('text/plain', node.id); card.classList.add('dragging'); });
    card.addEventListener('dragend', () => card.classList.remove('dragging'));
    const head = document.createElement('div'); head.className = 'problem-tree-card-head';
    const number = document.createElement('span'); number.textContent = `${lane === 'causes' ? 'Causa' : 'Efecto'} ${index + 1}`;
    const badge = document.createElement('span'); badge.className = `problem-tree-evidence ${node.source.trim() ? 'has-source' : ''}`;
    badge.textContent = node.source.trim() ? 'Fuente registrada' : 'Por contrastar'; head.append(number, badge);
    const textLabel = document.createElement('label'); textLabel.className = 'sr-only'; textLabel.htmlFor = `tree-text-${node.id}`; textLabel.textContent = `Texto de ${lane === 'causes' ? 'causa' : 'efecto'} ${index + 1}`;
    const text = document.createElement('textarea'); text.id = textLabel.htmlFor; text.rows = 2; text.maxLength = 240;
    text.placeholder = lane === 'causes' ? '¿Por qué ocurre?' : '¿Qué consecuencia produce?'; text.value = node.text; text.readOnly = this.role === 'viewer';
    text.addEventListener('input', () => { node.text = text.value; this.updateState(); });
    const sourceLabel = document.createElement('label'); sourceLabel.htmlFor = `tree-source-${node.id}`; sourceLabel.textContent = 'Origen de esta relación';
    const source = document.createElement('input'); source.id = sourceLabel.htmlFor; source.maxLength = 500;
    source.placeholder = 'Ej. Entrevista, observación o documento'; source.value = node.source; source.readOnly = this.role === 'viewer';
    source.addEventListener('input', () => { node.source = source.value; badge.textContent = node.source.trim() ? 'Fuente registrada' : 'Por contrastar'; badge.classList.toggle('has-source', !!node.source.trim()); this.updateState(); });
    card.append(head, textLabel, text, sourceLabel, source);
    if (this.role !== 'viewer') {
      const actions = document.createElement('div'); actions.className = 'problem-tree-card-actions';
      for (const [label, className, callback, disabled] of [
        ['Subir', 'tree-move-up', () => this.reorder(lane, node.id, -1), index === 0],
        ['Bajar', 'tree-move-down', () => this.reorder(lane, node.id, 1), index === this.draft[lane].length - 1],
        [lane === 'causes' ? 'Pasar a efecto' : 'Pasar a causa', 'tree-change-lane', () => this.moveTo(node.id, lane === 'causes' ? 'effects' : 'causes'), false],
        ['Quitar', 'tree-remove', () => { this.draft[lane].splice(this.draft[lane].findIndex(item => item.id === node.id), 1); this.render(); }, false],
      ] as const) {
        const button = document.createElement('button'); button.type = 'button'; button.className = className; button.textContent = label; button.disabled = disabled;
        button.addEventListener('click', callback); actions.append(button);
      }
      card.append(actions);
    }
    return card;
  }

  private updateState() {
    const dirty = this.isDirty();
    const status = byId('problem-tree-save-state');
    status.textContent = this.loading ? 'Cargando…' : this.saving ? 'Guardando…' : this.role === 'viewer' ? 'Solo lectura' : dirty ? 'Cambios sin guardar' : this.draft.version ? 'Guardado' : 'Árbol nuevo';
    byId<HTMLButtonElement>('problem-tree-save').disabled = this.loading || this.saving || this.role === 'viewer' || !dirty;
    byId<HTMLButtonElement>('problem-tree-reload').disabled = this.loading || this.saving;
    byId<HTMLButtonElement>('problem-tree-add-cause').disabled = this.loading || this.saving || this.role === 'viewer' || this.draft.causes.length >= 30;
    byId<HTMLButtonElement>('problem-tree-add-effect').disabled = this.loading || this.saving || this.role === 'viewer' || this.draft.effects.length >= 30;
  }

  private showError(message: string) { const error = byId('problem-tree-error'); error.textContent = message; error.hidden = !message; }

  private async save() {
    if (this.saving || this.loading || this.role === 'viewer' || !this.isDirty()) return;
    const blanks = [...this.draft.causes, ...this.draft.effects].filter(node => !node.text.trim());
    if (blanks.length) { this.showError('Completa el texto de cada tarjeta o quita las que estén vacías.'); return; }
    if (!this.draft.problem.trim()) { this.showError('Escribe el problema central antes de guardar.'); byId<HTMLTextAreaElement>('problem-tree-problem').focus(); return; }
    this.saving = true; this.showError(''); this.updateState();
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
    finally { this.saving = false; this.updateState(); }
  }
}
