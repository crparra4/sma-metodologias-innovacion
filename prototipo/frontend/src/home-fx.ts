// Inicio como cuaderno: portada con saludo y animaciones al interactuar.
// Todo es decorativo: no guarda nada ni cambia datos. Con «reducir movimiento» activo en el
// sistema, los estallidos no se muestran y los números aparecen sin conteo.

const calm = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const pick = <T,>(items: T[]) => items[Math.floor(Math.random() * items.length)];
const node = <T extends HTMLElement>(id: string) => document.getElementById(id) as T | null;

let layer: HTMLElement | null = null;

/** Lanza piezas (emojis o la palabra «hoja») desde un punto de la pantalla. */
export function burst(x: number, y: number, items: string[], count = 9) {
  if (calm()) return;
  if (!layer) { layer = document.createElement('div'); layer.className = 'fx-layer'; layer.setAttribute('aria-hidden', 'true'); document.body.append(layer); }
  for (let index = 0; index < count; index += 1) {
    const piece = document.createElement('span');
    const item = pick(items);
    if (item === 'hoja') piece.className = 'fx-piece fx-sheet'; else { piece.className = 'fx-piece'; piece.textContent = item; }
    piece.style.left = `${x}px`; piece.style.top = `${y}px`;
    layer.append(piece);
    // Abanico hacia arriba, con caída al final: como papel o confeti que se suelta.
    const angle = -Math.PI / 2 + (Math.random() - 0.5) * 2.3;
    const reach = 60 + Math.random() * 90;
    const dx = Math.cos(angle) * reach; const dy = Math.sin(angle) * reach;
    const spin = (Math.random() - 0.5) * 520;
    const animation = piece.animate([
      { transform: 'translate(-50%,-50%) scale(.3) rotate(0deg)', opacity: 0 },
      { transform: `translate(calc(-50% + ${dx * 0.7}px),calc(-50% + ${dy}px)) scale(1.15) rotate(${spin * 0.5}deg)`, opacity: 1, offset: 0.35 },
      { transform: `translate(calc(-50% + ${dx}px),calc(-50% + ${dy + 95 + Math.random() * 50}px)) scale(.85) rotate(${spin}deg)`, opacity: 0 },
    ], { duration: 850 + Math.random() * 450, easing: 'cubic-bezier(.2,.7,.4,1)', delay: index * 18 });
    animation.onfinish = () => piece.remove();
  }
}

const centerOf = (element: Element) => { const box = element.getBoundingClientRect(); return [box.left + box.width / 2, box.top + box.height / 2] as const; };

