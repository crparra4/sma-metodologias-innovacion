// Eventos de Google Calendar y Outlook en la vista Calendario. Son de solo lectura: se piden
// para el rango visible y no se guardan en Hilo. Las cuentas se conectan en Ajustes.

import { localDateKey } from './agenda';

export type ProviderId = 'google' | 'microsoft';
export type ExternalEvent = { id: string; proveedor: ProviderId; titulo: string; inicio: string; fin: string; todo_el_dia: boolean; enlace: string | null };
export type ExternalError = { proveedor: ProviderId; mensaje: string; reconectar: boolean };
export type ProviderStatus = { id: ProviderId; nombre: string; configurado: boolean; conectado: boolean; cuenta: string | null };

export const providerNames: Record<ProviderId, string> = { google: 'Google Calendar', microsoft: 'Outlook' };

const addDays = (key: string, days: number) => {
  const date = new Date(`${key}T12:00:00`); date.setDate(date.getDate() + days); return localDateKey(date);
};

/** Días en que aparece el evento. Uno de todo el día termina el día anterior a `fin`. */
export function eventDays(event: ExternalEvent): string[] {
  if (!event.todo_el_dia) return [localDateKey(new Date(event.inicio))];
  const days: string[] = [];
  for (let day = event.inicio; day < event.fin && days.length < 62; day = addDays(day, 1)) days.push(day);
  return days.length ? days : [event.inicio];
}

export function eventsOn(events: ExternalEvent[], key: string): ExternalEvent[] {
  return events.filter(event => eventDays(event).includes(key))
    .sort((a, b) => Number(b.todo_el_dia) - Number(a.todo_el_dia) || Date.parse(a.inicio) - Date.parse(b.inicio));
}

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;

export class ExternalCalendars {
  events: ExternalEvent[] = [];
  errors: ExternalError[] = [];
  readonly hidden = new Set<ProviderId>();
  private connected: ProviderId[] = [];
  private loadedRange = '';
  private pending = '';

  constructor(private readonly api: Api, private readonly changed: () => void, private readonly warn: (error: ExternalError) => void) {}

  get providers(): ProviderId[] { return this.connected; }
  visible(): ExternalEvent[] { return this.events.filter(event => !this.hidden.has(event.proveedor)); }

  /** Estado de las conexiones; si cambió, vuelve a pedir los eventos. */
  async refresh() {
    try {
      const { proveedores } = await this.api<{ proveedores: ProviderStatus[] }>('/calendarios');
      this.connected = proveedores.filter(item => item.conectado).map(item => item.id);
    } catch { this.connected = []; }
    this.loadedRange = '';
    if (!this.connected.length) { this.events = []; this.errors = []; }
    this.changed();
  }

  /** Pide los eventos del rango si todavía no están; al llegar, vuelve a pintar. */
  ensure(from: Date, to: Date) {
    if (!this.connected.length) return;
    const range = `${from.toISOString()}|${to.toISOString()}`;
    if (range === this.loadedRange || range === this.pending) return;
    this.pending = range;
    const query = new URLSearchParams({ desde: from.toISOString(), hasta: to.toISOString() });
    void this.api<{ eventos: ExternalEvent[]; errores: ExternalError[] }>(`/calendario-externo?${query}`)
      .then(data => {
        if (this.pending !== range) return;
        this.events = data.eventos; this.errors = data.errores; this.loadedRange = range;
        for (const error of data.errores) this.warn(error);
        if (data.errores.some(error => error.reconectar)) void this.refresh(); else this.changed();
      })
      .catch(() => { /* sin conexión: se reintenta al cambiar de periodo */ })
      .finally(() => { if (this.pending === range) this.pending = ''; });
  }
}
