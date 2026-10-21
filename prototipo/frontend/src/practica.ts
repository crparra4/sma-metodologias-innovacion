import './practica.css';

// Practicar una entrevista con un cliente simulado (`cliente_simulado.py`). A la izquierda la
// entrevista; a la derecha la libreta del entrevistador, que sella cada pregunta en cuanto se
// hace: lo que estuvo bien y lo que conviene evitar, con la cita literal de la ficha «Trabajo de
// campo». Lo que responde el cliente es práctica: no se guarda en la ficha ni en el chat.

type Role = 'owner' | 'editor' | 'viewer';
type Request = <T>(path: string, options?: RequestInit) => Promise<T>;
type Turn = { rol: 'entrevistador' | 'cliente'; texto: string };
type Evitar = { nombre: string; cita: string };
type Detalle = { pregunta: string; bien: string[]; evitar: Evitar[] };
type Retro = {
  preguntas: number; sin_problemas: number; detalle: Detalle[];
  consejos: { nombre: string; cita: string; veces: number }[];
};
type Practica = { id: string; persona: string; turnos: Turn[]; retro?: Retro; aviso?: string };

const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = '') => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
const key = (projectId: string) => `hilo-practica-${projectId}`;
const remember = (projectId: string, id: string | null) => {
  try { if (id) localStorage.setItem(key(projectId), id); else localStorage.removeItem(key(projectId)); } catch { /* sin almacenamiento: no se retoma */ }
};
const recall = (projectId: string) => {
  try { return localStorage.getItem(key(projectId)); } catch { return null; }
};
// Primera palabra con mayúscula del personaje («Don Hernando, 67 años…» → «Don Hernando»).
const shortName = (persona: string) => persona.split(/[,.;:(]/)[0].trim().slice(0, 40) || 'Tu cliente';

export class PracticeController {
  private projectId = '';
  private role: Role = 'viewer';
  private practica: Practica | null = null;
  private asking = false;
  private stamped = 0; // cuántos sellos ya se mostraron: solo el nuevo se anima

  constructor(private api: Request) {
    byId('practice-setup').addEventListener('submit', event => { event.preventDefault(); void this.start(); });
    byId('practice-ask').addEventListener('submit', event => { event.preventDefault(); void this.ask(); });
    byId('practice-new').addEventListener('click', () => this.reset());
    byId<HTMLTextAreaElement>('practice-question').addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); byId<HTMLFormElement>('practice-ask').requestSubmit(); }
    });
  }

  async open(projectId: string, role: Role): Promise<void> {
    this.projectId = projectId; this.role = role; this.practica = null; this.stamped = 0;
    this.showError();
    let saved = recall(projectId);
    if (!saved) {  // otro navegador u otro equipo: se retoma la práctica más reciente
      try {
        const lista = await this.api<{ id: string }[]>(`/projects/${encodeURIComponent(projectId)}/practicas`);
        saved = lista[0]?.id || null;
      } catch { saved = null; }
    }
    if (saved) {
      try {
        this.practica = await this.api<Practica>(`/projects/${encodeURIComponent(projectId)}/practicas/${encodeURIComponent(saved)}`);
        this.stamped = this.practica.retro?.detalle.length || 0;
      } catch { remember(projectId, null); }
    }
    this.render();
  }

  canLeave(): boolean { return !this.asking; }

  private showError(message = '') {
    const box = byId('practice-error');
    box.textContent = message; box.hidden = !message;
  }

  private async start() {
    const input = byId<HTMLTextAreaElement>('practice-persona');
    const persona = input.value.trim();
    if (persona.length < 10) { this.showError('Describe a la persona en una o dos frases: quién es y qué le pasa.'); input.focus(); return; }
    this.showError();
    const button = byId<HTMLButtonElement>('practice-start'); button.disabled = true;
    try {
      const creada = await this.api<Practica>(`/projects/${encodeURIComponent(this.projectId)}/practicas`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ persona }),
      });
      this.practica = { ...creada, turnos: [] }; this.stamped = 0;
      remember(this.projectId, creada.id);
      input.value = '';
      this.render();
      byId<HTMLTextAreaElement>('practice-question').focus();
    } catch (error) {
      this.showError((error as Error).message);
    } finally { button.disabled = false; }
  }

  private async ask() {
    const input = byId<HTMLTextAreaElement>('practice-question');
    const texto = input.value.trim();
    if (!texto || this.asking || !this.practica) return;
    this.asking = true; this.showError();
    const practica = this.practica;
    practica.turnos.push({ rol: 'entrevistador', texto });
    input.value = '';
    this.render(true);
    try {
      const base = `/projects/${encodeURIComponent(this.projectId)}/practicas/${encodeURIComponent(practica.id)}`;
      const respuesta = await this.api<{ respuesta: string }>(`${base}/mensajes`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto }),
      });
      practica.turnos.push({ rol: 'cliente', texto: respuesta.respuesta });
      const actual = await this.api<Practica>(base);
      practica.retro = actual.retro;
    } catch (error) {
      practica.turnos.pop();
      input.value = texto;
      this.showError((error as Error).message);
    } finally {
      this.asking = false;
      this.render();
      input.focus();
    }
  }

  private reset() {
    if (this.asking) return;
    remember(this.projectId, null);
    this.practica = null; this.stamped = 0;
    this.showError(); this.render();
    byId<HTMLTextAreaElement>('practice-persona').focus();
  }

  private render(thinking = false) {
    const practica = this.practica;
    const viewer = this.role === 'viewer';
    byId('practice-viewer-note').hidden = !viewer;
    byId('practice-setup').hidden = !!practica || viewer;
    byId('practice-board').hidden = !practica;
    byId<HTMLButtonElement>('practice-new').hidden = !practica || viewer;
    if (!practica) return;
    const nombre = shortName(practica.persona);
    byId('practice-persona-name').textContent = nombre;
    byId('practice-persona-text').textContent = practica.persona;
    byId<HTMLButtonElement>('practice-send').disabled = this.asking || viewer;
    byId<HTMLTextAreaElement>('practice-question').disabled = this.asking || viewer;
    this.renderTurns(nombre, thinking);
    this.renderNotebook();
  }

  private renderTurns(nombre: string, thinking: boolean) {
    const list = byId('practice-turns');
    list.replaceChildren();
    const practica = this.practica!;
    if (!practica.turnos.length) {
      list.append(make('li', 'practice-empty', `Saluda a ${nombre} y haz tu primera pregunta. Prueba pedirle que te cuente la última vez que vivió el problema.`));
    }
    for (const turno of practica.turnos) {
      const item = make('li', `practice-turn is-${turno.rol}`);
      if (turno.rol === 'cliente') item.dataset.noteColor = 'yellow';
      item.append(make('span', 'practice-who', turno.rol === 'cliente' ? nombre : 'Tú'), make('p', '', turno.texto));
      list.append(item);
    }
    if (thinking) {
      const item = make('li', 'practice-turn is-cliente is-thinking');
      item.dataset.noteColor = 'yellow';
      item.setAttribute('aria-busy', 'true');
      item.append(make('span', 'practice-who', nombre), make('p', '', `${nombre} está pensando…`));
      list.append(item);
    }
    list.lastElementChild?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  private renderNotebook() {
    const retro = this.practica!.retro;
    const stamps = byId('practice-stamps');
    const tips = byId('practice-tips');
    stamps.replaceChildren(); tips.replaceChildren();
    const total = retro?.preguntas || 0;
    const limpias = retro?.sin_problemas || 0;
    byId('practice-score').textContent = total
      ? `${limpias} de ${total} ${total === 1 ? 'pregunta' : 'preguntas'} sin nada que evitar`
      : 'Aquí se sella cada pregunta que hagas.';
    const meter = byId('practice-meter');
    meter.hidden = !total;
    meter.style.setProperty('--avance', total ? String(limpias / total) : '0');
    (retro?.detalle || []).forEach((detalle, index) => {
      const item = make('li', 'practice-stamp');
      if (index >= this.stamped) item.classList.add('is-new');
      item.append(make('span', 'practice-stamp-number', String(index + 1)), make('p', 'practice-stamp-question', `«${detalle.pregunta}»`));
      const seals = make('div', 'practice-seals');
      for (const bien of detalle.bien) seals.append(make('span', 'practice-seal is-good', `✔ ${bien}`));
      for (const evitar of detalle.evitar) {
        const seal = make('details', 'practice-seal is-avoid');
        seal.append(make('summary', '', `⚠ ${evitar.nombre}`), make('p', '', `La ficha dice: «${evitar.cita}»`));
        seals.append(seal);
      }
      if (!detalle.bien.length && !detalle.evitar.length) seals.append(make('span', 'practice-seal is-neutral', 'Sin observaciones'));
      item.append(seals);
      stamps.append(item);
    });
    this.stamped = retro?.detalle.length || 0;
    if (retro?.consejos.length) {
      tips.append(make('h4', '', 'Para la próxima'));
      const list = make('ul');
      for (const consejo of retro.consejos) {
        const item = make('li');
        item.append(make('strong', '', `${consejo.nombre} ×${consejo.veces}`), make('span', '', ` — «${consejo.cita}»`));
        list.append(item);
      }
      tips.append(list);
    }
  }
}