function countTo(target: HTMLElement, value: number) {
  const from = Number(target.dataset.value || 0);
  target.dataset.value = String(value);
  if (calm() || from === value) { target.textContent = String(value); return; }
  const started = performance.now();
  const step = (now: number) => {
    const progress = Math.min(1, (now - started) / 480);
    target.textContent = String(Math.round(from + (value - from) * (1 - (1 - progress) ** 3)));
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export type HomeSummary = { name: string; projects: number; pending: number; today: number; overdue: number };

const stats: { key: 'projects' | 'pending' | 'today'; one: string; many: string }[] = [
  { key: 'projects', one: 'proyecto', many: 'proyectos' },
  { key: 'pending', one: 'pendiente', many: 'pendientes' },
  { key: 'today', one: 'para hoy', many: 'para hoy' },
];

/** Saludo, fecha y los tres contadores de la portada. Solo muestra datos reales. */
export function renderHomeHero(summary: HomeSummary) {
  const greeting = node('home-greeting'); const box = node('home-stats');
  if (!greeting || !box) return;
  const now = new Date(); const hour = now.getHours();
  const first = summary.name.trim().split(/\s+/)[0];
  const known = first && summary.name !== 'Tu cuenta';
  greeting.textContent = `${hour < 12 ? '¡Buenos días' : hour < 19 ? '¡Buenas tardes' : '¡Buenas noches'}${known ? ',' : '!'}`;
  node('home-name')!.textContent = known ? `${first}!` : '';
  const date = new Intl.DateTimeFormat('es-CO', { weekday: 'long', day: 'numeric', month: 'long' }).format(now);
  node('home-date')!.textContent = date.charAt(0).toLocaleUpperCase('es') + date.slice(1);
  node('home-summary')!.textContent = summary.overdue
    ? `Tienes ${summary.overdue} ${summary.overdue === 1 ? 'tarea vencida' : 'tareas vencidas'}. Empieza por ahí.`
    : summary.today
      ? `Hoy tienes ${summary.today} ${summary.today === 1 ? 'pendiente' : 'pendientes'} en la agenda.`
      : summary.projects ? 'Abre un proyecto para continuar donde lo dejaste.' : 'Crea tu primer proyecto para empezar a rayar ideas.';
  if (!box.childElementCount) {
    for (const stat of stats) {
      const chip = document.createElement('button'); chip.type = 'button'; chip.className = 'hero-stat'; chip.dataset.stat = stat.key;
      chip.append(document.createElement('strong'), document.createElement('span'));
      box.append(chip);
    }
  }
  for (const stat of stats) {
    const chip = box.querySelector<HTMLElement>(`[data-stat="${stat.key}"]`)!;
    const value = summary[stat.key];
    const label = value === 1 ? stat.one : stat.many;
    countTo(chip.querySelector('strong')!, value);
    chip.querySelector('span')!.textContent = label;
    chip.setAttribute('aria-label', `${value} ${label}`);
  }
}

const cheers = ['¡A rayar ideas!', 'Un paso a la vez.', '¿Qué problema resolvemos hoy?', 'Primero el problema, después la solución.', '¡Buena esa!'];
let bubbleTimer = 0; let cheer = 0;

export function initHomeFx() {
  const home = node('home-view');
  if (!home) return;

  // Delegado: las carpetas, los días y las tareas se vuelven a pintar muchas veces.
  home.addEventListener('click', event => {
    const target = event.target as HTMLElement;
    const at = [event.clientX, event.clientY] as const;
    const folder = target.closest('.project-folder');
    if (folder) { burst(at[0], at[1], ['hoja', 'hoja', '📄', '✏️', '📎', '⭐'], 10); return; }
    const tile = target.closest('.tool-tile');
    if (tile) { burst(at[0], at[1], ['💡', '🧩', '🔍', '✏️', '⭐'], 7); return; }
    if (target.closest('.cal-day')) { burst(at[0], at[1], ['✏️'], 1); return; }
    if (target.closest('#home-new-project,#empty-new-project,.project-add')) { burst(at[0], at[1], ['hoja', '✨', '📁', '✏️'], 8); return; }
    if (target.closest('#new-task')) { burst(at[0], at[1], ['📌', '✏️', '🗓️'], 6); return; }
    const chip = target.closest<HTMLElement>('.hero-stat');
    if (chip) {
      chip.classList.remove('is-popped'); void chip.offsetWidth; chip.classList.add('is-popped');
      const stat = chip.dataset.stat;
      if (stat === 'projects') { burst(...centerOf(chip), ['📁', '📂'], 5); node<HTMLInputElement>('project-search')?.focus(); }
      else {
        burst(...centerOf(chip), stat === 'today' ? ['⏰', '☀️'] : ['📌', '✏️'], 5);
        (stat === 'today' ? node('cal-today') : document.querySelector<HTMLElement>('[data-task-filter="upcoming"]'))?.click();
        node('tasks-heading')?.scrollIntoView({ behavior: calm() ? 'auto' : 'smooth', block: 'center' });
      }
    }
  });

  // Completar una tarea es el momento de celebrar; reabrirla no.
  home.addEventListener('change', event => {
    const box = event.target as HTMLInputElement;
    if (box.type === 'checkbox' && box.checked && box.closest('.task-row')) burst(...centerOf(box), ['🎉', '⭐', '✅', '💪', '✏️'], 12);
  });

  const mascot = node('home-mascot'); const bubble = node('home-bubble');
  mascot?.addEventListener('click', () => {
    mascot.classList.remove('is-jumping'); void mascot.offsetWidth; mascot.classList.add('is-jumping');
    burst(...centerOf(mascot), ['✏️', '⭐', '💡', '🎈', '📝'], 10);
    if (!bubble) return;
    bubble.textContent = cheers[cheer % cheers.length]; cheer += 1;
    bubble.classList.add('is-visible');
    window.clearTimeout(bubbleTimer);
    bubbleTimer = window.setTimeout(() => bubble.classList.remove('is-visible'), 2600);
  });
}

/** Animaciones de la vista Calendario: pasar de hoja, marcar un día, celebrar lo completado. */
export function initCalendarFx() {
  const view = node('calendar-view');
  if (!view) return;
  const turn = (direction: 'next' | 'prev') => {
    const grid = node('calv-grid');
    if (!grid || calm()) return;
    // main.ts ya repintó la cuadrícula en este mismo clic; la clase solo dispara el paso de hoja.
    grid.classList.remove('is-turning-next', 'is-turning-prev'); void grid.offsetWidth;
    grid.classList.add(`is-turning-${direction}`);
    window.setTimeout(() => grid.classList.remove(`is-turning-${direction}`), 400);
  };
  view.addEventListener('click', event => {
    const target = event.target as HTMLElement;
    const at = [event.clientX, event.clientY] as const;
    if (target.closest('#calv-next')) { turn('next'); return; }
    if (target.closest('#calv-prev')) { turn('prev'); return; }
    if (target.closest('[data-calv-mode]')) { turn('next'); return; }
    if (target.closest('#calv-today')) { turn('next'); burst(at[0], at[1], ['☀️', '📍'], 4); return; }
    if (target.closest('#calv-new-entry,.calv-add,.calv-day-empty .button')) { burst(at[0], at[1], ['📌', '✏️', '🗓️'], 6); return; }
    if (target.closest('.calv-chip,.calv-block,.calv-item,.calv-filter,.calv-project-filter')) return;
    if (target.closest('.calv-cell,.calv-week-day')) burst(at[0], at[1], ['✏️'], 1);
  });
  view.addEventListener('change', event => {
    const box = event.target as HTMLInputElement;
    if (box.classList.contains('calv-item-check') && box.checked) burst(...centerOf(box), ['🎉', '⭐', '✅', '💪', '✏️'], 12);
  });
}

/** Animaciones del chat: enviar un mensaje, recibir la respuesta, guardar o copiar. */
export function initChatFx() {
  const form = node<HTMLFormElement>('chat-form'); const messages = node('messages'); const panel = node('chat-panel');
  if (!form || !messages || !panel) return;
  let waiting = false;
  // En captura: main.ts vacía el cuadro de texto en este mismo evento.
  form.addEventListener('submit', () => {
    const send = node<HTMLButtonElement>('send'); const text = node<HTMLTextAreaElement>('message');
    if (!send || send.disabled || !text?.value.trim()) return;
    waiting = true;
    burst(...centerOf(send), ['✏️', '💬', '✨'], 6);
  }, true);
  // La respuesta ya verificada reemplaza a la tarjeta «pensando»: ahí se celebra, una sola vez.
  new MutationObserver(records => {
    if (!waiting) return;
    for (const record of records) for (const added of record.addedNodes) {
      if (!(added instanceof HTMLElement) || !added.matches('.assistant-turn:not(.pending)')) continue;
      waiting = false;
      const avatar = added.querySelector('.turn-avatar');
      if (avatar) burst(...centerOf(avatar), ['💡', '✨', '📝'], 5);
      return;
    }
  }).observe(messages, { childList: true });
  panel.addEventListener('click', event => {
    const target = event.target as HTMLElement;
    const at = [event.clientX, event.clientY] as const;
    if (target.closest('.save-turn')) burst(at[0], at[1], ['📌', '📝', '⭐'], 6);
    else if (target.closest('.copy-button')) burst(at[0], at[1], ['📋', '✨'], 4);
    else if (target.closest('.welcome-card')) burst(at[0], at[1], ['✏️', '💡', '⭐'], 6);
  });
}

/** Animaciones del tablero: Post-its y Árbol de problemas (con su análisis de 5 porqués). */
export function initBoardFx() {
  const board = node('project-workspace');
  if (!board) return;
  board.addEventListener('click', event => {
    const target = event.target as HTMLElement;
    const at = [event.clientX, event.clientY] as const;
    const hit = (selector: string) => { const found = target.closest<HTMLButtonElement>(selector); return found && !found.disabled ? found : null; };
    if (hit('#new-note,#save-selection')) burst(at[0], at[1], ['📌', '📝', '⭐'], 6);
    else if (hit('#problem-tree-add-effect')) burst(at[0], at[1], ['🍃', '🌿'], 5);
    else if (hit('#problem-tree-add-cause')) burst(at[0], at[1], ['🌱', '🪵'], 5);
    else if (hit('#problem-tree-save')) burst(at[0], at[1], ['🌳', '✨', '🍃'], 8);
    else if (hit('#problem-tree-diagnose')) burst(at[0], at[1], ['🔍', '✏️'], 5);
    else if (hit('.tree-why')) burst(at[0], at[1], ['❓', '✏️'], 5);
    else if (hit('.pestel-add,.pestel-suggestion-add')) burst(at[0], at[1], ['✏️', '📌'], 5);
    else if (hit('.pestel-star[aria-pressed="true"]')) burst(at[0], at[1], ['⭐', '✨'], 6);
    else if (hit('#pestel-save')) burst(at[0], at[1], ['🧭', '✨', '📒'], 8);
    else if (hit('#empathy-save')) burst(at[0], at[1], ['🫶', '✨', '📒'], 8);
    else if (hit('#journey-save')) burst(at[0], at[1], ['🧗', '✨', '📒'], 8);
    else if (hit('.journey-add-stage')) burst(at[0], at[1], ['👣', '➡️'], 5);
    else if (hit('.journey-add')) burst(at[0], at[1], ['✏️', '📌'], 4);
    else if (hit('.journey-ask,.journey-persona-ask')) burst(at[0], at[1], ['💬', '✏️'], 5);
    else if (hit('.journey-critical[aria-pressed="true"]')) burst(at[0], at[1], ['⭐', '🚩'], 5);
    else if (hit('.empathy-ask')) burst(at[0], at[1], ['💬', '✏️'], 5);
    else if (hit('.pestel-ask')) burst(at[0], at[1], ['💬', '✏️'], 5);
    else if (hit('.why-button.primary')) burst(at[0], at[1], ['✏️', '⭐'], 5);
  });
}
