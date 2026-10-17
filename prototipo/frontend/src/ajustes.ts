// Ventana de configuración de la cuenta: perfil, seguridad, preferencias, proyectos y datos.
// Los datos los pone main.ts; aquí solo se pintan y se envían los cambios a la API.

import { paintAvatar, preparePhoto } from './avatar';
import { onThemeChange, savedTheme, setTheme, type Theme } from './tema';

export type SettingsSection = 'perfil' | 'seguridad' | 'preferencias' | 'proyectos' | 'datos';
type Account = { id: string; username: string; display_name: string; avatar: number };
type Details = Account & { created_at: number; session_hours: number };
type Profile = { first_name: string; last_name: string; phone: string; email: string };
const PROFILE_FIELDS: [keyof Profile, string][] = [
  ['first_name', 'settings-first-name'], ['last_name', 'settings-last-name'],
  ['phone', 'settings-phone'], ['email', 'settings-email'],
];
type Role = 'owner' | 'editor' | 'viewer';
export type SettingsProject = { project_id: string; notebook_id: string; role: Role; stage: number; color: string; owner_name: string };
export type SettingsInvitation = { notebook_id: string; owner_name: string };

export type SettingsHooks = {
  api: <T>(path: string, options?: RequestInit) => Promise<T>;
  account: () => Account | null;
  projects: () => SettingsProject[];
  invitations: () => SettingsInvitation[];
  pendingTasks: () => number;
  onAccountChanged: (account: Account) => void;
  openProject: (projectId: string) => void;
  openNotifications: () => void;
  openGuide: () => void;
  endSession: () => Promise<void>;
};

