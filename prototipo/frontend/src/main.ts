import './style.css';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { taskTiming, localDateKey, kindLabels, kindIcons, dayLanes, notificationGroups, type Task, type EntryKind } from './agenda';
import { authText, translateAuthError, loadAuthLanguage, saveAuthLanguage, type AuthTextKey } from './auth-language';
import { ProblemTreeController } from './problem-tree';
let tasks: Task[] = [];
let taskFilter: 'today' | 'upcoming' | 'all' = 'upcoming';
let editingTask: Task | null = null;
let taskLoading = true;
let taskSaving = false;
let taskLoadError = '';
let activityFailed = false;
const priorityLabels = { high: 'Alta', medium: 'Media', low: 'Baja' };

type Stage = { id: number; name: string; phase: string; objective: string; tools: string[] };
type Tool = { id: string; name: string; methodology: string; template_fields: string[] };
type Verification = { verdict: string; findings: { code: string; detail: string }[] };
type Result = { message: string; verification: Verification; attempts: number; degraded: boolean; handoff: { active_tool: string; stage: number; phase: string } };
type Context = { question: string; environment: string; objective: string; hypothesis: string; acceptance_criteria: string; ambition: string };
type Color = 'blue' | 'yellow' | 'green' | 'orange' | 'purple' | 'gray';
type State = { notebook_id: string; stage: number; phase: string; active_tool: string; recent_turns: string[]; shared_context?: string[]; validated_fields: Record<string, Record<string, unknown>>; context: Context; color: Color };
type MemberRole = 'owner' | 'editor' | 'viewer';
type ProjectAccess = { project_id: string; owner_user_id: string; notebook_id: string; owner_name: string; owner_username: string; role: MemberRole };
type Notebook = { notebook_id: string; project_id: string; owner_name: string; owner_username: string; role: MemberRole; shared: boolean; stage: number; updated_at: string; preview: string | null; turn_count: number; color: Color; collaborators?: SharingMember[] };
type Turn = { role: string; content: string; created_at?: string; metadata?: Result | null };
type NoteColor = 'yellow' | 'pink' | 'blue' | 'green' | 'purple' | 'orange';
type Note = { id: string; title: string; text: string; color: NoteColor; category: string; source_text: string; created_at: string; updated_at: string; author_id?: string; author_name?: string };
type Advance = { id: string; content: string; kind: 'decision' | 'finding' | 'hypothesis' | 'next_step' | 'other'; author_id: string; author_name: string; created_at: number; version: number };
type SharingMember = { user_id?: string; id?: string; username: string; display_name: string; role: MemberRole; status?: 'pending'; invitation_id?: string };
type Invitation = { id: string; role: 'viewer' | 'editor'; notebook_id: string; project_id: string; owner_name: string; owner_username: string; created_at: number };
const categoryNames: Record<string, string> = { idea: 'Idea', prototipo: 'Prototipo', observacion: 'Observación', pregunta: 'Pregunta', decision: 'Decisión', otro: 'Otro' };
let notes: Note[] = [];
let editingNote: Note | null = null;
let editingAdvanceId: string | null = null; let retiringAdvanceId: string | null = null; let advanceConflictId: string | null = null;
let noteSource = '';
let noteSaving = false;
let selectedExcerpt = '';
type Graph = { nodes: string[]; edges: { source: string; target: string; conditional: boolean }[] };
type StreamEvent = { type: string; node?: string; status?: string; attempt?: number; duration_ms?: number; state?: State; handoff?: Result['handoff']; verification?: Verification; result?: Result; elapsed_ms?: number; source_sections?: string[]; message?: string };
const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const icon = (name: string) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const safeMarkdown = (text: string) => DOMPurify.sanitize(marked.parse(text, { async: false }) as string);
const names: Record<string, string> = { orchestrate: 'Orquestador', guide: 'Metodólogo', verify: 'Verificador', finalize: 'Respuesta', degrade: 'Respuesta segura', knowledge_gap: 'Sin ficha' };
const verdictNames: Record<string, string> = { approved: 'Aprobada', observed: 'Con observaciones', rejected: 'Respuesta segura' };
let stages: Stage[] = [];
let tools: Tool[] = [];
let graphData: Graph;
let activeState: State | null = null;
let activeAccess: ProjectAccess | null = null;
let sharedMembers: SharingMember[] = [];
let advances: Advance[] = [];
let invitations: Invitation[] = [];
let currentView: 'home' | 'project' | 'tools' | 'calendar' | 'tree' = 'home';
const methodologyNames: Record<string, string> = { transversal: 'Transversal', 'design-thinking': 'Design Thinking', 'lean-startup': 'Lean Startup', sit: 'SIT' };
type Account = { id: string; username: string; display_name: string };
let account: Account | null = null;
const notebookStorageKey = () => `hilo-notebook-${account?.id || 'local'}`;
let authMode: 'login' | 'register' = 'login';
let authLanguage = loadAuthLanguage();
const authT = (key: AuthTextKey) => authText(authLanguage, key);
const summaries = new Map<string, string>();
let summariesRequested = false;
type DayActivity = { notebook: string; count: number };
let activity = new Map<string, DayActivity[]>();
let activityReady = false;
let activityVersion = 0;
let calendarCursor = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let selectedDay = '';
let editingProject = false;
const contextLabels: Record<keyof Context, string> = { question: 'Reto o pregunta de negocio', environment: 'Entorno', objective: 'Objetivo del proyecto', hypothesis: 'Hipótesis o supuestos · por contrastar', acceptance_criteria: 'Criterio de aceptación · meta', ambition: 'Ambición 10X · meta' };
const colorNames: Record<Color, string> = { blue: 'azul', yellow: 'amarillo', green: 'verde', orange: 'naranja', purple: 'morado', gray: 'gris' };
let notebooks: Notebook[] = [];
let busy = false;
let loadingNotebook = false;
let available = false;
let serverBusy = false;
let selectedVersion = 0;
let pending: HTMLElement | null = null;
let traceCount = 0;
let lastNode = '__start__';
const traversedEdges = new Set<string>();
let clock: ReturnType<typeof setInterval> | null = null;
const messageInput = el<HTMLTextAreaElement>('message');
const expandMessage = el<HTMLButtonElement>('expand-message');
let messageExpanded = false;
function fitMessageInput() {
  if (!messageInput.value) messageExpanded = false;
  const collapsedLimit = 154;
  const expandedLimit = Math.min(520, Math.max(200, window.innerHeight * .58));
  messageInput.style.height = 'auto';
  const naturalHeight = Math.max(24, messageInput.scrollHeight);
  const limit = messageExpanded ? expandedLimit : collapsedLimit;
  messageInput.style.height = `${Math.min(naturalHeight, limit)}px`;
  messageInput.style.overflowY = naturalHeight > limit ? 'auto' : 'hidden';
  const canExpand = naturalHeight > collapsedLimit || messageExpanded;
  expandMessage.hidden = !canExpand;
  expandMessage.setAttribute('aria-expanded', String(messageExpanded));
  expandMessage.setAttribute('aria-label', messageExpanded ? 'Reducir el espacio para escribir' : 'Ampliar el espacio para escribir');
  expandMessage.querySelector('use')!.setAttribute('href', messageExpanded ? '#i-collapse' : '#i-expand');
  el('chat-form').classList.toggle('is-expanded', messageExpanded);
  el('chat-form').classList.toggle('is-multiline', naturalHeight > 48);
  el('chat-form').classList.toggle('has-long-message', naturalHeight > collapsedLimit);
}
const messageBox = el('messages');
let followingEnd = true;
let chatWidth = messageBox.clientWidth;
let chatHeight = messageBox.clientHeight;

messageBox.addEventListener('scroll', () => {
  // Un reflujo cambia las dimensiones antes de cambiar el desplazamiento; no es un gesto del usuario.
  if (messageBox.clientWidth === chatWidth && messageBox.clientHeight === chatHeight) {
    followingEnd = messageBox.scrollHeight - messageBox.scrollTop - messageBox.clientHeight < 40;
  }
});
new ResizeObserver(() => {
  const keepLatestVisible = followingEnd;
  chatWidth = messageBox.clientWidth;
  chatHeight = messageBox.clientHeight;
  if (keepLatestVisible) requestAnimationFrame(scrollChat);
}).observe(messageBox);

function errorMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => String(item.msg || 'Revisa los datos ingresados.')).join(' ');
  return 'No se pudo conectar con la interfaz. Vuelve a intentarlo.';
}

/** Error de la API con su codigo HTTP; un 409 trae la version vigente en `current`. */
class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly current?: unknown) { super(message); }
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(errorMessage(error.detail), response.status, error.current);
  }
  return response.json();
}

const problemTree = new ProblemTreeController(api, () => {
  currentView = 'project';
  history.pushState(null, '', `#proyecto=${encodeURIComponent(activeAccess!.project_id)}`);
  updateHeader(); renderNotebooks();
}, () => {
  currentView = 'project';
  history.pushState(null, '', `#proyecto=${encodeURIComponent(activeAccess!.project_id)}`);
  updateHeader(); renderNotebooks();
  messageInput.value = 'Ayúdame a revisar las posibles causas y efectos de mi árbol de problemas. ¿Qué relación debería contrastar primero?';
  fitMessageInput(); syncControls(); messageInput.focus();
});

function showError(message = '') {
  el('global-error').textContent = message;
  el('global-error').hidden = !message;
  el('project-form-error').textContent = message;
  el('project-form-error').hidden = !message;
  if (message && !el('app').hidden) showToast('error', 'No pudimos completar la acción', message);
}

type ToastTone = 'info' | 'success' | 'warning' | 'error';
const toastIcons: Record<ToastTone, string> = { info: 'info', success: 'check', warning: 'warning', error: 'error' };
const toastTimers = new WeakMap<HTMLElement, ReturnType<typeof setTimeout>>();

function removeToast(toast: HTMLElement) {
  const timer = toastTimers.get(toast); if (timer) clearTimeout(timer);
  toastTimers.delete(toast);
  toast.classList.add('is-leaving');
  setTimeout(() => toast.remove(), 180);
}

function showToast(tone: ToastTone, title: string, message: string, duration = tone === 'error' ? 7000 : 4800) {
  const region = el('toast-region');
  const repeated = [...region.querySelectorAll<HTMLElement>('.toast')].find(item => item.dataset.message === message);
  if (repeated) removeToast(repeated);
  while (region.children.length >= 3) region.firstElementChild?.remove();
  const toast = document.createElement('article'); toast.className = 'toast'; toast.dataset.tone = tone; toast.dataset.message = message;
  if (tone === 'error') toast.setAttribute('role', 'alert'); else toast.setAttribute('role', 'status');
  const mark = document.createElement('span'); mark.className = 'toast-mark'; mark.innerHTML = icon(toastIcons[tone]);
  const copy = document.createElement('div'); copy.className = 'toast-copy';
  const heading = document.createElement('strong'); heading.textContent = title;
  const detail = document.createElement('p'); detail.textContent = message;
  const close = document.createElement('button'); close.type = 'button'; close.className = 'toast-close'; close.innerHTML = icon('close'); close.setAttribute('aria-label', `Cerrar aviso: ${title}`);
  close.addEventListener('click', () => removeToast(toast));
  copy.append(heading, detail); toast.append(mark, copy, close); region.append(toast);
  const pause = () => { const timer = toastTimers.get(toast); if (timer) clearTimeout(timer); toastTimers.delete(toast); };
  const resume = () => { if (!toast.isConnected || toast.classList.contains('is-leaving')) return; pause(); toastTimers.set(toast, setTimeout(() => removeToast(toast), duration)); };
  toast.addEventListener('pointerenter', pause); toast.addEventListener('pointerleave', resume);
  toast.addEventListener('focusin', pause); toast.addEventListener('focusout', event => { if (!toast.contains(event.relatedTarget as Node | null)) resume(); });
  resume();
}

function syncControls() {
  const blocked = busy || loadingNotebook || noteSaving;
  const canEdit = activeAccess?.role !== 'viewer';
  const isOwner = activeAccess?.role === 'owner';
  el<HTMLButtonElement>('new-note').disabled = loadingNotebook || !activeState || !['project', 'tree'].includes(currentView) || noteSaving || !canEdit;
  el<HTMLButtonElement>('save-selection').disabled = loadingNotebook || !activeState || !selectedExcerpt || selectedExcerpt.length > 3000 || noteSaving || !canEdit;
  el<HTMLButtonElement>('send').disabled = blocked || !available || serverBusy || !activeState || !messageInput.value.trim();
  el<HTMLButtonElement>('new-notebook').disabled = blocked;
  el<HTMLButtonElement>('edit-project').disabled = blocked || serverBusy || !activeState || !isOwner;
  el<HTMLButtonElement>('open-problem-tree').disabled = blocked || !activeState;
  el<HTMLButtonElement>('share-project').disabled = loadingNotebook || !activeState;
  el<HTMLButtonElement>('tree-share-project').disabled = loadingNotebook || !activeState;
  for (const id of ['go-home', 'go-tools', 'go-calendar', 'see-all-projects', 'home-new-project', 'empty-new-project', 'sidebar-search', 'sidebar-projects']) el<HTMLButtonElement>(id).disabled = blocked || !stages.length;
  el('project-grid').querySelectorAll('button').forEach(node => { node.disabled = blocked; });
  el<HTMLButtonElement>('delete-notebook').disabled = blocked || !activeState || !isOwner;
  messageInput.disabled = blocked || !activeState;
  el<HTMLButtonElement>('confirm-delete').disabled = blocked;
  el<HTMLFormElement>('notebook-form').querySelectorAll('button, input, select').forEach(node => {
    (node as HTMLButtonElement).disabled = blocked;
  });
  el('notebook-form').querySelectorAll('textarea').forEach(node => { node.disabled = blocked; });
  el<HTMLInputElement>('notebook-name').disabled = blocked || editingProject;
  el<HTMLSelectElement>('initial-stage').disabled = blocked || editingProject;
  el('notebook-list').querySelectorAll('button').forEach(node => { node.disabled = blocked; });
}

async function refreshStatus() {
  try {
    const status = await api<{ available: boolean; busy: boolean; model: string }>('/status');
    available = status.available;
    serverBusy = status.busy;
    el('model-dot').className = `status-dot ${available ? 'online' : 'offline'}`;
    el('profile').title = `${status.model} · ${available ? 'disponible' : 'sin conexión'}`;
    if (!busy) el('run-status').firstElementChild!.textContent = available
      ? (serverBusy ? 'Hay una respuesta en curso. Se guardará al terminar; recarga el cuaderno después.' : 'Una pregunta a la vez, con respaldo metodológico.')
      : 'Inicia Qwen para conversar. La conexión se comprueba automáticamente.';
  } catch {
    available = false;
    el('profile').title = 'Sin conexión al servidor';
    el('model-dot').className = 'status-dot offline';
  }
  syncControls();
}

function toolName(id: string) { return tools.find(tool => tool.id === id)?.name || id; }
function stageName(id: number) { return stages.find(stage => stage.id === id)?.name || `Etapa ${id}`; }
function scrollChat() { followingEnd = true; messageBox.scrollTo({ top: messageBox.scrollHeight, behavior: 'auto' }); }

function turnHeader(role: string, createdAt?: string): HTMLElement {
  const header = document.createElement('div'); header.className = 'turn-label';
  const avatar = document.createElement('span'); avatar.className = 'turn-avatar'; avatar.setAttribute('aria-hidden', 'true');
  if (role === 'user') avatar.textContent = profileName().split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('').toLocaleUpperCase('es');
  else avatar.innerHTML = '<img src="/hilo-mark.png" alt="" width="24" height="24" />';
  const name = document.createElement('span'); name.className = 'turn-name'; name.textContent = role === 'user' ? 'Tú' : 'Hilo';
  header.append(avatar, name);
  if (createdAt) {
    const date = new Date(createdAt);
    if (!Number.isNaN(date.getTime())) {
      const time = document.createElement('time'); time.className = 'turn-time'; time.dateTime = date.toISOString();
      time.textContent = new Intl.DateTimeFormat('es-CO', { hour: '2-digit', minute: '2-digit' }).format(date);
      time.title = new Intl.DateTimeFormat('es-CO', { dateStyle: 'long', timeStyle: 'short' }).format(date);
      header.append(time);
    }
  }
  return header;
}

function appendTurn(turn: Turn): HTMLElement {
  const wrapper = document.createElement('article');
  wrapper.className = `turn ${turn.role === 'user' ? 'user-turn' : 'assistant-turn'}`;
  const label = turnHeader(turn.role, turn.created_at);
  const content = document.createElement('div');
  content.className = 'turn-content';
  if (turn.role === 'user') content.textContent = turn.content;
  else content.innerHTML = safeMarkdown(turn.content);
  wrapper.append(label, content);
  if (turn.role !== 'user' && turn.metadata) {
    const result = turn.metadata;
    const footer = document.createElement('div');
    footer.className = 'turn-footer';
    const badge = document.createElement('span');
    badge.className = `verdict ${result.verification.verdict}`;
    badge.textContent = verdictNames[result.verification.verdict] || result.verification.verdict;
    const source = document.createElement('button');
    source.type = 'button'; source.className = 'source-link';
    source.textContent = result.handoff.active_tool ? toolName(result.handoff.active_tool) : 'Etapa sin ficha';
    source.disabled = !result.handoff.active_tool;
    source.addEventListener('click', () => {
      const tool = tools.find(item => item.id === result.handoff.active_tool);
      if (tool) void openTool(tool);
    });
    const copy = document.createElement('button');
    copy.className = 'icon-button copy-button'; copy.type = 'button';
    copy.setAttribute('aria-label', 'Copiar respuesta'); copy.innerHTML = icon('copy');
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(turn.content); copy.innerHTML = icon('check'); showToast('success', 'Respuesta copiada', 'Ya puedes pegarla donde la necesites.'); setTimeout(() => { copy.innerHTML = icon('copy'); }, 1500); }
      catch { showError('No se pudo copiar. Selecciona el texto para copiarlo manualmente.'); }
    });
    const save = document.createElement('button'); save.type = 'button'; save.className = 'source-link save-turn';
    save.innerHTML = `${icon('note')}Guardar en post-it`;
    save.addEventListener('click', () => openNote(undefined, content.textContent || turn.content));
    footer.append(badge, source, save, copy);
    if (result.attempts > 1) {
      const retry = document.createElement('span'); retry.className = 'retry-label'; retry.textContent = `${result.attempts} intentos`; footer.insertBefore(retry, copy);
    }
    wrapper.append(footer);
    if (result.verification.findings.length) {
      const details = document.createElement('details'); details.className = 'findings';
      const summary = document.createElement('summary'); summary.textContent = 'Ver observaciones'; details.append(summary);
      for (const finding of result.verification.findings) { const paragraph = document.createElement('p'); paragraph.textContent = finding.detail; details.append(paragraph); }
      wrapper.append(details);
    }
  }
  el('messages').append(wrapper);
  return wrapper;
}

