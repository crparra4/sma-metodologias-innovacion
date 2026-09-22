export type EntryKind = 'tarea' | 'recordatorio' | 'reunion';
export type Task = { id: string; title: string; kind: EntryKind; due_at: string; ends_at: string | null; priority: 'high' | 'medium' | 'low'; notebook_id: string | null; project_id?: string | null; project_role?: 'owner' | 'editor' | 'viewer'; completed: boolean; updated_at?: string };
export const kindLabels: Record<EntryKind, string> = { tarea: 'Tarea', recordatorio: 'Recordatorio', reunion: 'Reunión' };
export const kindIcons: Record<EntryKind, string> = { tarea: 'task', recordatorio: 'bell', reunion: 'meeting' };
export const localDateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
export function taskTiming(task: Task, now = new Date()): { tone: string; label: string } {
  if (task.completed) return { tone: 'done', label: 'Completada' };
  const due = new Date(task.due_at); const hours = (due.getTime() - now.getTime()) / 3600000;
  if (hours < 0) return { tone: 'overdue', label: 'Vencida' };
  const dayGap = (Date.UTC(due.getFullYear(), due.getMonth(), due.getDate()) - Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())) / 86400000;
  const label = dayGap === 0 ? 'Hoy' : dayGap === 1 ? 'Mañana' : `En ${dayGap} días`;
  return { tone: hours <= 24 ? 'soon' : hours <= 72 ? 'near' : 'later', label };
}

/** Fin efectivo de una entrada: su hora de fin o, si es puntual, 30 minutos despues. */
export function entryEnd(task: Task): number {
  return task.ends_at ? Date.parse(task.ends_at) : Date.parse(task.due_at) + 30 * 60000;
}

/**
 * Carriles de un dia en la vista semanal. Las entradas que se solapan en el tiempo
 * se reparten en columnas; cada grupo de solapes usa el ancho completo.
 */
export function dayLanes(entries: Task[]): Map<string, { lane: number; lanes: number }> {
  const sorted = [...entries].sort((a, b) => Date.parse(a.due_at) - Date.parse(b.due_at) || entryEnd(b) - entryEnd(a));
  const result = new Map<string, { lane: number; lanes: number }>();
  let group: { task: Task; lane: number }[] = []; let groupEnd = -Infinity; let laneEnds: number[] = [];
  const close = () => { const lanes = Math.max(1, laneEnds.length); for (const item of group) result.set(item.task.id, { lane: item.lane, lanes }); };
  for (const task of sorted) {
    const start = Date.parse(task.due_at);
    if (start >= groupEnd) { close(); group = []; laneEnds = []; groupEnd = -Infinity; }
    let lane = laneEnds.findIndex(end => end <= start);
    if (lane < 0) { lane = laneEnds.length; laneEnds.push(0); }
    laneEnds[lane] = entryEnd(task); groupEnd = Math.max(groupEnd, entryEnd(task));
    group.push({ task, lane });
  }
  close();
  return result;
}

/** Lo que la campanita avisa: vencido, lo que queda de hoy y los proximos tres dias. */
export function notificationGroups(tasks: Task[], now = new Date()) {
  const pending = tasks.filter(task => !task.completed).sort((a, b) => Date.parse(a.due_at) - Date.parse(b.due_at));
  const today = localDateKey(now);
  const limit = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 4).getTime();
  const overdue = pending.filter(task => Date.parse(task.due_at) < now.getTime());
  const todayLeft = pending.filter(task => Date.parse(task.due_at) >= now.getTime() && localDateKey(new Date(task.due_at)) === today);
  const soon = pending.filter(task => localDateKey(new Date(task.due_at)) !== today && Date.parse(task.due_at) >= now.getTime() && Date.parse(task.due_at) < limit);
  return { overdue, today: todayLeft, soon, alert: overdue.length + todayLeft.length };
}
