import './why-analysis.css';

type Step = { text: string; evidence: string };
export type WhyAnalysis = {
  id: string; cause_id: string; cause_text: string; problem_text: string;
  steps: Step[]; doubts: string[]; status: 'en_curso' | 'cerrado' | 'descartado';
  reviewing: boolean; awaiting_plan: boolean; candidate: string; incorporated_node_id: string;
  /** Qué notó el código en el último mensaje: «tipo|texto». */
  notice: string;
};

// Mensajes que no entraron a la cadena y por qué. Si la persona insiste con una respuesta
// general o con una herramienta, la segunda vez sí entra.
const SKIPPED: Record<string, string> = {
  pregunta: 'es una pregunta, no una respuesta',
  vaga: 'es muy general; nombra una sola razón concreta',
  solucion: 'nombra una herramienta que falta, no la causa; si la repites, se anota',
};
type Request = <T>(path: string, options?: RequestInit) => Promise<T>;
export type WhyHooks = {
  /** Envía un mensaje al chat como si lo escribiera la persona. */
  send: (text: string) => void;
  /** Deja el chat visible, junto al árbol si el árbol está abierto. */
  openChat: () => void;
  /** Recarga el árbol después de incorporar la causa candidata. */
  reloadTree: () => Promise<void>;
  treeDirty: () => boolean;
  /** Avisa al árbol para que actualice los botones de sus tarjetas. */
  changed: () => void;
};
export type WhyLabel = { label: string; disabled: boolean; title: string };

const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const snippet = (text: string, limit = 70) => text.length <= limit ? text : `${text.slice(0, limit - 1).trimEnd()}…`;
const json = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = ''): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

/**
 * Barra del análisis de 5 porqués en el chat. El agente conduce las preguntas; esta barra
 * muestra la cadena que registró el código, la pregunta pendiente, la evidencia de cada paso
 * y el cierre. Nunca modifica el árbol sin que la persona lo pida.
 */
export class WhyAnalysisController {
  private projectId = '';
  private role = 'viewer';
  private analyses: WhyAnalysis[] = [];
  private finished: WhyAnalysis | null = null;
  private closing = false;
  private error = '';

  constructor(private request: Request, private hooks: WhyHooks) {}

  private base() { return `/projects/${encodeURIComponent(this.projectId)}/why-analyses`; }
  private active() { return this.analyses.find(item => item.status === 'en_curso') || null; }
  private canEdit() { return this.role !== 'viewer'; }

  async setProject(projectId: string, role: string) {
    this.projectId = projectId; this.role = role;
    this.finished = null; this.closing = false; this.error = '';
    await this.refresh();
  }

  async refresh() {
    if (!this.projectId) return;
    try { this.analyses = await this.request<WhyAnalysis[]>(this.base()); }
    catch { this.analyses = []; }
    this.render();
    this.hooks.changed();
  }

  labelFor(causeId: string): WhyLabel {
    const active = this.active();
    if (active?.cause_id === causeId) {
      return { label: 'Continuar 5 porqués', disabled: false, title: 'Hay un análisis en curso sobre esta causa.' };
    }
    if (active) {
      return { label: 'Profundizar con 5 porqués', disabled: true, title: `Termina primero el análisis en curso sobre «${snippet(active.cause_text)}».` };
    }
    const done = this.analyses.some(item => item.cause_id === causeId && item.status === 'cerrado');
    return {
      label: done ? 'Profundizar otra vez' : 'Profundizar con 5 porqués', disabled: false,
      title: 'Abre el chat y pregunta «¿por qué?» a partir de esta causa, una pregunta a la vez.',
    };
  }

  async start(causeId: string, causeText: string) {
    const active = this.active();
    if (active && active.cause_id !== causeId) return;
    if (!active) await this.request(this.base(), json({ cause_id: causeId }));
    this.finished = null; this.closing = false; this.error = '';
    await this.refresh();
    this.hooks.openChat();
    if (!active) this.hooks.send(`Quiero profundizar con cinco porqués la causa «${causeText}».`);
  }

  private async act(run: () => Promise<void>) {
    this.error = '';
    try { await run(); } catch (error) { this.error = (error as Error).message; }
    await this.refresh();
  }