function welcome() {
  el('messages').replaceChildren();
  const box = document.createElement('div'); box.className = 'welcome';
  box.innerHTML = `<div class="welcome-symbol">${icon('route')}</div><h2>Tu proyecto, paso a paso.</h2><p>Cuéntame qué quieres entender o mejorar. Te acompañaré con una pregunta y la ficha metodológica que corresponda.</p><div class="suggestions"></div><div class="welcome-footnote">Puedes seguir el recorrido de los agentes y revisar qué información conserva tu cuaderno.</div>`;
  const suggestions = [
    ['Definir mi reto', 'Quiero definir el reto de mi proyecto. ¿Cómo puedo comenzar?'],
    ['Explorar las causas', 'Quiero aplicar cinco porqués para entender las causas de mi problema.'],
    ['Analizar el entorno', 'Quiero analizar el entorno de mi proyecto utilizando PESTEL.'],
  ];
  for (const [label, text] of suggestions) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'suggestion';
    const caption = document.createElement('span'); caption.textContent = label; button.append(caption); button.insertAdjacentHTML('beforeend', icon('arrow'));
    button.addEventListener('click', () => { if (busy || !activeState) return; messageInput.value = text; fitMessageInput(); messageInput.focus(); syncControls(); });
    box.querySelector('.suggestions')!.append(button);
  }
  el('messages').append(box);
}

function renderMemory() {
  const box = el('memory-fields'); box.replaceChildren();
  const values = activeState?.validated_fields || {};
  if (!Object.keys(values).length) {
    const paragraph = document.createElement('p'); paragraph.className = 'empty-memory';
    paragraph.textContent = 'Los datos que aportes aparecerán aquí cuando sean verificados.'; box.append(paragraph);
    return;
  }
  for (const [tool, fields] of Object.entries(values)) {
    const heading = document.createElement('h3'); heading.textContent = toolName(tool); box.append(heading);
    const list = document.createElement('dl');
    for (const [field, value] of Object.entries(fields)) {
      const term = document.createElement('dt'); term.textContent = field.replaceAll('_', ' ');
      const definition = document.createElement('dd'); definition.textContent = typeof value === 'string' ? value : JSON.stringify(value);
      list.append(term, definition);
    }
    box.append(list);
  }
}


function updateHeader() {
  el('project-name').textContent = currentView === 'home' ? 'Inicio' : activeState?.notebook_id || 'Elige un proyecto';
  el('tree-project-name').textContent = activeState?.notebook_id || '';
  el('project-phase').textContent = activeState?.phase || '';
  el('tree-project-phase').textContent = activeState?.phase || '';
  el('project-current-stage').textContent = activeState ? stageName(activeState.stage) : 'Crea un proyecto para empezar a conversar';
  el('tree-project-stage').textContent = activeState ? stageName(activeState.stage) : '';
  el('project-access-label').textContent = activeAccess
    ? activeAccess.role === 'owner' ? 'Propietario' : activeAccess.role === 'editor' ? `Compartido por ${activeAccess.owner_name} · puedes editar` : `Compartido por ${activeAccess.owner_name} · solo lectura`
    : '';
  el('tree-project-access').textContent = el('project-access-label').textContent;
  el('project-phase').hidden = !activeState;
  const currentStage = activeState?.stage;
  const stagePosition = stages.findIndex(stage => stage.id === currentStage) + 1;
  const hasProgress = ['project', 'tree'].includes(currentView) && stagePosition > 0 && stages.length > 0;
  el('project-progress').hidden = !hasProgress;
  el('tree-project-progress').hidden = !hasProgress;
  if (hasProgress) {
    el('project-progress-label').textContent = `${stagePosition} de ${stages.length}`;
    el('tree-project-progress-label').textContent = `${stagePosition} de ${stages.length}`;
    el('project-progress').setAttribute('aria-label', `Etapa ${stagePosition} de ${stages.length}: ${stageName(activeState!.stage)}`);
    el('tree-project-progress').setAttribute('aria-label', `Etapa ${stagePosition} de ${stages.length}: ${stageName(activeState!.stage)}`);
    el('project-progress-fill').setAttribute('stroke-dashoffset', String(100 - stagePosition / stages.length * 100));
    el('tree-project-progress-fill').setAttribute('stroke-dashoffset', String(100 - stagePosition / stages.length * 100));
  }
  el('project-floating-toolbar').hidden = !['project', 'tree'].includes(currentView);
  el('project-name').title = activeState?.notebook_id || '';
  el('project-heading').hidden = false;
  el('menu-toggle').hidden = false;
  el('home-view').hidden = currentView !== 'home';
  el('tools-view').hidden = currentView !== 'tools';
  el('problem-tree-view').hidden = currentView !== 'tree';
  el('chat-panel').hidden = currentView !== 'project';
  el('calendar-view').hidden = currentView !== 'calendar';
  el('go-calendar').setAttribute('aria-current', currentView === 'calendar' ? 'page' : 'false');
  el('go-tools').setAttribute('aria-current', currentView === 'tools' ? 'page' : 'false');
  el('project-workspace').hidden = !['project', 'tree'].includes(currentView);
  renderBoard();
  el('go-home').setAttribute('aria-current', currentView === 'home' ? 'page' : 'false');
  renderMemory(); syncControls();
}

async function refreshNotebooks() {
  notebooks = await api<Notebook[]>('/notebooks');
  renderNotebooks();
  void loadActivity();
}

function renderNotebooks() {
  const list = el('notebook-list'); list.replaceChildren();
  el('sidebar-project-count').textContent = String(notebooks.length);
  el('recent-group').hidden = !notebooks.length;
  el('see-all-projects').hidden = notebooks.length <= 3;
  for (const notebook of notebooks.slice(0, 3)) {
    const selected = ['project', 'tree'].includes(currentView) && notebook.project_id === activeAccess?.project_id;
    const button = document.createElement('button'); button.className = `notebook-item ${selected ? 'selected' : ''}`; button.type = 'button';
    button.setAttribute('aria-current', selected ? 'page' : 'false');
    const title = document.createElement('strong'); title.textContent = notebook.notebook_id;
    const sub = document.createElement('span'); sub.className = 'notebook-preview'; sub.textContent = notebook.shared ? `${notebook.role === 'editor' ? 'Puedes editar' : 'Solo lectura'} · ${notebook.owner_name}` : notebook.preview || stageName(notebook.stage);
    const glyph = document.createElement('span'); glyph.className = 'notebook-glyph'; glyph.setAttribute('aria-hidden', 'true'); glyph.innerHTML = icon('book');
    button.append(glyph, title, sub); button.title = notebook.notebook_id;
    button.addEventListener('click', () => { if (!busy && !loadingNotebook) void loadNotebook(notebook.project_id); });
    list.append(button);
  }
  renderProjects();
  syncControls();
}

function renderProjects() {
  const query = el<HTMLInputElement>('project-search').value.trim().toLocaleLowerCase('es');
  const matches = notebooks.filter(item => item.notebook_id.toLocaleLowerCase('es').includes(query));
  if (el<HTMLSelectElement>('project-order').value === 'name') matches.sort((a, b) => a.notebook_id.localeCompare(b.notebook_id, 'es', { sensitivity: 'base' }));
  const grid = el('project-grid'); grid.replaceChildren();
  const remembered = localStorage.getItem(notebookStorageKey());
  for (const notebook of matches) {
    const card = document.createElement('button'); card.type = 'button'; card.className = `project-folder ${notebook.project_id === remembered ? 'last-opened' : ''}`;
    card.dataset.color = notebook.color || 'blue';
    card.setAttribute('aria-label', `Abrir proyecto ${notebook.notebook_id}`);
    card.innerHTML = '<span class="folder-papers" aria-hidden="true"><span></span><span></span><span></span></span><span class="folder-front"><strong class="folder-title"></strong><span class="folder-stage"></span><span class="folder-meta"><span class="folder-messages"></span><span class="folder-collaborators" aria-hidden="true"></span></span></span>';
    card.querySelector('.folder-title')!.textContent = notebook.notebook_id;
    card.querySelector('.folder-stage')!.textContent = stageName(notebook.stage);
    if (notebook.project_id === remembered) {
      const last = document.createElement('span'); last.className = 'folder-last'; last.textContent = 'Último abierto'; card.querySelector('.folder-front')!.prepend(last);
    }
    card.querySelector('.folder-messages')!.textContent = notebook.shared ? `${notebook.role === 'editor' ? 'Editor' : 'Lector'} · ${notebook.owner_name}` : `${notebook.turn_count} ${notebook.turn_count === 1 ? 'mensaje' : 'mensajes'}`;
    const collaborators = notebook.collaborators || [];
    const group = card.querySelector('.folder-collaborators')!;
    if (!collaborators.length) group.remove();
    else {
      const people = collaborators.map(member => `${member.display_name}${member.status === 'pending' ? ' (invitación pendiente)' : ''}`);
      card.setAttribute('aria-label', `Abrir proyecto ${notebook.notebook_id}. Personas del proyecto: ${people.join(', ')}`);
      for (const member of collaborators.slice(0, 3)) {
        const avatar = document.createElement('span'); avatar.className = 'folder-collaborator';
        if (member.status === 'pending') avatar.classList.add('is-pending');
        avatar.textContent = initialsOf(member.display_name);
        avatar.style.background = memberTone({ id: member.user_id || member.username, name: member.display_name, role: member.role });
        avatar.title = member.status === 'pending' ? `${member.display_name} · invitación pendiente` : `${member.display_name} · ${memberRoles[member.role]}`;
        group.append(avatar);
      }
      if (collaborators.length > 3) {
        const more = document.createElement('span'); more.className = 'folder-collaborator folder-collaborator-more';
        more.textContent = `+${collaborators.length - 3}`;
        more.title = `${collaborators.length - 3} personas más en el proyecto`;
        group.append(more);
      }
    }
    card.addEventListener('click', () => { if (!busy && !loadingNotebook) void loadNotebook(notebook.project_id); });
    grid.append(card);
  }
  el('project-count').textContent = query ? `${matches.length} de ${notebooks.length} proyectos` : `${notebooks.length} ${notebooks.length === 1 ? 'proyecto guardado' : 'proyectos guardados'}`;
  el('home-empty').hidden = !!matches.length;
  el('home-empty-title').textContent = notebooks.length ? 'No encontramos ese proyecto.' : 'Tu primer proyecto empieza aquí.';
  el('home-empty-description').textContent = notebooks.length ? 'Prueba con otro nombre o borra la búsqueda para ver todos tus proyectos.' : 'Crea un proyecto para organizar tus conversaciones, fuentes y avances.';
  el('empty-new-project').hidden = !!notebooks.length;
  syncControls();
}

function canNavigateAwayFromTree(): boolean {
  if (currentView !== 'tree' || problemTree.canLeave()) return true;
  if (activeAccess) history.replaceState(null, '', `#arbol=${encodeURIComponent(activeAccess.project_id)}`);
  return false;
}

function showHome(updateLocation = true) {
  if (!canNavigateAwayFromTree()) return;
  currentView = 'home';
  if (updateLocation && location.hash !== '#inicio') history.pushState(null, '', '#inicio');
  updateHeader(); renderNotebooks(); setSidebar(false);
}

function showTools(updateLocation = true) {
  if (!canNavigateAwayFromTree()) return;
  currentView = 'tools';
  if (updateLocation && location.hash !== '#herramientas') history.pushState(null, '', '#herramientas');
  updateHeader(); renderNotebooks(); setSidebar(false);
}

async function navigateHome() {
  if (busy || loadingNotebook) return;
  showHome();
  try { await refreshNotebooks(); } catch (error) { showError((error as Error).message); }
}