const ROLES: Record<Role, string> = { owner: 'Propietario', editor: 'Puede editar', viewer: 'Puede ver' };
const json = (body: unknown): RequestInit => ({ method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;

export class SettingsController {
  private readonly dialog = $<HTMLDialogElement>('settings-dialog');
  private details: Details | null = null;
  private profile: Profile | null = null;

  constructor(private readonly hooks: SettingsHooks) {
    this.dialog.querySelectorAll<HTMLButtonElement>('.settings-tab').forEach(tab => {
      tab.addEventListener('click', () => this.show(tab.dataset.section as SettingsSection, true));
    });
    // Al cambiar de sección el foco va al título, para que el lector de pantalla lo anuncie.
    this.dialog.querySelectorAll<HTMLElement>('.settings-section h2').forEach(title => { title.tabIndex = -1; });
    $('settings-close').addEventListener('click', () => this.dialog.close());
    this.dialog.addEventListener('click', event => { if (event.target === this.dialog) this.dialog.close(); });
    for (const [, id] of PROFILE_FIELDS) $(id).addEventListener('input', () => this.syncProfileButton());
    $('settings-profile-form').addEventListener('submit', event => { event.preventDefault(); void this.saveProfile(); });
    $('settings-photo-change').addEventListener('click', () => $<HTMLInputElement>('settings-photo-input').click());
    $('settings-photo-input').addEventListener('change', () => void this.uploadPhoto());
    $('settings-photo-remove').addEventListener('click', () => void this.removePhoto());
    document.querySelectorAll<HTMLButtonElement>('[data-theme-choice]').forEach(button => {
      button.addEventListener('click', () => setTheme(button.dataset.themeChoice as Theme));
    });
    onThemeChange(() => this.renderTheme());
    this.renderTheme();
    $('settings-password-form').addEventListener('submit', event => { event.preventDefault(); void this.savePassword(); });
    $('settings-guide').addEventListener('click', () => { this.dialog.close(); hooks.openGuide(); });
    $('settings-open-notifications').addEventListener('click', () => { this.dialog.close(); hooks.openNotifications(); });
    $('settings-switch').addEventListener('click', () => void hooks.endSession());
    $('settings-logout').addEventListener('click', () => void hooks.endSession());
  }

  async open(section: SettingsSection = 'perfil') {
    this.renderAccount();
    this.renderProjects();
    for (const id of ['settings-profile-status', 'settings-photo-status', 'settings-password-status', 'settings-session-error']) this.status(id, '');
    $<HTMLFormElement>('settings-password-form').reset();
    this.show(section, false);
    if (!this.dialog.open) this.dialog.showModal();
    // Los campos se rellenan con lo que hay en el servidor, no con lo que se escribió y no
    // se guardó la última vez.
    this.profile = null;
    for (const [, id] of PROFILE_FIELDS) $<HTMLInputElement>(id).value = '';
    this.syncProfileButton();
    const [details, profile] = await Promise.allSettled([
      this.hooks.api<Details>('/auth/account'), this.hooks.api<Account & Profile>('/auth/profile'),
    ]);
    // La fecha es un dato adicional: sin ella la ventana funciona igual.
    if (details.status === 'fulfilled') this.details = details.value;
    if (profile.status === 'fulfilled') this.fillProfile(profile.value);
    else this.status('settings-profile-status', 'No se pudieron cargar tus datos. Cierra y vuelve a abrir la configuración.', 'error');
    this.renderAccount();
  }

  private fillProfile(profile: Profile) {
    this.profile = { first_name: profile.first_name, last_name: profile.last_name, phone: profile.phone, email: profile.email };
    for (const [key, id] of PROFILE_FIELDS) $<HTMLInputElement>(id).value = profile[key];
    this.syncProfileButton();
  }

  private formProfile(): Profile {
    const value = (id: string) => $<HTMLInputElement>(id).value.trim().replace(/\s+/g, ' ');
    return Object.fromEntries(PROFILE_FIELDS.map(([key, id]) => [key, value(id)])) as Profile;
  }

  private show(section: SettingsSection, focus: boolean) {
    this.dialog.querySelectorAll<HTMLElement>('.settings-section').forEach(panel => { panel.hidden = panel.dataset.section !== section; });
    this.dialog.querySelectorAll<HTMLButtonElement>('.settings-tab').forEach(tab => {
      if (tab.dataset.section === section) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current');
    });
    this.dialog.querySelector('.settings-main')!.scrollTop = 0;
    if (focus) this.dialog.querySelector<HTMLElement>(`.settings-section[data-section="${section}"] h2`)?.focus();
  }

  private renderAccount() {
    const account = this.hooks.account();
    const name = account?.display_name || 'Tu cuenta';
    const user = account ? `@${account.username}` : '';
    for (const id of ['settings-nav-avatar', 'settings-big-avatar']) paintAvatar($(id), name, account?.id, account?.avatar);
    $('settings-nav-name').textContent = name; $('settings-card-name').textContent = name;
    $('settings-nav-username').textContent = user; $('settings-card-username').textContent = user;
    $('settings-username').textContent = account?.username || '';
    const hasPhoto = Boolean(account?.avatar);
    $('settings-photo-change').querySelector('span')!.textContent = hasPhoto ? 'Cambiar foto' : 'Subir foto';
    $('settings-photo-remove').hidden = !hasPhoto;
    const created = this.details?.created_at;
    $('settings-since').textContent = created
      ? `En Hilo desde el ${new Date(created * 1000).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' })}`
      : '';
    if (this.details) $('settings-session-hours').textContent = `La sesión dura ${this.details.session_hours} horas; después Hilo te pide entrar de nuevo.`;
  }

  private syncProfileButton() {
    const form = this.formProfile();
    const changed = this.profile !== null && PROFILE_FIELDS.some(([key]) => form[key] !== this.profile![key]);
    $<HTMLButtonElement>('settings-profile-save').disabled = !changed;
  }

  private status(id: string, text: string, tone: 'ok' | 'error' | '' = '') {
    const node = $(id); node.textContent = text; node.dataset.tone = tone; node.hidden = !text && id === 'settings-session-error';
  }

  /** El mismo control que el servidor, para avisar sin esperar la respuesta. */
  private profileProblem(profile: Profile): [string, string] | null {
    if (!profile.first_name) return ['Escribe tu nombre.', 'settings-first-name'];
    const digits = profile.phone.replace(/\D/g, '').length;
    if (profile.phone && (!/^\+?[0-9 ()-]+$/.test(profile.phone) || digits < 7 || digits > 15)) {
      return ['Escribe el teléfono con números (de 7 a 15); puede empezar con +.', 'settings-phone'];
    }
    if (profile.email && !/^[^@\s]+@[^@\s]+\.[^@\s.]+$/.test(profile.email)) {
      return ['Ese correo no parece válido: revisa la @ y el dominio.', 'settings-email'];
    }
    return null;
  }

  private async saveProfile() {
    const profile = this.formProfile();
    const problem = this.profileProblem(profile);
    for (const [, id] of PROFILE_FIELDS) $(id).removeAttribute('aria-invalid');
    if (problem) {
      this.status('settings-profile-status', problem[0], 'error');
      $(problem[1]).setAttribute('aria-invalid', 'true'); $(problem[1]).focus(); return;
    }
    const button = $<HTMLButtonElement>('settings-profile-save');
    button.disabled = true;
    try {
      const saved = await this.hooks.api<Account & Profile>('/auth/profile', json(profile));
      this.hooks.onAccountChanged({ id: saved.id, username: saved.username, display_name: saved.display_name, avatar: saved.avatar });
      this.fillProfile(saved);
      this.renderAccount();
      this.status('settings-profile-status', 'Datos guardados.', 'ok');
    } catch (error) {
      this.status('settings-profile-status', (error as Error).message, 'error');
      this.syncProfileButton();
    }
  }

  private async uploadPhoto() {
    const input = $<HTMLInputElement>('settings-photo-input');
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    const button = $<HTMLButtonElement>('settings-photo-change');
    button.disabled = true;
    this.status('settings-photo-status', 'Subiendo la foto…');
    try {
      const photo = await preparePhoto(file);
      const account = await this.hooks.api<Account>('/auth/avatar', { method: 'PUT', headers: { 'Content-Type': photo.type }, body: photo });
      this.hooks.onAccountChanged(account);
      this.renderAccount();
      this.status('settings-photo-status', 'Foto actualizada.', 'ok');
    } catch (error) {
      this.status('settings-photo-status', (error as Error).message, 'error');
    } finally { button.disabled = false; }
  }

  private async removePhoto() {
    const button = $<HTMLButtonElement>('settings-photo-remove');
    button.disabled = true;
    try {
      const account = await this.hooks.api<Account>('/auth/avatar', { method: 'DELETE' });
      this.hooks.onAccountChanged(account);
      this.renderAccount();
      this.status('settings-photo-status', 'Foto quitada. Se muestran tus iniciales.', 'ok');
      $('settings-photo-change').focus();
    } catch (error) {
      this.status('settings-photo-status', (error as Error).message, 'error');
    } finally { button.disabled = false; }
  }

  private renderTheme() {
    const theme = savedTheme();
    document.querySelectorAll<HTMLButtonElement>('[data-theme-choice]').forEach(button => {
      button.setAttribute('aria-checked', String(button.dataset.themeChoice === theme));
    });
  }

  private async savePassword() {
    const [current, fresh, confirm] = ['settings-password-current', 'settings-password-new', 'settings-password-confirm']
      .map(id => $<HTMLInputElement>(id));
    const problem = !current.value ? ['Escribe tu contraseña actual.', current]
      : fresh.value.length < 10 ? ['La contraseña nueva necesita al menos 10 caracteres.', fresh]
        : fresh.value !== confirm.value ? ['Las contraseñas nuevas no coinciden.', confirm] : null;
    if (problem) { this.status('settings-password-status', problem[0] as string, 'error'); (problem[1] as HTMLInputElement).focus(); return; }
    const button = $('settings-password-form').querySelector<HTMLButtonElement>('button[type="submit"]')!;
    button.disabled = true;
    try {
      await this.hooks.api('/auth/password', json({ current_password: current.value, new_password: fresh.value, confirm_password: confirm.value }));
      $<HTMLFormElement>('settings-password-form').reset();
      this.status('settings-password-status', 'Contraseña cambiada. Tus otras sesiones se cerraron.', 'ok');
    } catch (error) {
      this.status('settings-password-status', (error as Error).message, 'error');
    } finally { button.disabled = false; }
  }

  private renderProjects() {
    const projects = this.hooks.projects();
    const invitations = this.hooks.invitations();
    $('settings-stat-own').textContent = String(projects.filter(item => item.role === 'owner').length);
    $('settings-stat-shared').textContent = String(projects.filter(item => item.role !== 'owner').length);
    $('settings-stat-invitations').textContent = String(invitations.length);
    $('settings-stat-tasks').textContent = String(this.hooks.pendingTasks());
    $('settings-invitations').hidden = !invitations.length;
    $('settings-invitations-text').textContent = invitations.map(item => `«${item.notebook_id}», de ${item.owner_name}`).join(' · ');
    const list = $('settings-projects'); list.replaceChildren();
    for (const project of projects) {
      const item = document.createElement('li'); item.className = 'settings-project'; item.dataset.color = project.color;
      const dot = document.createElement('span'); dot.className = 'settings-project-dot'; dot.setAttribute('aria-hidden', 'true');
      const text = document.createElement('div');
      const title = document.createElement('strong'); title.textContent = project.notebook_id;
      const meta = document.createElement('span');
      meta.textContent = project.role === 'owner' ? `Etapa ${project.stage}` : `Etapa ${project.stage} · de ${project.owner_name}`;
      text.append(title, meta);
      const role = document.createElement('span'); role.className = 'settings-role'; role.dataset.role = project.role; role.textContent = ROLES[project.role];
      const open = document.createElement('button'); open.type = 'button'; open.className = 'button quiet'; open.textContent = 'Abrir';
      open.setAttribute('aria-label', `Abrir ${project.notebook_id}`);
      open.addEventListener('click', () => { this.dialog.close(); this.hooks.openProject(project.project_id); });
      item.append(dot, text, role, open); list.append(item);
    }
    $('settings-projects-empty').hidden = projects.length > 0;
  }
}