  private saveSteps(analysis: WhyAnalysis, steps: Step[]) {
    void this.act(async () => {
      await this.request(`${this.base()}/${analysis.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ steps }),
      });
    });
  }

  render() {
    const bar = byId('why-bar');
    const active = this.active();
    const shown = active || this.finished;
    bar.hidden = !shown;
    if (!shown) { bar.replaceChildren(); return; }
    const parts: HTMLElement[] = [];
    if (active) parts.push(...(this.closing ? this.closeForm(active) : this.progress(active)));
    else if (this.finished) parts.push(...this.result(this.finished));
    if (this.error) parts.push(el('p', 'why-error', this.error));
    bar.replaceChildren(...parts);
  }

  private header(analysis: WhyAnalysis, state: string) {
    const head = el('div', 'why-head');
    const title = el('div', 'why-title');
    title.append(el('span', 'why-chip', '5 porqués'), el('strong', '', `«${snippet(analysis.cause_text, 80)}»`));
    head.append(title, el('span', 'why-state', state));
    return head;
  }

  private progress(analysis: WhyAnalysis): HTMLElement[] {
    const count = analysis.steps.length;
    const state = analysis.reviewing ? 'Revisando la cadena' : `${count} de 5 respuestas`;
    const parts: HTMLElement[] = [this.header(analysis, state)];
    if (count) {
      const list = el('ol', 'why-chain');
      analysis.steps.forEach((step, index) => {
        const item = el('li');
        const text = el('p', 'why-step', step.text);
        const evidence = el('input', 'why-evidence');
        evidence.placeholder = 'De dónde sale (opcional)'; evidence.value = step.evidence; evidence.maxLength = 500;
        evidence.setAttribute('aria-label', `Evidencia de la respuesta ${index + 1}`);
        evidence.readOnly = !this.canEdit();
        evidence.addEventListener('change', () => {
          this.saveSteps(analysis, analysis.steps.map((item, at) => at === index ? { ...item, evidence: evidence.value.trim() } : item));
        });
        item.append(text, evidence);
        if (this.canEdit()) {
          const remove = el('button', 'why-remove', 'Quitar');
          remove.type = 'button'; remove.title = 'Quita esta respuesta de la cadena';
          remove.addEventListener('click', () => this.saveSteps(analysis, analysis.steps.filter((_, at) => at !== index)));
          item.append(remove);
        }
        list.append(item);
      });
      parts.push(list);
    }
    if (analysis.doubts.length) {
      const doubts = el('div', 'why-doubts');
      doubts.append(el('span', '', 'Por investigar'));
      const list = el('ul');
      for (const doubt of analysis.doubts) list.append(el('li', '', doubt));
      doubts.append(list);
      parts.push(doubts);
    }
    const [kind, said] = [analysis.notice.split('|')[0], analysis.notice.slice(analysis.notice.indexOf('|') + 1)];
    if (!analysis.reviewing && SKIPPED[kind]) {
      parts.push(el('p', 'why-skipped', `No se anotó «${snippet(said, 60)}»: ${SKIPPED[kind]}.`));
    }
    const last = count ? analysis.steps[count - 1].text : analysis.cause_text;
    const paused = analysis.doubts.some(doubt => doubt.startsWith(`¿Por qué ocurre «${snippet(last, 90)}»?`));
    parts.push(el('p', 'why-next', analysis.reviewing
      ? 'Cuéntale a Hilo en el chat qué conexión te parece más débil.'
      : analysis.awaiting_plan
        ? 'Cuéntale a Hilo qué podrías revisar o a quién podrías preguntar para averiguarlo.'
        : kind === 'sin_hipotesis'
          ? 'Queda por investigar. Revisa la cadena con lo que tienes o escribe otra razón.'
          : paused
            ? 'Si tienes una hipótesis, escríbela en el chat; si no, revisa la cadena y termina.'
            : `Responde en el chat: ¿por qué ocurre «${snippet(last, 90)}»? Si no lo sabes, escribe «no sé».`));
    if (this.canEdit()) {
      const actions = el('div', 'why-actions');
      if (count && !analysis.reviewing) {
        actions.append(this.button('Revisar cadena', 'quiet', () => this.act(async () => {
          await this.request(`${this.base()}/${analysis.id}/review`, { method: 'POST' });
          this.hooks.send('Revisemos la cadena de porqués antes de terminar.');
        })));
      }
      if (analysis.reviewing) {
        actions.append(this.button('Seguir preguntando', 'quiet', () => this.act(async () => {
          await this.request(`${this.base()}/${analysis.id}/resume`, { method: 'POST' });
        })));
      }
      if (count) actions.append(this.button('Terminar', 'primary', async () => { this.closing = true; this.render(); }));
      actions.append(this.button('Descartar', 'danger', () => this.act(async () => {
        if (!window.confirm('¿Descartar este análisis? La conversación se conserva en el chat.')) return;
        await this.request(`${this.base()}/${analysis.id}/discard`, { method: 'POST' });
      })));
      parts.push(actions);
    }
    return parts;
  }

  private closeForm(analysis: WhyAnalysis): HTMLElement[] {
    const form = el('form', 'why-close');
    const label = el('label', '', 'Causa candidata');
    const input = el('input');
    input.id = 'why-candidate'; label.htmlFor = input.id; input.maxLength = 240; input.required = true;
    // Se propone la última respuesta, sin «porque» ni «creo que» al inicio.
    let proposed = (analysis.steps[analysis.steps.length - 1]?.text || '').trim().replace(/\.$/, '');
    for (let i = 0; i < 3; i++) proposed = proposed.replace(/^(porque|ya que|pues|creo que|pienso que|supongo que|tal vez|quiz[aá]s)\s+/i, '');
    input.value = (proposed.charAt(0).toUpperCase() + proposed.slice(1)).slice(0, 240);
    const hint = el('p', 'why-hint', 'Cinco respuestas no confirman por sí solas una causa raíz. Elige la que mejor explica el problema según la evidencia; puedes reescribirla.');
    const actions = el('div', 'why-actions');
    const save = this.button('Guardar resultado', 'primary', async () => { /* lo maneja el submit */ });
    save.type = 'submit';
    actions.append(save, this.button('Volver', 'quiet', async () => { this.closing = false; this.render(); }));
    form.append(label, input, hint, actions);
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (!input.value.trim()) return;
      void this.act(async () => {
        this.finished = await this.request<WhyAnalysis>(`${this.base()}/${analysis.id}/close`, json({ candidate: input.value.trim() }));
        this.closing = false;
      });
    });
    queueMicrotask(() => input.focus());
    return [this.header(analysis, 'Terminar el análisis'), form];
  }

  private result(analysis: WhyAnalysis): HTMLElement[] {
    const parts: HTMLElement[] = [this.header(analysis, 'Resultado guardado')];
    const summary = el('div', 'why-result');
    summary.append(el('span', '', 'Causa candidata'), el('p', '', analysis.candidate));
    const evidence = analysis.steps.filter(step => step.evidence).map(step => step.evidence);
    if (evidence.length) summary.append(el('span', '', 'Evidencia'), el('p', '', evidence.join(' · ')));
    if (analysis.doubts.length) summary.append(el('span', '', 'Por investigar'), el('p', '', analysis.doubts.join(' ')));
    parts.push(summary);
    const actions = el('div', 'why-actions');
    if (analysis.incorporated_node_id) {
      parts.push(el('p', 'why-next', 'Quedó en el árbol como causa de fondo de la causa de partida.'));
    } else if (this.canEdit()) {
      actions.append(this.button('Incorporar al árbol', 'primary', () => this.act(async () => {
        if (this.hooks.treeDirty()) throw new Error('Guarda o descarta los cambios del árbol antes de incorporar la causa.');
        const done = await this.request<{ node_id: string }>(`${this.base()}/${analysis.id}/incorporate`, { method: 'POST' });
        this.finished = { ...analysis, incorporated_node_id: done.node_id };
        await this.hooks.reloadTree();
      })));
    }
    actions.append(this.button('Cerrar', 'quiet', async () => { this.finished = null; this.render(); }));
    parts.push(actions);
    return parts;
  }

  private button(text: string, tone: 'primary' | 'quiet' | 'danger', run: () => Promise<void>) {
    const button = el('button', `why-button ${tone}`, text);
    button.type = 'button';
    button.addEventListener('click', () => { void run(); });
    return button;
  }
}