async function followLocation() {
  if (busy || loadingNotebook) return;
  if (location.hash === '#herramientas') { showTools(false); return; }
  if (location.hash === '#calendario') { showCalendar(false); return; }
  const treeMatch = location.hash.match(/^#arbol=(.+)$/);
  if (treeMatch) {
    let id: string;
    try { id = decodeURIComponent(treeMatch[1]); } catch { showHome(false); return; }
    const notebook = notebooks.find(item => item.project_id === id || item.notebook_id === id);
    if (notebook) {
      await loadNotebook(notebook.project_id, false);
      if (currentView === 'project' && activeAccess?.project_id === notebook.project_id) {
        await showProblemTree(false);
      }
      return;
    }
  }
  const match = location.hash.match(/^#proyecto=(.+)$/);
  if (match) {
    let id: string;
    try { id = decodeURIComponent(match[1]); } catch { showHome(false); return; }
    const notebook = notebooks.find(item => item.project_id === id || item.notebook_id === id);
    if (notebook) { await loadNotebook(notebook.project_id, false); return; }
    showError('Ese proyecto no está disponible. Puedes elegir otro en Inicio.');
  }
  showHome(false);
}

async function loadNotebook(id: string, updateLocation = true) {
  if (!canNavigateAwayFromTree()) return;
  const version = ++selectedVersion; loadingNotebook = true; syncControls(); showError();
  try {
    const data = await api<{ state: State; turns: Turn[]; notes: Note[]; advances: Advance[]; access: ProjectAccess }>(`/notebooks/${encodeURIComponent(id)}`);
    if (version !== selectedVersion) return;
    activeState = data.state; activeAccess = data.access; advances = data.advances || []; currentView = 'project'; localStorage.setItem(notebookStorageKey(), data.access.project_id);
    sharedMembers = await api<SharingMember[]>(`/projects/${encodeURIComponent(data.access.project_id)}/members`);
    notes = data.notes || []; selectedExcerpt = ''; renderNotes();
    if (updateLocation && location.hash !== `#proyecto=${encodeURIComponent(data.access.project_id)}`) history.pushState(null, '', `#proyecto=${encodeURIComponent(data.access.project_id)}`);
    el('messages').replaceChildren();
    if (data.turns.length) data.turns.forEach(appendTurn); else welcome();
    messageInput.value = ''; messageExpanded = false; fitMessageInput(); resetGraph();
    renderMembers(); renderNotebooks(); updateHeader(); scrollChat(); setSidebar(false);
    el('delete-confirm').hidden = true;
  } catch (error) { showError((error as Error).message); }
  finally { if (version === selectedVersion) { loadingNotebook = false; syncControls(); } }
}

async function showProblemTree(updateLocation = true) {
  if (!activeAccess || !activeState) return;
  currentView = 'tree';
  if (updateLocation) history.pushState(null, '', `#arbol=${encodeURIComponent(activeAccess.project_id)}`);
  updateHeader(); renderNotebooks(); setSidebar(false);
  await problemTree.open(activeAccess.project_id, activeAccess.role,
    activeState.context.question, activeState.notebook_id);
}

el('open-problem-tree').addEventListener('click', () => {
  if (busy || loadingNotebook) return;
  if (currentView === 'tree') {
    if (!problemTree.canLeave()) return;
    currentView = 'project';
    history.pushState(null, '', `#proyecto=${encodeURIComponent(activeAccess!.project_id)}`);
    updateHeader(); renderNotebooks();
    return;
  }
  void showProblemTree();
});
el('tree-share-project').addEventListener('click', () => el<HTMLButtonElement>('share-project').click());

const positions: Record<string, { x: number; y: number; w: number; h: number; label: string }> = {
  __start__: { x: 144, y: 15, w: 12, h: 12, label: 'Inicio' },
  orchestrate: { x: 144, y: 65, w: 180, h: 46, label: 'Orquestador' },
  guide: { x: 144, y: 150, w: 180, h: 46, label: 'Metodólogo' },
  verify: { x: 144, y: 235, w: 180, h: 46, label: 'Verificador' },
  finalize: { x: 110, y: 320, w: 145, h: 44, label: 'Respuesta' },
  knowledge_gap: { x: 285, y: 150, w: 100, h: 44, label: 'Sin ficha' },
  degrade: { x: 285, y: 320, w: 100, h: 44, label: 'Respuesta segura' },
  __end__: { x: 144, y: 385, w: 12, h: 12, label: 'Fin' },
};
const paths: Record<string, string> = {
  '__start__>orchestrate': 'M144 21V42', 'orchestrate>guide': 'M144 88V127',
  'orchestrate>knowledge_gap': 'M234 65H285V128', 'guide>verify': 'M144 173V212',
  'verify>guide': 'M54 235H27V150H54', 'verify>finalize': 'M144 258V279H110V298',
  'verify>degrade': 'M234 235H285V298', 'finalize>__end__': 'M110 342V366H144V379',
  'degrade>__end__': 'M285 342V366H144V379', 'knowledge_gap>__end__': 'M335 150H338V395H144V391',
};
const svgNS = 'http://www.w3.org/2000/svg';
const svgElement = (tag: string, attrs: Record<string, string>) => { const node = document.createElementNS(svgNS, tag); for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value); return node; };

function buildGraph() {
  const graph = document.getElementById('graph')!;
  graph.innerHTML = '<defs><marker id="arrowhead" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#9ba9bf"/></marker></defs>';
  for (const edge of graphData.edges) {
    const key = `${edge.source}>${edge.target}`;
    if (!paths[key]) continue;
    graph.append(svgElement('path', { d: paths[key], class: `graph-edge ${edge.conditional ? 'conditional' : ''}`, 'data-source': edge.source, 'data-target': edge.target, 'marker-end': 'url(#arrowhead)' }));
  }
  const retry = svgElement('text', { x: '18', y: '199', transform: 'rotate(-90 18 199)', class: 'edge-label' }); retry.textContent = 'Reintento'; graph.append(retry);
  for (const key of graphData.nodes) {
    const p = positions[key]; if (!p) continue;
    const group = svgElement('g', { 'data-node': key, class: 'graph-node idle' });
    const title = svgElement('title', {}); title.textContent = p.label; group.append(title);
    if (key.startsWith('__')) group.append(svgElement('circle', { cx: String(p.x), cy: String(p.y), r: '6' }));
    else {
      group.append(svgElement('rect', { x: String(p.x - p.w / 2), y: String(p.y - p.h / 2), width: String(p.w), height: String(p.h), rx: '9' }));
      const label = svgElement('text', { x: String(p.x), y: String(p.y - 3), class: `node-title ${p.w < 110 ? 'small' : ''}`, 'text-anchor': 'middle' }); label.textContent = p.label; group.append(label);
      const status = svgElement('text', { x: String(p.x), y: String(p.y + 12), class: 'node-status', 'text-anchor': 'middle' }); status.textContent = 'En espera'; group.append(status);
    }
    graph.append(group);
  }
}

function resetGraph() {
  traversedEdges.clear(); lastNode = '__start__';
  if (graphData) buildGraph();
  traceCount = 0; el('trace-count').textContent = '0';
  el('trace-list').innerHTML = '<li class="empty-trace">Los eventos aparecerán al enviar un mensaje.</li>';
  el('flow-description').textContent = 'El recorrido se ilumina mientras conversas.';
}

function markNode(node: string, status: string, description?: string) {
  const target = document.querySelector<SVGGElement>(`[data-node="${node}"]`);
  if (!target) return;
  target.setAttribute('class', `graph-node ${status}`);
  if (description) { const label = target.querySelector('.node-status'); if (label) label.textContent = description; }
  document.querySelectorAll<SVGPathElement>('.graph-edge').forEach(path => {
    path.classList.toggle('visited', traversedEdges.has(`${path.dataset.source}>${path.dataset.target}`));
  });
}

function handleEvent(event: StreamEvent) {
  if (event.type === 'node' && event.node) {
    const running = event.status === 'started';
    if (running) {
      traversedEdges.add(`${lastNode}>${event.node}`);
      lastNode = event.node;
    }
    markNode(event.node, running ? 'running' : event.status === 'failed' ? 'failed' : 'done', running ? `En ejecución${event.attempt ? ` · intento ${event.attempt}` : ''}` : event.duration_ms !== undefined ? `${(event.duration_ms / 1000).toFixed(1)} s` : 'Completado');
    if (running) {
      el('flow-description').textContent = `${names[event.node] || event.node} en ejecución.`;
      if (pending) pending.querySelector('.pending-text')!.textContent = `${names[event.node] || event.node} trabajando…`;
    }
    if (!traceCount) el('trace-list').replaceChildren();
    const item = document.createElement('li');
    item.className = running ? 'trace-running' : '';
    const label = document.createElement('span'); label.textContent = `${names[event.node] || event.node}${running ? ' · inicio' : ' · completado'}`;
    const time = document.createElement('span'); time.textContent = event.duration_ms !== undefined ? `${(event.duration_ms / 1000).toFixed(1)} s` : event.attempt ? `#${event.attempt}` : '';
    item.append(label, time); el('trace-list').append(item); el('trace-count').textContent = String(++traceCount);
  } else if (event.type === 'session') markNode('__start__', 'done');
  else if (event.type === 'verification' && event.verification) {
    if (event.verification.verdict === 'rejected') markNode('verify', 'failed', 'Rechazada · revisar');
  } else if (event.type === 'result' && event.result && event.state) {
    pending?.remove(); pending = null;
    appendTurn({ role: 'assistant', content: event.result.message, metadata: event.result });
    activeState = event.state; updateHeader();
    traversedEdges.add(`${lastNode}>__end__`);
    markNode('__end__', 'done');
    if (event.result.degraded) {
      markNode(event.result.handoff.active_tool ? 'degrade' : 'knowledge_gap', 'failed', 'Revisión necesaria');
      if (event.result.verification.verdict === 'rejected') markNode('verify', 'failed', 'Rechazada');
    }
    el('flow-description').textContent = event.result.degraded ? 'El control activó una respuesta segura.' : `Respuesta verificada · ${toolName(event.result.handoff.active_tool)}.`;
    el('run-status').firstElementChild!.textContent = 'Respuesta guardada en este cuaderno.';
    el('run-time').textContent = `${((event.elapsed_ms || 0) / 1000).toFixed(1)} s`;
    scrollChat();
  } else if (event.type === 'error') {
    markNode(lastNode, 'failed', 'Error');
    el('flow-description').textContent = 'El turno no pudo completarse.';
    throw new Error(event.message || 'No se pudo completar la respuesta.');
  }
}

async function sendMessage(event: SubmitEvent) {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (busy || loadingNotebook || !available || serverBusy || !activeState || !text) return;
  const notebookId = activeState.notebook_id;
  busy = true; showError(); resetGraph(); syncControls();
  el('messages').querySelector('.welcome')?.remove();
  const userTurn = appendTurn({ role: 'user', content: text });
  pending = document.createElement('article'); pending.className = 'turn assistant-turn pending'; pending.setAttribute('aria-busy', 'true');
  pending.append(turnHeader('assistant'));
  pending.insertAdjacentHTML('beforeend', '<div class="pending-text">Preparando el recorrido…</div><div class="skeleton-line"></div><div class="skeleton-line short"></div>');
  el('messages').append(pending); scrollChat(); messageInput.value = ''; messageExpanded = false; fitMessageInput();
  const start = Date.now(); el('run-status').classList.add('running');
  el('run-status').firstElementChild!.textContent = 'Procesando y verificando tu mensaje…';
  el('run-time').textContent = '0 s';
  let receivedResult = false;
  clock = setInterval(() => { if (!receivedResult) el('run-time').textContent = `${Math.floor((Date.now() - start) / 1000)} s`; }, 1000);
  try {
    const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ notebook_id: notebookId, project_id: activeAccess?.project_id, stage: activeState.stage, message: text }) });
    if (!response.ok) { const error = await response.json(); throw new Error(errorMessage(error.detail)); }
    const reader = response.body!.getReader(); const decoder = new TextDecoder(); let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const packet = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        const line = packet.split('\n').find(item => item.startsWith('data: '));
        if (line) { const data: StreamEvent = JSON.parse(line.slice(6)); handleEvent(data); if (data.type === 'result') receivedResult = true; }
      }
      if (done) break;
    }
    if (!receivedResult) throw new Error('La conexión se interrumpió. Recarga el cuaderno para comprobar si la respuesta quedó guardada.');
    await refreshNotebooks();
  } catch (error) {
    pending?.remove(); pending = null;
    if (!receivedResult) { messageInput.value = text; fitMessageInput(); userTurn.classList.add('unsaved'); }
    showError((error as Error).message);
    if (!receivedResult) el('run-status').firstElementChild!.textContent = 'No se completó el turno. Puedes volver a enviarlo.';
  } finally {
    if (clock) clearInterval(clock); clock = null;
    busy = false; el('run-status').classList.remove('running'); syncControls();
    messageInput.focus();
    void refreshStatus();
  }
}

function setSidebar(open: boolean) {
  if (open) setAccountMenu(false);
  el('sidebar').classList.toggle('open', open);
  el('main-navigation').hidden = !open;
  el('sidebar-backdrop').hidden = true;
  el('menu-toggle').setAttribute('aria-expanded', String(open));
  el('menu-toggle').setAttribute('aria-label', open ? 'Ocultar menú' : 'Mostrar menú');
  if (!open) el<HTMLDetailsElement>('recent-menu').open = false;
}

el('menu-toggle').addEventListener('click', () => setSidebar(!el('sidebar').classList.contains('open')));
el('go-home').addEventListener('click', () => { void navigateHome(); });
window.addEventListener('popstate', () => { void followLocation(); });
window.addEventListener('hashchange', () => { void followLocation(); });
el('project-search').addEventListener('input', renderProjects);
el('project-order').addEventListener('change', renderProjects);
el('sidebar-backdrop').addEventListener('click', () => setSidebar(false));
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  if (!el('account-menu').hidden) { setAccountMenu(false); el('profile').focus(); event.preventDefault(); }
  for (const id of ['header-help', 'header-notifications']) {
    const utility = el<HTMLDetailsElement>(id);
    if (utility.open) { utility.open = false; utility.querySelector('summary')!.focus(); event.preventDefault(); }
  }
  if (el('sidebar').classList.contains('open')) { el('menu-toggle').focus(); event.preventDefault(); }
  setSidebar(false);
});
document.addEventListener('pointerdown', event => {
  if (!el('account-menu').contains(event.target as Node) && !el('profile').contains(event.target as Node)) setAccountMenu(false);
  for (const id of ['header-help', 'header-notifications']) {
    const utility = el<HTMLDetailsElement>(id);
    if (!utility.contains(event.target as Node)) utility.open = false;
  }
  if (!el('main-navigation').contains(event.target as Node) && !el('menu-toggle').contains(event.target as Node)) setSidebar(false);
  const recentMenu = el<HTMLDetailsElement>('recent-menu');
  if (!recentMenu.contains(event.target as Node)) recentMenu.open = false;
});
function selectedColor(): Color {
  return el<HTMLFormElement>('notebook-form').querySelector<HTMLInputElement>('input[name="notebook-color"]:checked')!.value as Color;
}

function setFieldError(id: string, message: string) {
  const input = el<HTMLInputElement | HTMLTextAreaElement>(id);
  const error = el(`${id}-error`); error.textContent = message; error.hidden = !message;
  if (message) input.setAttribute('aria-invalid', 'true'); else input.removeAttribute('aria-invalid');
}

function validateProjectForm(): boolean {
  const name = el<HTMLInputElement>('notebook-name');
  const question = el<HTMLTextAreaElement>('context-question');
  const missingName = !name.value.trim();
  const missingQuestion = question.required && !question.value.trim();
  setFieldError('notebook-name', missingName ? 'Escribe un nombre para tu cuaderno.' : '');
  setFieldError('context-question', missingQuestion ? 'Describe el reto o pregunta de negocio.' : '');
  if (missingName) name.focus(); else if (missingQuestion) question.focus();
  return !missingName && !missingQuestion;
}

function updatePreview() {
  const color = selectedColor(); el('folder-preview').dataset.color = color;
  el('folder-preview').setAttribute('aria-label', `Vista previa del cuaderno ${colorNames[color]}`);
  el('preview-name').textContent = el<HTMLInputElement>('notebook-name').value.trim() || 'Tu nuevo cuaderno';
  el('preview-stage').textContent = stageName(Number(el<HTMLSelectElement>('initial-stage').value));
}

function openProjectForm(edit = false) {
  if (busy || loadingNotebook || !stages.length) return;
  if (edit && (!activeState || serverBusy || activeAccess?.role !== 'owner')) return;
  editingProject = edit;
  setFieldError('notebook-name', ''); setFieldError('context-question', '');
  el<HTMLInputElement>('notebook-name').value = edit ? activeState!.notebook_id : '';
  for (const key of Object.keys(contextLabels) as (keyof Context)[]) el<HTMLTextAreaElement>(`context-${key}`).value = edit ? activeState!.context?.[key] || '' : '';
  el<HTMLSelectElement>('initial-stage').value = String(edit ? activeState!.stage : 1);
  const color = edit ? activeState!.color || 'blue' : 'blue';
  el<HTMLFormElement>('notebook-form').querySelector<HTMLInputElement>(`input[name="notebook-color"][value="${color}"]`)!.checked = true;
  el('new-project-title').textContent = edit ? 'Editar cuaderno' : 'Nuevo cuaderno';
  el('project-form-description').textContent = edit ? 'Actualiza el contexto y el color. Tus conversaciones y avances se conservan.' : 'Cuéntanos qué quieres explorar. El nombre y el reto son obligatorios.';
  el('save-project').textContent = edit ? 'Guardar cambios' : 'Crear cuaderno';
  el<HTMLTextAreaElement>('context-question').required = !edit;
  el('question-required').textContent = edit ? 'Contexto inicial' : 'Obligatorio';
  el<HTMLDetailsElement>('more-project-details').open = !!(edit && (activeState!.context?.hypothesis || activeState!.context?.acceptance_criteria || activeState!.context?.ambition));
  el('project-danger').hidden = !edit; el('delete-confirm').hidden = true;
  showError(); setSidebar(false); syncControls(); updatePreview(); el<HTMLDialogElement>('project-dialog').showModal();
}
for (const id of ['new-notebook', 'home-new-project', 'empty-new-project']) el(id).addEventListener('click', () => openProjectForm());
el('edit-project').addEventListener('click', () => { openProjectForm(true); });
const advanceNames: Record<Advance['kind'], string> = { decision: 'Decisión', finding: 'Hallazgo', hypothesis: 'Hipótesis', next_step: 'Próximo paso', other: 'Otro' };

function sharingError(message = '') {
  el('sharing-error').textContent = message; el('sharing-error').hidden = !message;
}

function renderSharingDialog() {
  const owner = activeAccess?.role === 'owner';
  el('sharing-invite-form').hidden = !owner;
  el('sharing-dialog-title').textContent = activeState ? `Compartir “${activeState.notebook_id}”` : 'Compartir proyecto';
  const people = el('sharing-people'); people.replaceChildren();
  const visible = sharedMembers.filter(member => member.status !== 'pending');
  el('sharing-people-count').textContent = `${visible.length} ${visible.length === 1 ? 'persona' : 'personas'}`;
  for (const member of sharedMembers) {
    const row = document.createElement('div'); row.className = 'sharing-person';
    const avatar = document.createElement('span'); avatar.className = 'sharing-avatar'; avatar.textContent = initialsOf(member.display_name); avatar.style.background = memberTone({ id: member.user_id || member.id || member.username, name: member.display_name, role: member.role });
    const identity = document.createElement('span'); identity.className = 'sharing-identity';
    const name = document.createElement('strong'); name.textContent = `${member.display_name}${member.user_id === account?.id ? ' (tú)' : ''}`;
    const username = document.createElement('small'); username.textContent = `@${member.username}${member.status === 'pending' ? ' · invitación pendiente' : ''}`;
    identity.append(name, username); row.append(avatar, identity);
    if (member.role === 'owner') {
      const role = document.createElement('span'); role.className = 'sharing-role'; role.textContent = 'Propietario'; row.append(role);
    } else if (owner && member.status === 'pending') {
      const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'sharing-remove'; cancel.textContent = 'Cancelar';
      cancel.addEventListener('click', async () => { try { await api(`/sharing/invitations/${member.id}`, { method: 'DELETE' }); await refreshSharing(); } catch (error) { sharingError((error as Error).message); } }); row.append(cancel);
    } else if (owner) {
      const role = document.createElement('select'); role.className = 'sharing-role-select'; role.ariaLabel = `Permiso de ${member.display_name}`;
      role.add(new Option('Puede ver', 'viewer')); role.add(new Option('Puede editar', 'editor')); role.value = member.role;
      role.addEventListener('change', async () => { try { await api(`/projects/${activeAccess!.project_id}/members/${member.user_id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role: role.value }) }); member.role = role.value as MemberRole; renderMembers(); showToast('success', 'Permiso actualizado', `${member.display_name} ahora ${role.value === 'editor' ? 'puede editar' : 'puede ver'}.`); } catch (error) { role.value = member.role; sharingError((error as Error).message); } });
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'sharing-remove'; remove.textContent = 'Quitar';
      remove.addEventListener('click', async () => { try { await api(`/projects/${activeAccess!.project_id}/members/${member.user_id}`, { method: 'DELETE' }); await refreshSharing(); } catch (error) { sharingError((error as Error).message); } });
      row.append(role, remove);
    } else {
      const role = document.createElement('span'); role.className = 'sharing-role'; role.textContent = member.role === 'editor' ? 'Puede editar' : 'Puede ver'; row.append(role);
    }
    people.append(row);
  }
  const list = el('sharing-advances'); list.replaceChildren();
  if (!advances.length) { const empty = document.createElement('p'); empty.className = 'sharing-empty'; empty.textContent = 'Todavía no hay avances compartidos.'; list.append(empty); }
  const canEdit = !!activeAccess && activeAccess.role !== 'viewer';
  for (const advance of advances) {
    const item = document.createElement('article'); item.className = 'shared-advance';
    const head = document.createElement('div'); head.className = 'shared-advance-head';
    const meta = document.createElement('p'); meta.textContent = `${advanceNames[advance.kind]} · ${advance.author_name}${advance.version > 1 ? ' · corregido' : ''}`;
    head.append(meta); item.append(head);
    if (canEdit && editingAdvanceId === advance.id) { item.append(advanceEditor(advance)); list.append(item); continue; }
    if (canEdit) {
      const actions = document.createElement('div'); actions.className = 'shared-advance-actions';
      if (retiringAdvanceId === advance.id) {
        const confirm = advanceAction('Retirar del contexto', 'danger', () => retireAdvance(advance));
        const keep = advanceAction('No', '', () => { retiringAdvanceId = null; renderSharingDialog(); });
        actions.append(confirm, keep); requestAnimationFrame(() => keep.focus());
      } else {
        actions.append(
          advanceAction('Corregir', '', () => { editingAdvanceId = advance.id; retiringAdvanceId = null; renderSharingDialog(); }),
          advanceAction('Retirar', '', () => { retiringAdvanceId = advance.id; editingAdvanceId = null; renderSharingDialog(); }),
        );
      }
      head.append(actions);
    }
    const content = document.createElement('p'); content.textContent = advance.content; item.append(content); list.append(item);
  }
  el('advance-form').hidden = activeAccess?.role === 'viewer';
  el('leave-project').hidden = !activeAccess || activeAccess.role === 'owner';
}

function advanceAction(label: string, tone: string, onClick: () => void) {
  const button = document.createElement('button'); button.type = 'button'; button.className = `shared-advance-action${tone ? ` ${tone}` : ''}`;
  button.textContent = label; button.addEventListener('click', onClick); return button;
}

/** Corrige un avance en su lugar; la version evita pisar la correccion de otra persona. */
function advanceEditor(advance: Advance) {
  const form = document.createElement('form'); form.className = 'shared-advance-editor';
  const kind = document.createElement('select'); kind.ariaLabel = 'Tipo de avance';
  for (const [value, label] of Object.entries(advanceNames)) kind.add(new Option(label, value));
  kind.value = advance.kind;
  const text = document.createElement('textarea'); text.required = true; text.maxLength = 1500; text.rows = 3; text.value = advance.content; text.ariaLabel = 'Texto del avance';
  const actions = document.createElement('div'); actions.className = 'shared-advance-actions';
  const cancel = advanceAction('Cancelar', '', () => { editingAdvanceId = null; advanceConflictId = null; renderSharingDialog(); });
  const save = document.createElement('button'); save.type = 'submit'; save.className = 'button primary'; save.textContent = 'Guardar corrección';
  actions.append(cancel, save);
  if (advanceConflictId === advance.id) {
    const current = document.createElement('p'); current.className = 'shared-advance-current';
    current.textContent = `Versión vigente (${advanceNames[advance.kind]}): ${advance.content}`; form.append(current);
  }
  form.append(kind, text, actions);
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (!activeAccess) return;
    const content = text.value.trim(); if (!content) { text.focus(); return; }
    save.disabled = true; sharingError();
    try {
      const saved = await api<Advance>(`/projects/${activeAccess.project_id}/advances/${advance.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content, kind: kind.value, version: advance.version }) });
      advances = advances.map(item => item.id === saved.id ? saved : item); editingAdvanceId = null; advanceConflictId = null; renderSharingDialog();
      showToast('success', 'Avance corregido', 'Los agentes del proyecto usarán la versión nueva.');
    } catch (error) {
      save.disabled = false;
      if (error instanceof ApiError && (error.status === 409 || error.status === 404)) {
        // Se recarga la lista pero el editor conserva lo que la persona escribio.
        const draft = text.value; const draftKind = kind.value; advanceConflictId = advance.id;
        await refreshSharing().catch(() => undefined);
        if (!advances.some(item => item.id === advance.id)) editingAdvanceId = null;
        else { const reopened = el('sharing-advances').querySelector<HTMLFormElement>('.shared-advance-editor'); if (reopened) { reopened.querySelector('textarea')!.value = draft; reopened.querySelector('select')!.value = draftKind; } }
      }
      sharingError((error as Error).message);
    }
  });
  requestAnimationFrame(() => text.focus());
  return form;
}

async function retireAdvance(advance: Advance) {
  if (!activeAccess) return; sharingError();
  try {
    await api(`/projects/${activeAccess.project_id}/advances/${advance.id}`, { method: 'DELETE' });
    advances = advances.filter(item => item.id !== advance.id); retiringAdvanceId = null; renderSharingDialog(); el('advance-content').focus();
    showToast('warning', 'Avance retirado', 'Ya no forma parte del contexto de los agentes.');
  } catch (error) { retiringAdvanceId = null; await refreshSharing().catch(() => undefined); sharingError((error as Error).message); }
}

async function refreshSharing() {
  if (!activeAccess) return;
  sharedMembers = await api<SharingMember[]>(`/projects/${activeAccess.project_id}/members`);
  const data = await api<{ advances: Advance[] }>(`/notebooks/${activeAccess.project_id}`);
  advances = data.advances || []; renderMembers(); renderSharingDialog();
}

el('share-project').addEventListener('click', () => {
  if (!activeState || !activeAccess || loadingNotebook) return;
  editingAdvanceId = null; retiringAdvanceId = null; advanceConflictId = null; sharingError(); renderSharingDialog(); el<HTMLDialogElement>('sharing-dialog').showModal();
});
el('close-sharing').addEventListener('click', () => el<HTMLDialogElement>('sharing-dialog').close());
el('sharing-invite-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!activeAccess || activeAccess.role !== 'owner') return;
  const username = el<HTMLInputElement>('sharing-username').value.trim(); if (!username) return;
  sharingError();
  try {
    await api(`/projects/${activeAccess.project_id}/invitations`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, role: el<HTMLSelectElement>('sharing-role').value }) });
    el<HTMLInputElement>('sharing-username').value = ''; await refreshSharing(); showToast('success', 'Invitación enviada', `@${username} la verá en su campanita.`);
  } catch (error) { sharingError((error as Error).message); }
});
el('advance-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!activeAccess || activeAccess.role === 'viewer') return;
  const content = el<HTMLTextAreaElement>('advance-content').value.trim(); if (!content) return;
  try {
    const saved = await api<Advance>(`/projects/${activeAccess.project_id}/advances`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content, kind: el<HTMLSelectElement>('advance-kind').value }) });
    advances.push(saved); el<HTMLTextAreaElement>('advance-content').value = ''; renderSharingDialog(); showToast('success', 'Avance compartido', 'Los agentes del proyecto recibirán este contexto.');
  } catch (error) { sharingError((error as Error).message); }
});
el('leave-project').addEventListener('click', async () => {
  if (!activeAccess || activeAccess.role === 'owner') return;
  try { await api(`/projects/${activeAccess.project_id}/leave`, { method: 'POST' }); el<HTMLDialogElement>('sharing-dialog').close(); activeState = null; activeAccess = null; await refreshNotebooks(); showHome(); showToast('warning', 'Proyecto retirado', 'Ya no aparece entre tus proyectos.'); }
  catch (error) { sharingError((error as Error).message); }
});
el('notebook-name').addEventListener('input', () => { updatePreview(); if (el<HTMLInputElement>('notebook-name').value.trim()) setFieldError('notebook-name', ''); });
el('context-question').addEventListener('input', () => { if (el<HTMLTextAreaElement>('context-question').value.trim()) setFieldError('context-question', ''); });
el('initial-stage').addEventListener('change', updatePreview);
el('notebook-form').querySelectorAll('input[name="notebook-color"]').forEach(input => input.addEventListener('change', updatePreview));
el('cancel-notebook').addEventListener('click', () => { el<HTMLDialogElement>('project-dialog').close(); });
messageInput.addEventListener('input', () => { fitMessageInput(); syncControls(); });
expandMessage.addEventListener('click', () => { messageExpanded = !messageExpanded; fitMessageInput(); messageInput.focus(); });
window.addEventListener('resize', fitMessageInput);
fitMessageInput();
messageInput.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); el<HTMLFormElement>('chat-form').requestSubmit(); } });
el<HTMLFormElement>('chat-form').addEventListener('submit', sendMessage);
el<HTMLFormElement>('notebook-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy || loadingNotebook) return;
  if (!validateProjectForm()) return;
  const name = el<HTMLInputElement>('notebook-name').value.trim(); if (!name) return;
  const context = Object.fromEntries(Object.keys(contextLabels).map(key => [key, el<HTMLTextAreaElement>(`context-${key}`).value.trim()])) as Context;
  const color = selectedColor();
  const edit = editingProject;
  loadingNotebook = true; syncControls();
  try {
    const state = await api<State>(edit ? `/notebooks/${encodeURIComponent(activeAccess?.project_id || name)}/profile` : '/notebooks', { method: edit ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(edit ? { context, color } : { notebook_id: name, stage: Number(el<HTMLSelectElement>('initial-stage').value), context, color }) });
    el<HTMLDialogElement>('project-dialog').close(); el<HTMLInputElement>('notebook-name').value = '';
    await refreshNotebooks();
    if (edit) { activeState = state; updateHeader(); }
    else await loadNotebook(state.notebook_id);
    showToast('success', edit ? 'Cuaderno actualizado' : 'Cuaderno creado', edit ? 'Tus cambios de contexto y color quedaron guardados.' : `${state.notebook_id} ya está listo para trabajar.`);
  } catch (error) { showError((error as Error).message); }
  finally { loadingNotebook = false; syncControls(); }
});
el('delete-notebook').addEventListener('click', () => { if (!busy) el('delete-confirm').hidden = false; });
el('cancel-delete').addEventListener('click', () => { el('delete-confirm').hidden = true; });
el('confirm-delete').addEventListener('click', async () => {
  if (busy || !activeState) return;
  loadingNotebook = true; syncControls();
  try {
    await api(`/notebooks/${encodeURIComponent(activeAccess?.project_id || activeState.notebook_id)}`, { method: 'DELETE' });
    activeState = null; activeAccess = null; sharedMembers = []; advances = []; localStorage.removeItem(notebookStorageKey()); await refreshNotebooks();
    el<HTMLDialogElement>('project-dialog').close();
    el('messages').replaceChildren(); resetGraph(); showHome();
    el('delete-confirm').hidden = true;
    showToast('warning', 'Cuaderno eliminado', 'El cuaderno y su contenido ya no aparecen en Hilo.');
  } catch (error) { showError((error as Error).message); }
  finally { loadingNotebook = false; syncControls(); }
});

function noteAuthor(note: Note): Member {
  // Sin autor guardado (modo sin cuentas o nota aun no reclamada) la nota es de la
  // cuenta duena del almacenamiento, que es la que esta viendo el cuaderno.
  if (!note.author_id || note.author_id === account?.id) return { id: account?.id || '', name: profileName(), role: 'owner' };
  return { id: note.author_id, name: note.author_name || 'Otra persona', role: 'editor' };
}

function renderNotes() {
  selectedExcerpt = '';
  const wall = el('notes-stack'); wall.replaceChildren();
  el('notes-count').textContent = String(notes.length);
  const readOnly = activeAccess?.role === 'viewer';
  el('selection-hint').textContent = readOnly ? 'Puedes leer los post-its compartidos. Tu permiso es de solo lectura.' : 'Selecciona un fragmento del chat o escribe una nota.';
  if (!notes.length) {
    const empty = document.createElement('div'); empty.className = 'notes-empty';
    const paper = document.createElement('div'); paper.className = 'notes-empty-paper'; paper.setAttribute('aria-hidden', 'true');
    const text = document.createElement('p'); text.innerHTML = '<strong>Nada anotado todavía.</strong> Escribe una nota o guarda un fragmento del chat.';
    empty.append(paper, text); wall.append(empty);
  }
  const dates = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short' });
  // «18 sept» en lugar de «18 de sept.»: en una nota angosta cada caracter cuenta.
  const shortDate = (value: string) => dates.formatToParts(new Date(value))
    .filter(part => part.type === 'day' || part.type === 'month').map(part => part.value.replace('.', '')).join(' ');
  for (const note of notes) {
    const author = noteAuthor(note);
    const card = document.createElement('article'); card.className = 'sticky-note'; card.dataset.noteColor = note.color; card.dataset.noteId = note.id;
    card.setAttribute('aria-labelledby', `note-title-${note.id}`);

    const top = document.createElement('div'); top.className = 'note-top';
    const category = document.createElement('span'); category.className = 'note-category'; category.textContent = categoryNames[note.category];
    const actions = document.createElement('div'); actions.className = 'note-actions';
    const edit = document.createElement('button'); edit.type = 'button'; edit.className = 'note-action'; edit.innerHTML = icon('edit'); edit.setAttribute('aria-label', `Editar post-it: ${note.title}`); edit.addEventListener('click', () => openNote(note));
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'note-action'; remove.innerHTML = icon('trash'); remove.setAttribute('aria-label', `Eliminar post-it: ${note.title}`);
    if (!readOnly) actions.append(edit, remove);
    const label = document.createElement('span'); label.className = 'note-label'; label.append(category);
    if (note.source_text) {
      const fromChat = document.createElement('span'); fromChat.className = 'note-from-chat'; fromChat.title = 'Guardado desde el chat';
      fromChat.innerHTML = `${icon('quote')}<span class="sr-only">Guardado desde el chat</span>`;
      label.append(fromChat);
    }
    top.append(label, actions);


    const title = document.createElement('h3'); title.id = `note-title-${note.id}`; title.textContent = note.title;
    const body = document.createElement('p'); body.className = 'note-body'; body.textContent = note.text;

    const footer = document.createElement('div'); footer.className = 'note-footer';
    const who = document.createElement('span'); who.className = 'note-author'; who.title = `Creado por ${author.name}`;
    const avatar = document.createElement('span'); avatar.className = 'note-avatar'; avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = initialsOf(author.name); avatar.style.background = memberTone(author);
    const name = document.createElement('span'); name.className = 'note-author-name';
    name.textContent = author.name.split(/\s+/)[0] || author.name;
    const whoText = document.createElement('span'); whoText.className = 'sr-only'; whoText.textContent = `Creado por ${author.name}`;
    who.append(avatar, name, whoText);
    const meta = document.createElement('span'); meta.className = 'note-meta';
    const date = document.createElement('time'); date.dateTime = note.created_at; date.textContent = shortDate(note.created_at);
    date.title = dates.format(new Date(note.created_at));
    meta.append(date); top.insertBefore(meta, actions); footer.append(who);

    const confirmation = document.createElement('div'); confirmation.className = 'note-delete-confirm'; confirmation.hidden = true;
    const prompt = document.createElement('p'); prompt.textContent = '¿Eliminar este post-it?';
    const yes = document.createElement('button'); yes.type = 'button'; yes.className = 'note-text-button'; yes.textContent = 'Eliminar';
    const no = document.createElement('button'); no.type = 'button'; no.className = 'note-text-button'; no.textContent = 'Cancelar';
    no.addEventListener('click', () => { confirmation.hidden = true; remove.focus(); });
    remove.addEventListener('click', () => { confirmation.hidden = false; no.focus(); });
    yes.addEventListener('click', async () => {
      if (!activeState || loadingNotebook || noteSaving) return;
      const notebook = activeAccess?.project_id || activeState.notebook_id; noteSaving = true; yes.disabled = no.disabled = true; syncControls();
      try { await api(`/notebooks/${encodeURIComponent(notebook)}/notes/${note.id}`, { method: 'DELETE' }); notes = notes.filter(item => item.id !== note.id); renderNotes(); el('new-note').focus(); showToast('warning', 'Post-it eliminado', `“${note.title}” se quitó del cuaderno.`); }
      catch (error) { showError((error as Error).message); yes.disabled = no.disabled = false; }
      finally { noteSaving = false; syncControls(); }
    });
    confirmation.append(prompt, yes, no);
    card.append(top, title, body, footer, confirmation); wall.append(card);
  }
}

function openNote(note?: Note, excerpt = '') {
  if (!activeState || loadingNotebook || noteSaving || activeAccess?.role === 'viewer') return;
  if (excerpt.length > 3000) { showError('Elige un fragmento más corto: cada post-it admite hasta 3000 caracteres.'); return; }
  editingNote = note || null; noteSource = note?.source_text || excerpt;
  el('note-dialog-title').textContent = note ? 'Editar post-it' : 'Nuevo post-it';
  el<HTMLInputElement>('note-title').value = note?.title || '';
  el<HTMLTextAreaElement>('note-text').value = note?.text || excerpt;
  el('note-form').querySelector<HTMLInputElement>(`input[name="note-category"][value="${note?.category || 'idea'}"]`)!.checked = true;
  // La hoja firma con quien escribio la nota; una nota nueva la firma la cuenta actual.
  const signer = note ? noteAuthor(note) : { id: account?.id || '', name: profileName(), role: 'owner' as const };
  el('note-sign-avatar').textContent = initialsOf(signer.name);
  el('note-sign-avatar').style.background = memberTone(signer);
  el('note-sign-name').textContent = signer.name;
  el('note-sign-date').textContent = note
    ? `· ${new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'long' }).format(new Date(note.created_at))}`
    : '· ahora';
  el<HTMLInputElement>('note-form').querySelector<HTMLInputElement>(`input[name="note-color"][value="${note?.color || 'yellow'}"]`)!.checked = true;
  el('note-source').hidden = !noteSource; el<HTMLDetailsElement>('note-source').open = false; el('note-source-text').textContent = noteSource;
  el('note-error').hidden = true;
  for (const id of ['note-title', 'note-text']) el(id).removeAttribute('aria-invalid');
  el<HTMLDialogElement>('note-dialog').showModal();
  updateNoteColor(); el<HTMLInputElement>('note-title').focus();
}

function updateNoteColor() {
  el('note-dialog').dataset.noteColor = document.querySelector<HTMLInputElement>('input[name="note-color"]:checked')!.value;
}
el('new-note').addEventListener('click', () => openNote());
el('cancel-note').addEventListener('click', () => { if (!noteSaving) el<HTMLDialogElement>('note-dialog').close(); });
el('note-dialog').addEventListener('cancel', event => { if (noteSaving) event.preventDefault(); });
el('note-form').addEventListener('change', updateNoteColor);
el('note-form').addEventListener('input', () => {
  for (const id of ['note-title', 'note-text']) if (el<HTMLInputElement>(id).value.trim()) el(id).removeAttribute('aria-invalid');
  if (el<HTMLInputElement>('note-title').value.trim() && el<HTMLTextAreaElement>('note-text').value.trim()) el('note-error').hidden = true;
});
const BOARD_KEY = 'hilo-tablero';
const BOARD_TOOLS = ['notes', 'agents'] as const;
type BoardTool = typeof BOARD_TOOLS[number];
const boardTools = new Set<BoardTool>(readBoard().slice(-1));

function readBoard(): BoardTool[] {
  // Por defecto el tablero muestra solo el chat.
  try {
    const saved = JSON.parse(localStorage.getItem(BOARD_KEY) || '[]');
    return Array.isArray(saved) ? saved.filter((tool): tool is BoardTool => BOARD_TOOLS.includes(tool)) : [];
  } catch { return []; }
}

function renderBoard() {
  const workspace = el('project-workspace');
  workspace.dataset.boardCount = String(boardTools.size);
  workspace.classList.toggle('board-primary-tree', currentView === 'tree');
  const treeToggle = el<HTMLButtonElement>('open-problem-tree');
  treeToggle.setAttribute('aria-pressed', String(currentView === 'tree'));
  treeToggle.title = currentView === 'tree' ? 'Volver al chat' : 'Mostrar el árbol de problemas';
  for (const tool of BOARD_TOOLS) {
    const active = boardTools.has(tool);
    workspace.classList.toggle(`board-has-${tool}`, active);
    const toggle = document.querySelector<HTMLButtonElement>(`[data-board-tool="${tool}"]`);
    if (toggle) {
      toggle.setAttribute('aria-pressed', String(active));
      const name = toggle.textContent?.trim() || tool;
      toggle.title = active ? `Quitar ${name} del tablero` : `Agregar ${name} al tablero`;
    }
  }
}

function setBoardTool(tool: BoardTool, active: boolean) {
  boardTools.clear();
  if (active) boardTools.add(tool);
  // Sin almacenamiento disponible la eleccion vale para esta pestana.
  try { localStorage.setItem(BOARD_KEY, JSON.stringify([...boardTools])); } catch { /* sin persistencia */ }
  renderBoard();
}

document.querySelectorAll<HTMLButtonElement>('[data-board-tool]').forEach(toggle => {
  toggle.addEventListener('click', () => {
    const tool = toggle.dataset.boardTool as BoardTool;
    setBoardTool(tool, !boardTools.has(tool));
  });
});
renderBoard();

document.addEventListener('selectionchange', () => {
  if (el<HTMLDialogElement>('note-dialog').open) return;
  const selection = window.getSelection();
  const anchor = selection?.anchorNode; const focus = selection?.focusNode;
  if (anchor && focus && messageBox.contains(anchor) && messageBox.contains(focus)) {
    const contents = [...messageBox.querySelectorAll('.turn-content')];
    if (contents.some(content => content.contains(anchor)) && contents.some(content => content.contains(focus))) {
      selectedExcerpt = selection!.toString().trim();
      el('selection-hint').textContent = selectedExcerpt.length > 3000 ? 'Selecciona menos texto: máximo 3000 caracteres.' : selectedExcerpt ? `${selectedExcerpt.length} caracteres seleccionados. Listos para guardar.` : 'Selecciona un fragmento del chat o escribe una nota.';
      syncControls();
    }
  }
});
el('save-selection').addEventListener('mousedown', event => event.preventDefault());
el('save-selection').addEventListener('click', () => { if (selectedExcerpt) openNote(undefined, selectedExcerpt); });
el('note-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!activeState || loadingNotebook || noteSaving) return;
  const title = el<HTMLInputElement>('note-title').value.trim(); const text = el<HTMLTextAreaElement>('note-text').value.trim();
  if (!title || !text) {
    el('note-title').setAttribute('aria-invalid', String(!title)); el('note-text').setAttribute('aria-invalid', String(!text));
    el('note-error').textContent = 'Escribe un título y un texto para guardar el post-it.'; el('note-error').hidden = false; (!title ? el('note-title') : el('note-text')).focus(); return;
  }
  const notebook = activeAccess?.project_id || activeState.notebook_id; const noteId = editingNote?.id;
  noteSaving = true; el('note-form').querySelectorAll<HTMLInputElement>('button, input, select, textarea').forEach(node => { node.disabled = true; }); syncControls();
  try {
    const saved = await api<Note>(`/notebooks/${encodeURIComponent(notebook)}/notes${noteId ? `/${noteId}` : ''}`, { method: noteId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, text, category: document.querySelector<HTMLInputElement>('input[name="note-category"]:checked')?.value || 'idea', color: document.querySelector<HTMLInputElement>('input[name="note-color"]:checked')!.value, source_text: noteSource, base_updated_at: editingNote?.updated_at ?? null }) });
    notes = noteId ? notes.map(note => note.id === noteId ? saved : note) : [saved, ...notes]; renderNotes(); selectedExcerpt = ''; el<HTMLDialogElement>('note-dialog').close();
    setBoardTool('notes', true);
    const savedCard = el('notes-stack').querySelector<HTMLElement>(`[data-note-id="${saved.id}"]`);
    savedCard?.scrollIntoView({ block: 'nearest' }); savedCard?.querySelector('button')?.focus();
    showToast('success', noteId ? 'Post-it actualizado' : 'Post-it guardado', `“${saved.title}” quedó en el tablero del cuaderno.`);
  } catch (error) {
    let message = (error as Error).message;
    if (error instanceof ApiError && error.status === 409 && error.current) {
      // Lo escrito se queda en la hoja; la pared muestra ya la version de la otra persona.
      const current = error.current as Note;
      notes = notes.map(note => note.id === current.id ? current : note); editingNote = current; renderNotes();
      const excerpt = current.text.length > 160 ? `${current.text.slice(0, 160)}…` : current.text;
      message = `${message} Ahora dice: “${current.title}: ${excerpt}”. Si guardas otra vez, tu texto la reemplaza.`;
    }
    el('note-error').textContent = message; el('note-error').hidden = false;
  }
  finally { noteSaving = false; el('note-form').querySelectorAll<HTMLInputElement>('button, input, select, textarea').forEach(node => { node.disabled = false; }); syncControls(); }
});

function renderTools() {
  const grid = el('tools-grid'); grid.replaceChildren();
  for (const tool of tools) {
    const where = stages.filter(stage => stage.tools.includes(tool.id));
    const card = document.createElement('button'); card.type = 'button'; card.className = 'tool-card';
    card.setAttribute('aria-label', `Abrir la ficha ${tool.name}`);
    const head = document.createElement('div'); head.className = 'tool-card-head';
    const name = document.createElement('h3'); name.textContent = tool.name;
    const badge = document.createElement('span'); badge.className = 'tool-method';
    badge.textContent = methodologyNames[tool.methodology] || tool.methodology;
    head.append(name, badge);
    const place = document.createElement('p'); place.className = 'tool-stages';
    place.textContent = where.length
      ? where.map(stage => `Etapa ${stage.id} \u00b7 ${stage.name}`).join(' \u00b7 ')
      : 'Sin etapa asignada en la ruta';
    const fields = document.createElement('p'); fields.className = 'tool-fields';
    fields.textContent = tool.template_fields.length
      ? `${tool.template_fields.length} ${tool.template_fields.length === 1 ? 'campo verificable' : 'campos verificables'}`
      : 'Solo orientaci\u00f3n; no guarda campos';
    card.append(head, place, fields);
    card.addEventListener('click', () => { void openTool(tool); });
    grid.append(card);
  }
  el('tools-count').textContent = String(tools.length);
  const withFields = tools.filter(tool => tool.template_fields.length).length;
  el('tools-summary').textContent = `${tools.length} fichas cargadas \u00b7 ${withFields} pueden guardar datos verificados`;
}

async function openTool(tool: Tool) {
  const where = stages.filter(stage => stage.tools.includes(tool.id));
  el('tool-dialog-title').textContent = tool.name;
  el('tool-dialog-meta').textContent = `${methodologyNames[tool.methodology] || tool.methodology}${where.length ? ` \u00b7 ${where.map(stage => `Etapa ${stage.id}`).join(', ')}` : ''}`;
  el('tool-dialog-body').textContent = 'Cargando la ficha\u2026';
  el<HTMLDialogElement>('tool-dialog').showModal();
  try {
    const card = await api<{ content: string }>(`/tools/${encodeURIComponent(tool.id)}`);
    el('tool-dialog-body').innerHTML = safeMarkdown(card.content);
  } catch (error) {
    el('tool-dialog-body').textContent = (error as Error).message;
  }
}

function profileName(): string {
  return account?.display_name || 'Tu cuenta';
}

const initialsOf = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2)
  .map(word => word[0]).join('').toLocaleUpperCase('es');

type Member = { id: string; name: string; role: MemberRole };
const memberRoles: Record<MemberRole, string> = { owner: 'propietario', editor: 'puede editar', viewer: 'puede ver' };
const MEMBERS_SHOWN = 4;
// Tonos con contraste AA sobre texto blanco. La cuenta propia conserva el azul de Hilo;
// las demas reciben un tono fijo derivado de su id, estable entre sesiones.
const MEMBER_TONES = ['#2f7a5a', '#8a4fb8', '#a85616', '#b2405c', '#2b7a8c'];
function memberTone(member: Member): string {
  if (member.id === account?.id) return '#2a55bc';
  let hash = 0;
  for (const char of member.id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return MEMBER_TONES[hash % MEMBER_TONES.length];
}

function projectMembers(): Member[] {
  return sharedMembers
    .filter(member => member.status !== 'pending')
    .map(member => ({ id: member.user_id || member.id || '', name: member.display_name, role: member.role }));
}

function renderMembers() {
  const list = el('project-members'); list.replaceChildren();
  const members = projectMembers();
  for (const member of members.slice(0, MEMBERS_SHOWN)) {
    const item = document.createElement('li'); item.className = 'project-member';
    const label = `${member.name}${member.id === account?.id ? ' (tú)' : ''} · ${memberRoles[member.role]}`;
    item.title = label;
    const avatar = document.createElement('span'); avatar.className = 'project-member-avatar';
    avatar.setAttribute('aria-hidden', 'true'); avatar.textContent = initialsOf(member.name);
    avatar.style.background = memberTone(member);
    const text = document.createElement('span'); text.className = 'sr-only'; text.textContent = label;
    item.append(avatar, text); list.append(item);
  }
  if (members.length > MEMBERS_SHOWN) {
    const more = document.createElement('li'); more.className = 'project-member project-member-more';
    more.textContent = `+${members.length - MEMBERS_SHOWN}`;
    more.title = `${members.length - MEMBERS_SHOWN} personas más con acceso`;
    list.append(more);
  }
  list.setAttribute('aria-label', members.length === 1 ? '1 persona con acceso' : `${members.length} personas con acceso`);
  list.hidden = !members.length;
}

function renderProfile() {
  const name = profileName();
  el('profile-name').textContent = name;
  el('profile-initials').textContent = initialsOf(name);
  renderMembers();
  document.querySelectorAll('.user-turn .turn-avatar').forEach(avatar => { avatar.textContent = el('profile-initials').textContent; });
  el('profile').setAttribute('aria-label', `Abrir tu cuenta: ${name}`);
  el('account-menu-name').textContent = name;
  el('account-menu-username').textContent = account ? `@${account.username}` : '';
  el('account-menu-initials').textContent = el('profile-initials').textContent;
}

function setAccountMenu(open: boolean) {
  el('account-menu').hidden = !open;
  el('profile').setAttribute('aria-expanded', String(open));
  if (!open) el<HTMLDetailsElement>('account-theme').open = false;
}

el('go-tools').addEventListener('click', () => { if (!busy && !loadingNotebook) showTools(); });
el('see-all-projects').addEventListener('click', () => { void navigateHome(); });
el('sidebar-projects').addEventListener('click', () => { void navigateHome(); });
el('sidebar-search').addEventListener('click', async () => {
  if (busy || loadingNotebook) return;
  await navigateHome();
  el<HTMLInputElement>('project-search').focus();
});
el('close-tool').addEventListener('click', () => { el<HTMLDialogElement>('tool-dialog').close(); });
el('profile').addEventListener('click', () => {
  const open = el('account-menu').hidden;
  setSidebar(false);
  for (const id of ['header-help', 'header-notifications']) el<HTMLDetailsElement>(id).open = false;
  setAccountMenu(open);
});
function openAccountProfile(settings = false) {
  setAccountMenu(false);
  el('profile-dialog-title').textContent = settings ? 'Configuración de la cuenta' : 'Tu perfil';
  el('profile-dialog-description').textContent = settings
    ? 'Administra el nombre de tu cuenta local. Tus proyectos permanecen vinculados a esta cuenta.'
    : 'Tu nombre aparecerá en tus mensajes. Tus proyectos están vinculados a esta cuenta local.';
  el('account-settings-username').hidden = !settings;
  el('account-settings-username').textContent = `Usuario: ${account?.username || ''}`;
  el<HTMLInputElement>('profile-input').value = profileName();
  el('profile-error').hidden = true; el('profile-input').removeAttribute('aria-invalid');
  el<HTMLDialogElement>('profile-dialog').showModal(); el<HTMLInputElement>('profile-input').select();
}
el('cancel-profile').addEventListener('click', () => { el<HTMLDialogElement>('profile-dialog').close(); });
el('profile-form').addEventListener('submit', async event => {
  event.preventDefault();
  const value = el<HTMLInputElement>('profile-input').value.trim();
  if (!value) {
    el('profile-error').textContent = 'Escribe un nombre para tu perfil.';
    el('profile-error').hidden = false; el('profile-input').setAttribute('aria-invalid', 'true');
    el('profile-input').focus(); return;
  }
  try {
    account = await api<Account>('/auth/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ display_name: value }) });
    renderProfile(); el<HTMLDialogElement>('profile-dialog').close(); el('profile').focus();
  } catch (error) {
    el('profile-error').textContent = (error as Error).message; el('profile-error').hidden = false;
  }
});
el('account-open-profile').addEventListener('click', () => openAccountProfile());
el('account-open-settings').addEventListener('click', () => openAccountProfile(true));
el('account-quick-guide').addEventListener('click', () => {
  setAccountMenu(false);
  el<HTMLDetailsElement>('header-help').open = true;
  el('header-help').querySelector('summary')!.focus();
});
for (const id of ['header-help', 'header-notifications']) el<HTMLDetailsElement>(id).addEventListener('toggle', () => {
  if (el<HTMLDetailsElement>(id).open) {
    setAccountMenu(false);
    if (id === 'header-notifications') el('toast-region').querySelectorAll<HTMLElement>('.toast').forEach(removeToast);
  }
});
async function endAccountSession() {
  for (const id of ['logout', 'account-switch', 'account-logout']) el<HTMLButtonElement>(id).disabled = true;
  el('account-menu-error').hidden = true;
  try {
    await api('/auth/logout', { method: 'POST' });
    history.replaceState(null, '', '#inicio');
    window.location.reload();
  }
  catch (error) {
    for (const id of ['profile-error', 'account-menu-error']) { el(id).textContent = (error as Error).message; el(id).hidden = false; }
    for (const id of ['logout', 'account-switch', 'account-logout']) el<HTMLButtonElement>(id).disabled = false;
  }
}
for (const id of ['logout', 'account-switch', 'account-logout']) el(id).addEventListener('click', () => { void endAccountSession(); });

const dayKey = (value: string | Date) => {
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '';
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
};

async function loadActivity() {
  const version = ++activityVersion;
  activityReady = false; activityFailed = false; renderCalendar();
  try {
    const histories = await Promise.all(notebooks.map(async item => ({
      id: item.notebook_id,
      turns: (await api<{ turns: Turn[] }>(`/notebooks/${encodeURIComponent(item.project_id)}`)).turns,
    })));
    if (version !== activityVersion) return;
    const next = new Map<string, DayActivity[]>();
    for (const history of histories) {
      for (const turn of history.turns) {
        const key = dayKey(turn.created_at || '');
        if (!key) continue;
        const entries = next.get(key) || [];
        const found = entries.find(entry => entry.notebook === history.id);
        if (found) found.count += 1; else entries.push({ notebook: history.id, count: 1 });
        next.set(key, entries);
      }
    }
    activity = next; activityReady = true;
  } catch {
    // Sin historial no se inventa actividad: el calendario lo dice y queda vacio.
    activity = new Map(); activityReady = true; activityFailed = true;
  }
  if (version === activityVersion) renderCalendar();
}

function renderCalendar() {
  const grid = el('calendar'); grid.replaceChildren();
  const year = calendarCursor.getFullYear(); const month = calendarCursor.getMonth();
  const label = new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' }).format(calendarCursor);
  el('cal-month').textContent = label.charAt(0).toLocaleUpperCase('es') + label.slice(1);
  for (const name of ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']) {
    const head = document.createElement('span'); head.className = 'cal-head'; head.textContent = name; grid.append(head);
  }
  const offset = (new Date(year, month, 1).getDay() + 6) % 7; // la semana empieza en lunes
  for (let blank = 0; blank < offset; blank += 1) {
    const filler = document.createElement('span'); filler.className = 'cal-blank'; grid.append(filler);
  }
  const today = dayKey(new Date());
  let monthTotal = 0;
  for (let day = 1; day <= new Date(year, month + 1, 0).getDate(); day += 1) {
    const key = dayKey(new Date(year, month, day));
    const entries = activity.get(key) || [];
    const dayTasks = tasks.filter(task => localDateKey(new Date(task.due_at)) === key);
    const total = entries.reduce((sum, entry) => sum + entry.count, 0);
    monthTotal += total;
    const cell = document.createElement('button'); cell.type = 'button'; cell.className = 'cal-day';
    const number = document.createElement('span'); number.textContent = String(day); cell.append(number);
    if (key === today) cell.classList.add('today');
    if (total) cell.classList.add('active');
    if (key === selectedDay) { cell.classList.add('picked'); cell.setAttribute('aria-pressed', 'true'); } else cell.setAttribute('aria-pressed', 'false');
    const dots = document.createElement('span'); dots.className = 'cal-dots';
    if (dayTasks.length) { const dot = document.createElement('i'); dot.className = 'cal-task-dot'; dot.dataset.tone = dayTasks.some(task => !task.completed) ? taskTiming(dayTasks.find(task => !task.completed)!).tone : 'done'; dots.append(dot); }
    if (total) { const dot = document.createElement('i'); dot.className = 'cal-activity-dot'; dots.append(dot); }
    dots.setAttribute('aria-hidden', 'true'); cell.append(dots);
    cell.setAttribute('aria-label', `${day} de ${label}: ${dayTasks.length} ${dayTasks.length === 1 ? 'tarea' : 'tareas'}, ${total} ${total === 1 ? 'mensaje' : 'mensajes'}`);
    cell.addEventListener('click', () => { selectedDay = selectedDay === key ? '' : key; renderCalendar(); renderTasks(); });
    grid.append(cell);
  }
  const detail = el('cal-detail');
  const chosen = selectedDay ? activity.get(selectedDay) : undefined;
  if (activityFailed) {
    detail.textContent = 'No se pudo leer el historial de conversaciones. Recarga para volver a intentarlo.';
  } else if (!activityReady && !activity.size) {
    detail.textContent = 'Leyendo la actividad de tus proyectos\u2026';
  } else if (chosen) {
    const date = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'long' }).format(new Date(`${selectedDay}T12:00:00`));
    detail.textContent = `${date}: ${chosen.map(entry => `${entry.count} ${entry.count === 1 ? 'mensaje' : 'mensajes'} en ${entry.notebook}`).join(' \u00b7 ')}`;
  } else if (monthTotal) {
    detail.textContent = `${monthTotal} ${monthTotal === 1 ? 'mensaje' : 'mensajes'} este mes. Elige un d\u00eda marcado para ver el detalle.`;
  } else {
    detail.textContent = 'Sin conversaciones registradas en este mes.';
  }
}

async function loadTasks() {
  taskLoading = true; taskLoadError = ''; renderTasks();
  try { tasks = await api<Task[]>('/tasks'); }
  catch (error) { taskLoadError = (error as Error).message; }
  finally { taskLoading = false; tasksChanged(); }
}

function renderTasks() {
  const list = el('task-list'); list.replaceChildren();
  document.querySelectorAll<HTMLButtonElement>('[data-task-filter]').forEach(button => button.setAttribute('aria-pressed', String(!selectedDay && button.dataset.taskFilter === taskFilter)));
  el('tasks-heading').textContent = selectedDay ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'long' }).format(new Date(`${selectedDay}T12:00:00`)) : 'Tu agenda';
  if (taskLoading || taskLoadError) {
    el('task-status').textContent = taskLoading ? 'Cargando tus tareas…' : taskLoadError;
    if (taskLoadError) { const retry = document.createElement('button'); retry.className = 'button quiet'; retry.textContent = 'Reintentar'; retry.type = 'button'; retry.addEventListener('click', () => { void loadTasks(); }); list.append(retry); } return;
  }
  const today = localDateKey(new Date());
  const filtered = tasks.filter(task => selectedDay ? localDateKey(new Date(task.due_at)) === selectedDay : taskFilter === 'today' ? localDateKey(new Date(task.due_at)) === today : taskFilter === 'upcoming' ? !task.completed : true)
    .sort((a,b) => Number(a.completed)-Number(b.completed) || Date.parse(a.due_at)-Date.parse(b.due_at) || ['high','medium','low'].indexOf(a.priority)-['high','medium','low'].indexOf(b.priority));
  el('task-status').textContent = filtered.length ? `${filtered.length} ${filtered.length === 1 ? 'tarea' : 'tareas'}${taskFilter === 'upcoming' && !selectedDay ? ` ${filtered.length === 1 ? 'pendiente' : 'pendientes'} · primero las más cercanas` : ''}` : '';
  if (!filtered.length) {
    const empty = document.createElement('div'); empty.className = 'tasks-empty';
    const title = document.createElement('h4'); title.textContent = tasks.length ? 'Un espacio libre en tu agenda.' : 'Dale fecha a tu próximo paso.';
    const text = document.createElement('p'); text.textContent = tasks.length ? 'No hay tareas en esta vista. Puedes elegir otra fecha o crear una nueva.' : 'Agrega una tarea con hora e importancia. Aquí verás qué viene primero.';
    empty.append(title,text); list.append(empty);
  }
  for (const task of filtered) {
    const timing = taskTiming(task); const row = document.createElement('article'); row.className = `task-row${task.completed ? ' completed' : ''}`; row.dataset.tone = timing.tone;
    const check = document.createElement('input'); check.type = 'checkbox'; check.checked = task.completed; check.disabled = taskSaving || task.project_role === 'viewer'; check.setAttribute('aria-label', `${task.completed ? 'Reabrir' : 'Completar'} tarea: ${task.title}`);
    check.addEventListener('change', async () => { await saveTask({ ...task, completed: check.checked }); });
    const toggle = document.createElement('label'); toggle.className = 'task-toggle';
    const mark = document.createElement('span'); mark.className = 'task-mark'; mark.innerHTML = icon(task.completed ? 'check' : 'note'); mark.setAttribute('aria-hidden', 'true'); toggle.append(check,mark);
    const body = document.createElement('div'); body.className = 'task-content';
    const title = document.createElement('h4'); title.textContent = task.title;
    const meta = document.createElement('p'); meta.className = 'task-meta';
    const due = new Date(task.due_at); const when = document.createElement('time'); when.dateTime = task.due_at; when.textContent = new Intl.DateTimeFormat('es-CO',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(due);
    const deadline = document.createElement('span'); deadline.className = 'task-deadline'; deadline.textContent = timing.label;
    const priority = document.createElement('span'); priority.className = 'task-priority'; priority.dataset.priority = task.priority; priority.textContent = `Prioridad ${priorityLabels[task.priority].toLocaleLowerCase('es')}`;
    meta.append(when,deadline); body.append(title,meta);
    if (task.notebook_id) { const project = document.createElement('span'); project.className = 'task-project'; project.textContent = task.notebook_id; body.append(project); }
    const edit = document.createElement('button'); edit.type = 'button'; edit.className = 'icon-button'; edit.innerHTML = icon('edit'); edit.setAttribute('aria-label', `Editar tarea: ${task.title}`); edit.disabled = taskSaving || task.project_role === 'viewer'; edit.addEventListener('click', () => openTask(task));
    const status = document.createElement('span'); status.className = 'task-state'; status.textContent = task.completed ? 'Completada' : timing.tone === 'overdue' ? 'Vencida' : 'Pendiente';
    row.append(toggle,body,priority,status,edit); list.append(row);
  }
}

function openTask(task?: Task) {
  if (taskSaving || task?.project_role === 'viewer') return; editingTask = task || null;
  el('task-form').hidden = false; el('task-error').hidden = true;
  el('task-form-title').textContent = task ? 'Editar tarea' : 'Nueva tarea';
  el<HTMLInputElement>('task-title').value = task?.title || '';
  const due = task ? new Date(task.due_at) : new Date();
  el<HTMLInputElement>('task-date').value = task ? localDateKey(due) : selectedDay || localDateKey(due);
  el<HTMLInputElement>('task-time').value = task ? `${String(due.getHours()).padStart(2,'0')}:${String(due.getMinutes()).padStart(2,'0')}` : '17:00';
  el<HTMLSelectElement>('task-priority').value = task?.priority || 'medium';
  const project = el<HTMLSelectElement>('task-project'); project.replaceChildren(new Option('Sin proyecto',''));
  for (const notebook of notebooks.filter(item => item.role !== 'viewer')) project.add(new Option(notebook.notebook_id, notebook.project_id));
  project.value = task?.project_id || '';
  el('task-form').scrollIntoView({block:'nearest',behavior:'smooth'}); el('task-title').focus();
}

async function saveTask(task: Task | Omit<Task,'id'>): Promise<boolean> {
  if (taskSaving) return false; taskSaving = true; renderTasks();
  el('task-form').querySelectorAll<HTMLInputElement>('button,input,select').forEach(node => { node.disabled = true; }); el<HTMLButtonElement>('new-task').disabled = true;
  try {
    const previous = 'id' in task ? tasks.find(item => item.id === task.id) : undefined;
    const saved = await persistTask(task);
    const title = !previous ? 'Tarea creada' : previous.completed !== saved.completed ? (saved.completed ? 'Tarea completada' : 'Tarea reabierta') : 'Tarea actualizada';
    showToast(previous?.completed && !saved.completed ? 'info' : 'success', title, `“${saved.title}” quedó guardada en tu agenda.`);
    return true;
  } catch (error) { showError((error as Error).message); el('task-error').textContent = (error as Error).message; el('task-error').hidden = false; return false; }
  finally { taskSaving = false; el('task-form').querySelectorAll<HTMLInputElement>('button,input,select').forEach(node => { node.disabled = false; }); el<HTMLButtonElement>('new-task').disabled = false; tasksChanged(); }
}
el('new-task').addEventListener('click', () => openTask());
el('cancel-task').addEventListener('click', () => { el('task-form').hidden = true; el('new-task').focus(); });
el('task-form').addEventListener('submit', async event => {
  event.preventDefault(); if (taskSaving) return;
  const title = el<HTMLInputElement>('task-title').value.trim(); const date = el<HTMLInputElement>('task-date').value; const time = el<HTMLInputElement>('task-time').value;
  const due = new Date(`${date}T${time}`);
  if (!title || !date || !time || Number.isNaN(due.getTime())) { el('task-error').textContent = 'Escribe una tarea y elige una fecha y una hora válidas.'; el('task-error').hidden = false; (!title ? el('task-title') : !date ? el('task-date') : el('task-time')).focus(); return; }
  const span = editingTask?.ends_at ? Date.parse(editingTask.ends_at) - Date.parse(editingTask.due_at) : 0;
  const body = { title, kind: editingTask?.kind || 'tarea' as EntryKind, due_at:due.toISOString(), ends_at: span > 0 ? new Date(due.getTime() + span).toISOString() : null, priority:el<HTMLSelectElement>('task-priority').value as Task['priority'], notebook_id:null, project_id:el<HTMLSelectElement>('task-project').value || null, completed:editingTask?.completed || false };
  const ok = await saveTask(editingTask ? {...body,id:editingTask.id} : body);
  if (ok) { el('task-form').hidden = true; taskFilter = 'all'; selectedDay = ''; renderCalendar(); renderTasks(); el('new-task').focus(); }
});
document.querySelectorAll<HTMLButtonElement>('[data-task-filter]').forEach(button => button.addEventListener('click', () => { taskFilter = button.dataset.taskFilter as typeof taskFilter; selectedDay = ''; renderTasks(); renderCalendar(); }));
el('cal-today').addEventListener('click', () => { calendarCursor = new Date(new Date().getFullYear(),new Date().getMonth(),1); selectedDay = ''; taskFilter = 'today'; renderCalendar(); renderTasks(); });
setInterval(() => {
  // No reemplazar controles mientras se navega o escribe dentro de la agenda.
  const agendaHasFocus = el('home-calendar').contains(document.activeElement);
  if (currentView === 'home' && !taskSaving && !agendaHasFocus) { renderCalendar(); renderTasks(); }
},60000);

// ============================================================ Calendario
type CalvMode = 'month' | 'week';
let calvMode: CalvMode = 'month';
let calvCursor = new Date();
let calvSelected = localDateKey(new Date());
const calvHiddenKinds = new Set<EntryKind>();
const calvHiddenProjects = new Set<string>();
let calvEditing: Task | null = null;
let calvSaving = false;
const PERSONAL = '__personal';
const HOUR_PX = 48;
const timeFmt = new Intl.DateTimeFormat('es-CO', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const longDay = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'long' });
const weekdayName = new Intl.DateTimeFormat('es-CO', { weekday: 'long' });
const monthYear = new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' });
const capital = (text: string) => text.charAt(0).toLocaleUpperCase('es') + text.slice(1);
const atMidnight = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());
const addDays = (date: Date, days: number) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
const mondayOf = (date: Date) => addDays(atMidnight(date), -((date.getDay() + 6) % 7));
const fromKey = (key: string) => new Date(`${key}T12:00:00`);

/** Color de identidad: el de la carpeta del proyecto; lo personal va en rosa. */
function entryColor(task: Task): string {
  if (!task.notebook_id) return 'personal';
  return notebooks.find(item => item.notebook_id === task.notebook_id)?.color || 'gray';
}
const projectKey = (task: Task) => task.notebook_id || PERSONAL;
const visibleTasks = () => tasks.filter(task => !calvHiddenKinds.has(task.kind) && !calvHiddenProjects.has(projectKey(task)));
function timeRange(task: Task): string {
  const start = timeFmt.format(new Date(task.due_at));
  return task.ends_at ? `${start}–${timeFmt.format(new Date(task.ends_at))}` : start;
}
function entryLabel(task: Task): string {
  const status = task.completed ? ', completada' : taskTiming(task).tone === 'overdue' ? ', vencida' : '';
  return `${kindLabels[task.kind]}: ${task.title}, ${longDay.format(new Date(task.due_at))} ${timeRange(task)}${task.notebook_id ? `, proyecto ${task.notebook_id}` : ', personal'}${status}`;
}

function entryChip(task: Task, className = 'calv-chip'): HTMLButtonElement {
  const chip = document.createElement('button'); chip.type = 'button'; chip.className = className;
  chip.dataset.eventColor = entryColor(task);
  if (task.completed) chip.classList.add('is-done');
  if (!task.completed && taskTiming(task).tone === 'overdue') chip.classList.add('is-overdue');
  chip.setAttribute('aria-label', entryLabel(task)); chip.title = entryLabel(task);
  chip.innerHTML = `${icon(kindIcons[task.kind])}<span class="calv-chip-time"></span><span class="calv-chip-title"></span>`;
  chip.querySelector('.calv-chip-time')!.textContent = timeFmt.format(new Date(task.due_at));
  chip.querySelector('.calv-chip-title')!.textContent = task.title;
  chip.addEventListener('click', event => { event.stopPropagation(); openEntry(task); });
  return chip;
}

function renderCalendarView() {
  if (currentView !== 'calendar') return;
  document.querySelectorAll<HTMLButtonElement>('[data-calv-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.calvMode === calvMode)));
  if (calvMode === 'month') renderMonth(); else renderWeek();
  renderDayPanel(); renderFilters();
}

function renderMonth() {
  const grid = el('calv-grid'); grid.replaceChildren(); grid.className = 'calv-grid is-month';
  const first = new Date(calvCursor.getFullYear(), calvCursor.getMonth(), 1);
  el('calv-range').textContent = capital(monthYear.format(first));
  const head = document.createElement('div'); head.className = 'calv-weekdays'; head.setAttribute('aria-hidden', 'true');
  for (const name of ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']) { const cell = document.createElement('span'); cell.textContent = name; head.append(cell); }
  const body = document.createElement('div'); body.className = 'calv-month';
  const start = mondayOf(first); const today = localDateKey(new Date());
  const byDay = new Map<string, Task[]>();
  for (const task of visibleTasks()) { const key = localDateKey(new Date(task.due_at)); byDay.set(key, [...(byDay.get(key) || []), task]); }
  for (let index = 0; index < 42; index += 1) {
    const date = addDays(start, index); const key = localDateKey(date);
    const entries = (byDay.get(key) || []).sort((a, b) => Date.parse(a.due_at) - Date.parse(b.due_at));
    const cell = document.createElement('div'); cell.className = 'calv-cell';
    if (date.getMonth() !== first.getMonth()) cell.classList.add('is-outside');
    if (key === today) cell.classList.add('is-today');
    if (key === calvSelected) cell.classList.add('is-selected');
    const top = document.createElement('div'); top.className = 'calv-cell-top';
    const number = document.createElement('button'); number.type = 'button'; number.className = 'calv-daynum'; number.textContent = String(date.getDate());
    number.setAttribute('aria-label', `${capital(weekdayName.format(date))} ${longDay.format(date)}: ${entries.length ? `${entries.length} ${entries.length === 1 ? 'entrada' : 'entradas'}` : 'sin entradas'}`);
    if (key === calvSelected) number.setAttribute('aria-current', 'date');
    number.addEventListener('click', () => selectDay(key));
    const add = document.createElement('button'); add.type = 'button'; add.className = 'calv-add'; add.innerHTML = icon('plus');
    add.setAttribute('aria-label', `Agregar el ${longDay.format(date)}`); add.addEventListener('click', event => { event.stopPropagation(); openEntry(undefined, key); });
    top.append(number, add); cell.append(top);
    const list = document.createElement('div'); list.className = 'calv-cell-entries';
    // Se pintan hasta cuatro y fitMonthCells esconde las que no quepan en el alto real
    // de la fila; lo escondido se cuenta en «+N más» y se lee completo en el panel del dia.
    cell.dataset.total = String(entries.length);
    for (const task of entries.slice(0, 4)) list.append(entryChip(task));
    const more = document.createElement('button'); more.type = 'button'; more.className = 'calv-more'; more.hidden = true;
    more.addEventListener('click', event => { event.stopPropagation(); selectDay(key); });
    list.append(more);
    // En pantallas angostas el dia muestra puntos de color en lugar de textos.
    const dots = document.createElement('div'); dots.className = 'calv-dots'; dots.setAttribute('aria-hidden', 'true');
    for (const task of entries.slice(0, 4)) { const dot = document.createElement('i'); dot.dataset.eventColor = entryColor(task); dots.append(dot); }
    cell.append(list, dots);
    cell.addEventListener('click', event => { if (!(event.target as HTMLElement).closest('button')) selectDay(key); });
    body.append(cell);
  }
  grid.append(head, body);
  fitMonthCells(body);
}

function fitMonthCells(body: HTMLElement) {
  for (const cell of body.querySelectorAll<HTMLElement>('.calv-cell')) {
    const chips = [...cell.querySelectorAll<HTMLElement>('.calv-cell-entries .calv-chip')];
    const more = cell.querySelector<HTMLButtonElement>('.calv-more')!;
    const total = Number(cell.dataset.total || 0); let shown = chips.length;
    const sync = () => { const rest = total - shown; more.hidden = rest <= 0; more.textContent = `+${rest} más`; more.setAttribute('aria-label', `Ver ${rest} ${rest === 1 ? 'entrada más' : 'entradas más'} de este día`); };
    sync();
    while (shown > 0 && cell.scrollHeight > cell.clientHeight + 1) { chips[shown - 1].hidden = true; shown -= 1; sync(); }
  }
}

function renderWeek() {
  const grid = el('calv-grid'); grid.replaceChildren(); grid.className = 'calv-grid is-week';
  const start = mondayOf(calvCursor); const end = addDays(start, 6);
  el('calv-range').textContent = start.getMonth() === end.getMonth()
    ? `${start.getDate()} – ${end.getDate()} de ${new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' }).format(end)}`
    : `${longDay.format(start)} – ${longDay.format(end)} ${end.getFullYear()}`;
  const today = localDateKey(new Date());
  const head = document.createElement('div'); head.className = 'calv-week-head';
  head.append(document.createElement('span'));
  const scroller = document.createElement('div'); scroller.className = 'calv-week-scroll';
  const board = document.createElement('div'); board.className = 'calv-week-board'; board.style.height = `${24 * HOUR_PX}px`;
  const hours = document.createElement('div'); hours.className = 'calv-hours'; hours.setAttribute('aria-hidden', 'true');
  for (let hour = 1; hour < 24; hour += 1) { const label = document.createElement('span'); label.style.top = `${hour * HOUR_PX}px`; label.textContent = `${String(hour).padStart(2, '0')}:00`; hours.append(label); }
  board.append(hours);
  let earliest = 8 * 60;
  for (let offset = 0; offset < 7; offset += 1) {
    const date = addDays(start, offset); const key = localDateKey(date);
    const dayHead = document.createElement('button'); dayHead.type = 'button'; dayHead.className = 'calv-week-day';
    if (key === today) dayHead.classList.add('is-today');
    if (key === calvSelected) { dayHead.classList.add('is-selected'); dayHead.setAttribute('aria-current', 'date'); }
    dayHead.innerHTML = '<span></span><strong></strong>';
    dayHead.querySelector('span')!.textContent = new Intl.DateTimeFormat('es-CO', { weekday: 'short' }).format(date).replace('.', '');
    dayHead.querySelector('strong')!.textContent = String(date.getDate());
    dayHead.setAttribute('aria-label', `${capital(weekdayName.format(date))} ${longDay.format(date)}`);
    dayHead.addEventListener('click', () => selectDay(key)); head.append(dayHead);
    const column = document.createElement('div'); column.className = 'calv-week-col';
    if (key === today) column.classList.add('is-today');
    column.setAttribute('aria-label', `Horas del ${longDay.format(date)}. Pulsa un espacio libre para agregar.`);
    column.addEventListener('click', event => {
      if ((event.target as HTMLElement).closest('button')) return;
      const y = event.clientY - column.getBoundingClientRect().top;
      const hour = Math.min(23, Math.max(0, Math.floor(y / HOUR_PX)));
      openEntry(undefined, key, `${String(hour).padStart(2, '0')}:00`);
    });
    const entries = visibleTasks().filter(task => localDateKey(new Date(task.due_at)) === key);
    const lanes = dayLanes(entries);
    for (const task of entries) {
      const begin = new Date(task.due_at); const minutes = begin.getHours() * 60 + begin.getMinutes();
      earliest = Math.min(earliest, minutes);
      const span = task.ends_at ? Math.max(20, (Date.parse(task.ends_at) - begin.getTime()) / 60000) : 0;
      const block = entryChip(task, task.ends_at ? 'calv-block' : 'calv-block is-point');
      const place = lanes.get(task.id) || { lane: 0, lanes: 1 };
      block.style.top = `${minutes * HOUR_PX / 60}px`;
      block.style.height = task.ends_at ? `${Math.min(span, 24 * 60 - minutes) * HOUR_PX / 60}px` : '';
      block.style.left = `calc(${place.lane / place.lanes * 100}% + 2px)`;
      block.style.width = `calc(${100 / place.lanes}% - 4px)`;
      if (task.ends_at) { const range = document.createElement('span'); range.className = 'calv-block-range'; range.textContent = timeRange(task); block.append(range); }
      column.append(block);
    }
    if (key === today) {
      const now = new Date(); const line = document.createElement('div'); line.className = 'calv-now';
      line.style.top = `${(now.getHours() * 60 + now.getMinutes()) * HOUR_PX / 60}px`; line.setAttribute('aria-hidden', 'true'); column.append(line);
    }
    board.append(column);
  }
  scroller.append(board); grid.append(head, scroller);
  scroller.scrollTop = Math.max(0, (earliest - 30) * HOUR_PX / 60);
}

function renderDayPanel() {
  const date = fromKey(calvSelected);
  el('calv-weekday').textContent = capital(weekdayName.format(date));
  el('calv-day-title').textContent = longDay.format(date);
  const list = el('calv-day-list'); list.replaceChildren();
  const entries = visibleTasks().filter(task => localDateKey(new Date(task.due_at)) === calvSelected)
    .sort((a, b) => Date.parse(a.due_at) - Date.parse(b.due_at));
  if (!entries.length) {
    const empty = document.createElement('div'); empty.className = 'calv-day-empty';
    const text = document.createElement('p'); text.textContent = 'Nada agendado para este día.';
    const add = document.createElement('button'); add.type = 'button'; add.className = 'button quiet'; add.innerHTML = `${icon('plus')}Agregar`;
    add.addEventListener('click', () => openEntry(undefined, calvSelected)); empty.append(text, add); list.append(empty); return;
  }
  for (const task of entries) {
    const timing = taskTiming(task);
    const row = document.createElement('article'); row.className = 'calv-item'; row.dataset.eventColor = entryColor(task);
    if (task.completed) row.classList.add('is-done');
    const check = document.createElement('input'); check.type = 'checkbox'; check.className = 'calv-item-check'; check.checked = task.completed;
    check.setAttribute('aria-label', `${task.completed ? 'Reabrir' : 'Completar'}: ${task.title}`); check.disabled = calvSaving || task.project_role === 'viewer';
    check.addEventListener('change', async () => { await saveEntry({ ...task, completed: check.checked }); });
    const open = document.createElement('button'); open.type = 'button'; open.className = 'calv-item-open'; open.setAttribute('aria-label', `Editar ${entryLabel(task)}`);
    open.innerHTML = `<span class="calv-item-kind">${icon(kindIcons[task.kind])}<span></span></span><strong></strong><span class="calv-item-meta"></span>`;
    open.querySelector('.calv-item-kind span')!.textContent = `${kindLabels[task.kind]} · ${timeRange(task)}`;
    open.querySelector('strong')!.textContent = task.title;
    const meta = open.querySelector('.calv-item-meta')!;
    const project = document.createElement('span'); project.className = 'calv-item-project'; project.textContent = task.notebook_id || 'Personal'; meta.append(project);
    if (!task.completed && timing.tone === 'overdue') { const late = document.createElement('span'); late.className = 'calv-item-late'; late.textContent = 'Vencida'; meta.append(late); }
    open.addEventListener('click', () => openEntry(task));
    row.append(check, open); list.append(row);
  }
}

function renderFilters() {
  const kindBox = el('calv-kind-filters'); kindBox.replaceChildren();
  for (const kind of Object.keys(kindLabels) as EntryKind[]) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'calv-filter';
    button.setAttribute('aria-pressed', String(!calvHiddenKinds.has(kind)));
    button.innerHTML = `${icon(kindIcons[kind])}<span></span>`; button.querySelector('span')!.textContent = kindLabels[kind];
    button.addEventListener('click', () => { if (calvHiddenKinds.has(kind)) calvHiddenKinds.delete(kind); else calvHiddenKinds.add(kind); renderCalendarView(); });
    kindBox.append(button);
  }
  const projectBox = el('calv-project-filters'); projectBox.replaceChildren();
  const options: [string, string, string][] = [...notebooks.map(item => [item.notebook_id, item.notebook_id, item.color] as [string, string, string]), [PERSONAL, 'Personal', 'personal']];
  for (const [key, name, color] of options) {
    const label = document.createElement('label'); label.className = 'calv-project-filter';
    const box = document.createElement('input'); box.type = 'checkbox'; box.checked = !calvHiddenProjects.has(key);
    box.addEventListener('change', () => { if (box.checked) calvHiddenProjects.delete(key); else calvHiddenProjects.add(key); renderCalendarView(); });
    const dot = document.createElement('i'); dot.dataset.eventColor = color; dot.setAttribute('aria-hidden', 'true');
    const text = document.createElement('span'); text.textContent = name; text.title = name;
    label.append(box, dot, text); projectBox.append(label);
  }
}

function selectDay(key: string) {
  calvSelected = key; calvCursor = fromKey(key); renderCalendarView();
}

function showCalendar(updateLocation = true, day?: string) {
  if (!canNavigateAwayFromTree()) return;
  currentView = 'calendar';
  if (day) { calvSelected = day; calvCursor = fromKey(day); }
  if (updateLocation && location.hash !== '#calendario') history.pushState(null, '', '#calendario');
  updateHeader(); renderNotebooks(); setSidebar(false); renderCalendarView();
}

function openEntry(task?: Task, day?: string, time?: string) {
  if (calvSaving || task?.project_role === 'viewer') return; calvEditing = task || null;
  el('calv-dialog-title').textContent = task ? `Editar ${kindLabels[task.kind].toLocaleLowerCase('es')}` : 'Nueva entrada';
  el('calv-error').hidden = true; el('calv-delete-confirm').hidden = true;
  el<HTMLInputElement>('calv-entry-title').value = task?.title || '';
  el<HTMLInputElement>('calv-entry-title').removeAttribute('aria-invalid');
  el('calv-form').querySelector<HTMLInputElement>(`input[name="calv-kind"][value="${task?.kind || 'tarea'}"]`)!.checked = true;
  const start = task ? new Date(task.due_at) : null;
  const hhmm = (date: Date) => `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  el<HTMLInputElement>('calv-date').value = start ? localDateKey(start) : day || calvSelected;
  el<HTMLInputElement>('calv-start').value = start ? hhmm(start) : time || '09:00';
  el<HTMLInputElement>('calv-end').value = task?.ends_at ? hhmm(new Date(task.ends_at)) : '';
  const project = el<HTMLSelectElement>('calv-project'); project.replaceChildren(new Option('Personal (sin proyecto)', ''));
  for (const notebook of notebooks.filter(item => item.role !== 'viewer')) project.add(new Option(notebook.notebook_id, notebook.project_id));
  project.value = task?.project_id || '';
  el<HTMLSelectElement>('calv-priority').value = task?.priority || 'medium';
  el('calv-done-row').hidden = !task; el<HTMLInputElement>('calv-done').checked = !!task?.completed;
  el('calv-delete').hidden = !task;
  el<HTMLDialogElement>('calv-dialog').showModal(); el('calv-entry-title').focus();
}

async function persistTask(task: Task | Omit<Task, 'id'>): Promise<Task> {
  const { title, kind, due_at, ends_at, priority, notebook_id, project_id, completed } = task;
  const id = 'id' in task ? task.id : '';
  // La marca sale de la copia guardada en memoria: es la version que la persona vio.
  const base_updated_at = id ? tasks.find(item => item.id === id)?.updated_at ?? null : null;
  try {
    const saved = await api<Task>(`/tasks${id ? `/${id}` : ''}`, { method: id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, kind, due_at, ends_at, priority, notebook_id, project_id, completed, base_updated_at }) });
    tasks = id ? tasks.map(item => item.id === id ? saved : item) : [...tasks, saved];
    return saved;
  } catch (error) {
    if (error instanceof ApiError && error.status === 409 && error.current) {
      const current = error.current as Task; tasks = tasks.map(item => item.id === current.id ? current : item);
      throw new ApiError(`${error.message} Si repites el cambio, tus datos la reemplazan.`, 409, current);
    }
    throw error;
  }
}

async function saveEntry(task: Task | Omit<Task, 'id'>): Promise<boolean> {
  if (calvSaving) return false; calvSaving = true;
  try {
    const previous = 'id' in task ? tasks.find(item => item.id === task.id) : undefined;
    const saved = await persistTask(task);
    const ending = saved.kind === 'recordatorio' ? 'o' : 'a';
    const title = !previous ? `${kindLabels[saved.kind]} cread${ending}` : previous.completed !== saved.completed ? (saved.completed ? `${kindLabels[saved.kind]} completad${ending}` : `${kindLabels[saved.kind]} reabiert${ending}`) : `${kindLabels[saved.kind]} actualizad${ending}`;
    showToast(previous?.completed && !saved.completed ? 'info' : 'success', title, `“${saved.title}” quedó guardad${ending} en el calendario.`);
    return true;
  }
  catch (error) { el('calv-error').textContent = (error as Error).message; el('calv-error').hidden = false; showError((error as Error).message); return false; }
  finally { calvSaving = false; tasksChanged(); }
}

/** Todo lo que depende de las entradas se vuelve a pintar junto. */
function tasksChanged() {
  renderCalendar(); renderTasks(); renderCalendarView(); renderNotifications();
}

async function loadInvitations() {
  invitations = await api<Invitation[]>('/sharing/invitations');
  renderNotifications();
}

function renderInvitations() {
  const section = el('invitation-notifications'); section.hidden = !invitations.length;
  el('invitation-count').textContent = String(invitations.length);
  const list = el('invitation-list'); list.replaceChildren();
  for (const invitation of invitations) {
    const item = document.createElement('article'); item.className = 'invitation-item';
    const copy = document.createElement('div');
    const title = document.createElement('strong'); title.textContent = invitation.notebook_id;
    const detail = document.createElement('p'); detail.textContent = `${invitation.owner_name} te invita como ${invitation.role === 'editor' ? 'editor' : 'lector'}. Tus chats serán privados.`;
    copy.append(title, detail);
    const actions = document.createElement('div'); actions.className = 'invitation-actions';
    for (const [label, accept] of [['Rechazar', false], ['Aceptar', true]] as const) {
      const button = document.createElement('button'); button.type = 'button'; button.className = accept ? 'button primary' : 'button quiet'; button.textContent = label;
      button.addEventListener('click', async () => {
        actions.querySelectorAll('button').forEach(node => { node.disabled = true; });
        try {
          await api(`/sharing/invitations/${invitation.id}/respond`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ accept }) });
          invitations = invitations.filter(item => item.id !== invitation.id); await refreshNotebooks(); renderNotifications();
          if (accept) {
            el<HTMLDetailsElement>('header-notifications').open = false;
            await loadNotebook(invitation.project_id);
          }
          showToast(accept ? 'success' : 'info', accept ? 'Proyecto añadido' : 'Invitación rechazada', accept ? `“${invitation.notebook_id}” ya aparece en tus proyectos.` : 'La invitación fue retirada.');
        } catch (error) { showError((error as Error).message); actions.querySelectorAll('button').forEach(node => { node.disabled = false; }); }
      }); actions.append(button);
    }
    item.append(copy, actions); list.append(item);
  }
}

function renderNotifications() {
  const groups = notificationGroups(tasks);
  const agendaTotal = groups.overdue.length + groups.today.length + groups.soon.length;
  const attention = groups.alert + invitations.length;
  const total = agendaTotal + invitations.length;
  const badge = el('notif-badge'); badge.hidden = !attention; badge.textContent = attention > 9 ? '9+' : String(attention);
  el('notif-summary').setAttribute('aria-label', attention ? `Notificaciones: ${attention} ${attention === 1 ? 'pendiente' : 'pendientes'}` : 'Notificaciones');
  const menuCount = el('calendar-alert-count'); menuCount.hidden = !groups.alert; menuCount.textContent = String(groups.alert);
  const panelSummary = el('notif-panel-summary');
  panelSummary.textContent = invitations.length ? `${invitations.length} ${invitations.length === 1 ? 'invitación espera' : 'invitaciones esperan'} tu respuesta.` : groups.alert
    ? `${groups.alert} ${groups.alert === 1 ? 'aviso requiere' : 'avisos requieren'} tu atención${groups.soon.length ? ` · ${groups.soon.length} próxim${groups.soon.length === 1 ? 'o' : 'os'}` : ''}.`
    : groups.soon.length ? `Todo en orden · ${groups.soon.length} próxim${groups.soon.length === 1 ? 'o' : 'os'}.` : 'Tu agenda está al día.';
  const totalBadge = el('notif-total'); totalBadge.hidden = !total; totalBadge.textContent = `${total} ${total === 1 ? 'aviso' : 'avisos'}`;
  renderInvitations();
  const list = el('notif-list'); list.replaceChildren();
  const sections: [string, string, string, Task[]][] = [
    ['Vencidas', 'overdue', 'Vencida', groups.overdue],
    ['Para hoy', 'today', 'Hoy', groups.today],
    ['Próximos días', 'soon', 'Próxima', groups.soon],
  ];
  for (const [name, tone, status, items] of sections) {
    if (!items.length) continue;
    const group = document.createElement('section'); group.className = 'notif-group'; group.dataset.tone = tone;
    const groupHead = document.createElement('div'); groupHead.className = 'notif-group-head';
    const heading = document.createElement('h3'); heading.textContent = name;
    const count = document.createElement('span'); count.className = 'notif-group-count'; count.textContent = String(items.length); count.setAttribute('aria-label', `${items.length} ${items.length === 1 ? 'notificación' : 'notificaciones'}`);
    groupHead.append(heading, count); group.append(groupHead);
    for (const task of items.slice(0, 6)) {
      const item = document.createElement('button'); item.type = 'button'; item.className = 'notif-item'; item.dataset.eventColor = entryColor(task);
      if (tone === 'overdue') item.classList.add('is-overdue');
      item.innerHTML = `<span class="notif-kind">${icon(kindIcons[task.kind])}</span><span class="notif-text"><span class="notif-item-top"><strong></strong><span class="notif-status"></span></span><span class="notif-meta"><span class="notif-when"></span><span class="notif-project"></span></span></span>`;
      item.querySelector('strong')!.textContent = task.title;
      item.querySelector('.notif-status')!.textContent = status;
      item.querySelector('.notif-when')!.textContent = tone === 'today' ? timeRange(task) : `${longDay.format(new Date(task.due_at))} · ${timeFmt.format(new Date(task.due_at))}`;
      item.querySelector('.notif-project')!.textContent = task.notebook_id || 'Personal';
      item.setAttribute('aria-label', `Ver en el calendario: ${entryLabel(task)}`);
      item.addEventListener('click', () => { el<HTMLDetailsElement>('header-notifications').open = false; showCalendar(true, localDateKey(new Date(task.due_at))); });
      group.append(item);
    }
    if (items.length > 6) { const more = document.createElement('p'); more.className = 'notif-more'; more.textContent = `Y ${items.length - 6} ${items.length - 6 === 1 ? 'aviso más' : 'avisos más'} en el calendario.`; group.append(more); }
    list.append(group);
  }
  if (!list.children.length) {
    const calm = document.createElement('div'); calm.className = 'notif-calm';
    calm.innerHTML = `<span class="notif-calm-mark">${icon('check')}</span><strong>Todo está en orden</strong><p>No tienes entradas vencidas ni pendientes para los próximos días.</p>`;
    list.append(calm);
  }
}

el('go-calendar').addEventListener('click', () => { if (!busy && !loadingNotebook) showCalendar(); });
let calvResize = 0;
window.addEventListener('resize', () => { window.clearTimeout(calvResize); calvResize = window.setTimeout(() => { if (currentView === 'calendar' && calvMode === 'month') renderCalendarView(); }, 150); });
el('notif-open-calendar').addEventListener('click', () => { el<HTMLDetailsElement>('header-notifications').open = false; showCalendar(true, localDateKey(new Date())); });
document.querySelectorAll<HTMLButtonElement>('[data-calv-mode]').forEach(button => button.addEventListener('click', () => { calvMode = button.dataset.calvMode as CalvMode; renderCalendarView(); }));
el('calv-today').addEventListener('click', () => selectDay(localDateKey(new Date())));
const shiftPeriod = (step: number) => {
  calvCursor = calvMode === 'month' ? new Date(calvCursor.getFullYear(), calvCursor.getMonth() + step, 1) : addDays(calvCursor, 7 * step);
  if (calvMode === 'week') calvSelected = localDateKey(mondayOf(calvCursor));
  renderCalendarView();
};
el('calv-prev').addEventListener('click', () => shiftPeriod(-1));
el('calv-next').addEventListener('click', () => shiftPeriod(1));
el('calv-new-entry').addEventListener('click', () => openEntry(undefined, calvSelected));
el('calv-cancel').addEventListener('click', () => { if (!calvSaving) el<HTMLDialogElement>('calv-dialog').close(); });
el('calv-dialog').addEventListener('cancel', event => { if (calvSaving) event.preventDefault(); });
el('calv-delete').addEventListener('click', () => { el('calv-delete-confirm').hidden = false; el('calv-cancel-delete').focus(); });
el('calv-cancel-delete').addEventListener('click', () => { el('calv-delete-confirm').hidden = true; el('calv-delete').focus(); });
el('calv-confirm-delete').addEventListener('click', async () => {
  if (!calvEditing || calvSaving) return; calvSaving = true;
  try { const removed = calvEditing; const ending = removed.kind === 'recordatorio' ? 'o' : 'a'; await api(`/tasks/${removed.id}`, { method: 'DELETE' }); tasks = tasks.filter(item => item.id !== removed.id); el<HTMLDialogElement>('calv-dialog').close(); showToast('warning', `${kindLabels[removed.kind]} eliminad${ending}`, `“${removed.title}” se quitó del calendario.`); }
  catch (error) { el('calv-error').textContent = (error as Error).message; el('calv-error').hidden = false; }
  finally { calvSaving = false; tasksChanged(); }
});
el('calv-form').addEventListener('submit', async event => {
  event.preventDefault(); if (calvSaving) return;
  const title = el<HTMLInputElement>('calv-entry-title').value.trim();
  const date = el<HTMLInputElement>('calv-date').value; const startText = el<HTMLInputElement>('calv-start').value; const endText = el<HTMLInputElement>('calv-end').value;
  const start = new Date(`${date}T${startText}`); const end = endText ? new Date(`${date}T${endText}`) : null;
  const fail = (message: string, field: string) => { el('calv-error').textContent = message; el('calv-error').hidden = false; el(field).setAttribute('aria-invalid', 'true'); el(field).focus(); };
  for (const id of ['calv-entry-title', 'calv-date', 'calv-start', 'calv-end']) el(id).removeAttribute('aria-invalid');
  if (!title) return fail('Escribe qué hay que recordar.', 'calv-entry-title');
  if (!date || !startText || Number.isNaN(start.getTime())) return fail('Elige una fecha y una hora válidas.', !date ? 'calv-date' : 'calv-start');
  if (end && end <= start) return fail('La hora de fin debe ser posterior a la de inicio.', 'calv-end');
  const kind = el('calv-form').querySelector<HTMLInputElement>('input[name="calv-kind"]:checked')!.value as EntryKind;
  const body = { title, kind, due_at: start.toISOString(), ends_at: end ? end.toISOString() : null, priority: el<HTMLSelectElement>('calv-priority').value as Task['priority'], notebook_id: null, project_id: el<HTMLSelectElement>('calv-project').value || null, completed: calvEditing ? el<HTMLInputElement>('calv-done').checked : false };
  const ok = await saveEntry(calvEditing ? { ...body, id: calvEditing.id } : body);
  if (ok) { el<HTMLDialogElement>('calv-dialog').close(); selectDay(date); }
});
// La hora avanza: vencidas y la linea de "ahora" se recalculan cada minuto.
setInterval(() => { renderNotifications(); if (currentView === 'calendar' && !calvSaving && !el('calendar-view').contains(document.activeElement)) renderCalendarView(); }, 60000);

function featuredTools(): Tool[] {
  // Criterio real y comprobable: son las unicas fichas que alimentan la memoria
  // verificada. El prototipo no registra uso, asi que no hay "mas usadas".
  return tools.filter(tool => tool.template_fields.length).slice(0, 4);
}

function whatItIs(markdown: string): string {
  const lines = markdown.split('\n');
  const start = lines.findIndex(line => /^#{1,6}\s*Qu[eé] es\s*$/.test(line.trim()));
  if (start < 0) return '';
  for (let index = start + 1; index < lines.length; index += 1) {
    const line = lines[index].trim();
    if (/^#{1,6}\s/.test(line)) break;
    if (line) return line.replace(/[*_`]/g, '').replace(/\s+/g, ' ').trim();
  }
  return '';
}

async function loadSummaries(featured: Tool[]) {
  await Promise.all(featured.map(async tool => {
    if (summaries.has(tool.id)) return;
    try {
      const card = await api<{ content: string }>(`/tools/${encodeURIComponent(tool.id)}`);
      const summary = whatItIs(card.content);
      if (summary) summaries.set(tool.id, summary);
    } catch {
      // Sin la ficha no se inventa descripcion: el recuadro se queda sin nota.
    }
  }));
  renderHomeTools();
}

function renderHomeTools() {
  const box = el('home-tool-chips'); box.replaceChildren();
  const featured = featuredTools();
  const looks: Record<string, { tint: string; mark?: string; image?: string }> = {
    'arbol-problemas': { tint: 'green', image: '/ficha-arbol.png' },
    'cinco-porques': { tint: 'peach', image: '/ficha-cinco.png' },
    pestel: { tint: 'lavender', image: '/ficha-pestel.png' },
    'mapa-empatia': { tint: 'rose', image: '/ficha-empatia.png' },
  };
  const fallback = ['green', 'peach', 'lavender', 'rose'];
  featured.forEach((tool, index) => {
    const look = looks[tool.id];
    const tile = document.createElement('button'); tile.type = 'button'; tile.className = 'tool-tile';
    tile.dataset.tint = look ? look.tint : fallback[index % fallback.length];
    const art = document.createElement('span'); art.className = 'tool-tile-art';
    if (look && look.image) {
      const picture = document.createElement('img');
      picture.src = look.image; picture.alt = ''; picture.loading = 'lazy'; picture.decoding = 'async';
      art.append(picture); art.classList.add('is-image');
    } else {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 64 64'); svg.setAttribute('aria-hidden', 'true');
      const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
      use.setAttribute('href', `#${look && look.mark ? look.mark : 'm-ficha'}`);
      svg.append(use); art.append(svg);
    }
    const name = document.createElement('span'); name.className = 'tool-tile-name'; name.textContent = tool.name;
    const note = document.createElement('span'); note.className = 'tool-tile-note';
    // El texto tiene ancho propio dentro de una caja que se abre: asi no se
    // reacomoda linea a linea mientras dura la animacion.
    const noteText = document.createElement('span'); noteText.className = 'tool-tile-note-text';
    noteText.textContent = summaries.get(tool.id) || '';
    note.append(noteText);
    const row = document.createElement('span'); row.className = 'tool-tile-row';
    row.append(art, note);
    tile.setAttribute('aria-label', `Abrir la ficha ${tool.name}`);
    tile.append(name, row);
    tile.addEventListener('click', () => { void openTool(tool); });
    box.append(tile);
  });
  if (!summariesRequested && featured.some(tool => !summaries.has(tool.id))) {
    summariesRequested = true;
    void loadSummaries(featured);
  }
}

function shiftMonth(step: number) {
  calendarCursor = new Date(calendarCursor.getFullYear(), calendarCursor.getMonth() + step, 1);
  selectedDay = ''; renderCalendar(); renderTasks();
}
el('cal-prev').addEventListener('click', () => shiftMonth(-1));
el('cal-next').addEventListener('click', () => shiftMonth(1));
el('home-tools-link').addEventListener('click', () => { if (!busy && !loadingNotebook) showTools(); });

function renderAuthLanguage() {
  const view = el('auth-view');
  view.lang = authLanguage;
  el<HTMLSelectElement>('auth-language').value = authLanguage;
  el('auth-language').setAttribute('aria-label', authT('language'));
  view.querySelectorAll<HTMLElement>('[data-auth-text]').forEach(node => {
    node.textContent = authT(node.dataset.authText as AuthTextKey);
  });
  view.querySelectorAll<HTMLInputElement>('[data-auth-placeholder]').forEach(node => {
    node.placeholder = authT(node.dataset.authPlaceholder as AuthTextKey);
  });
  view.querySelector('.auth-alternatives')?.setAttribute('aria-label', authT('alternatives'));
  view.querySelectorAll<HTMLButtonElement>('.auth-provider').forEach(button => {
    const providerName = button.querySelector('span')!.textContent;
    button.setAttribute('aria-label', `${providerName}, ${authT('soon')}`);
    button.title = `${providerName} · ${authT('soon')}`;
  });
  const registering = authMode === 'register';
  el('auth-title').textContent = authT(registering ? 'registerTitle' : 'loginTitle');
  el('auth-intro').textContent = authT(registering ? 'registerIntro' : 'loginIntro');
  const submit = el<HTMLButtonElement>('auth-submit');
  submit.textContent = authT(submit.disabled ? registering ? 'creating' : 'entering' : registering ? 'register' : el('auth-password-field').hidden ? 'continue' : 'login');
  el('auth-note').textContent = authT(registering ? 'registerNote' : 'loginNote');
  const error = el('auth-error');
  if (!error.hidden) error.textContent = translateAuthError(error.textContent || '', authLanguage);
}

el('auth-language').addEventListener('change', () => {
  authLanguage = el<HTMLSelectElement>('auth-language').value === 'en' ? 'en' : 'es';
  saveAuthLanguage(authLanguage);
  renderAuthLanguage();
});

function setAuthMode(mode: 'login' | 'register') {
  authMode = mode;
  const registering = mode === 'register';
  el('auth-name-field').hidden = !registering;
  el('auth-confirm-field').hidden = !registering;
  el('auth-password-hint').hidden = !registering;
  el('auth-password-field').hidden = !registering;
  el('auth-back').hidden = true;
  el<HTMLInputElement>('auth-username').readOnly = false;
  el<HTMLInputElement>('auth-password').value = '';
  el<HTMLInputElement>('auth-confirm').value = '';
  el<HTMLInputElement>('auth-password').autocomplete = registering ? 'new-password' : 'current-password';
  el('auth-login-prompt').hidden = !registering;
  el('auth-register-prompt').hidden = registering;
  el('auth-error').hidden = true;
  renderAuthLanguage();
  el<HTMLInputElement>(registering ? 'auth-name' : 'auth-username').focus();
}
el('auth-login-tab').addEventListener('click', () => setAuthMode('login'));
el('auth-register-tab').addEventListener('click', () => setAuthMode('register'));
el('auth-back').addEventListener('click', () => setAuthMode('login'));
el('auth-form').addEventListener('submit', async event => {
  event.preventDefault();
  const username = el<HTMLInputElement>('auth-username').value.trim();
  const password = el<HTMLInputElement>('auth-password').value;
  const displayName = el<HTMLInputElement>('auth-name').value.trim();
  const confirm = el<HTMLInputElement>('auth-confirm').value;
  const error = el('auth-error'); error.hidden = true;
  if (!/^[A-Za-z0-9_.-]{3,40}$/.test(username)) { error.textContent = authT('invalidUsername'); error.hidden = false; el('auth-username').focus(); return; }
  if (authMode === 'login' && el('auth-password-field').hidden) {
    el('auth-password-field').hidden = false;
    el('auth-back').hidden = false;
    el<HTMLInputElement>('auth-username').readOnly = true;
    el('auth-submit').textContent = authT('login');
    el<HTMLInputElement>('auth-password').focus();
    return;
  }
  if (authMode === 'register' && (!displayName || password.length < 10 || password !== confirm)) {
    error.textContent = authT(!displayName ? 'missingName' : password.length < 10 ? 'shortPassword' : 'passwordMismatch');
    error.hidden = false; el(authMode === 'register' && !displayName ? 'auth-name' : password.length < 10 ? 'auth-password' : 'auth-confirm').focus(); return;
  }
  if (!password) { error.textContent = authT('missingPassword'); error.hidden = false; el('auth-password').focus(); return; }
  const submit = el<HTMLButtonElement>('auth-submit'); submit.disabled = true; submit.textContent = authT(authMode === 'register' ? 'creating' : 'entering');
  const modeControls = ['auth-back', 'auth-login-tab', 'auth-register-tab'].map(id => el<HTMLButtonElement>(id));
  modeControls.forEach(control => { control.disabled = true; });
  try {
    const path = authMode === 'register' ? '/auth/register' : '/auth/login';
    await api<Account>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(authMode === 'register' ? { username, display_name: displayName, password, confirm_password: confirm } : { username, password }) });
    window.location.reload();
  } catch (caught) { error.textContent = translateAuthError((caught as Error).message, authLanguage); error.hidden = false; submit.disabled = false; submit.textContent = authT(authMode === 'register' ? 'register' : 'login'); modeControls.forEach(control => { control.disabled = false; }); }
});

async function init() {
  renderAuthLanguage();
  try {
    const response = await fetch('/api/auth/me', { cache: 'no-store' });
    if (response.status === 401) {
      el('auth-view').hidden = false; setAuthMode('login'); return;
    }
    if (!response.ok) throw new Error(authT('sessionError'));
    account = await response.json() as Account;
    el('app').hidden = false;
  } catch (error) {
    el('auth-view').hidden = false; el('auth-error').textContent = `${translateAuthError((error as Error).message, authLanguage)} ${authT('reload')}`; el('auth-error').hidden = false; return;
  }
  renderProfile(); renderCalendar(); syncControls();
  try {
    const [catalog] = await Promise.all([api<{ stages: Stage[]; tools: Tool[]; graph: Graph }>('/catalog'), refreshStatus(), refreshNotebooks(), loadTasks(), loadInvitations()]);
    stages = catalog.stages; tools = catalog.tools; graphData = catalog.graph; buildGraph(); renderTools(); renderHomeTools();
    for (const stage of stages) { const option = document.createElement('option'); option.value = String(stage.id); option.textContent = `${stage.id}. ${stage.name}`; el<HTMLSelectElement>('initial-stage').append(option); }
    renderNotebooks(); await followLocation(); updateHeader();
  } catch (error) { showError(`${(error as Error).message} Recarga la página cuando el servidor esté disponible.`); }
  setInterval(() => { if (!busy) void refreshStatus(); }, 20000);
}
void init();
