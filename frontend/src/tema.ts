// Tema claro, oscuro o el del sistema.
//
// Las hojas de estilo tienen más de 1.600 colores escritos a mano. En vez de duplicar cada
// regla, el tema oscuro se arma al vuelo: recorre las reglas ya cargadas y, para cada color,
// calcula su versión oscura según el papel que cumple. Los fondos claros pasan a oscuros, los
// textos oscuros a claros y los bordes a un gris medio; los colores intermedios (el azul de
// Hilo, los acentos, los post-its fuertes) se quedan como están. Las reglas nuevas van bajo
// `:root[data-theme="oscuro"]`, así que en el tema claro no cambian nada.
//
// Un color que se vea mal se corrige a mano en `tema-oscuro.css`, con el prefijo
// `:root[data-theme="oscuro"][data-theme-ready]`: pesa más que lo generado y gana siempre.

export type Theme = 'claro' | 'oscuro' | 'sistema';
const KEY = 'hilo-tema';
const SHEET_ID = 'tema-oscuro-generado';
const DARK_PAGE = '#121822';
const system = window.matchMedia('(prefers-color-scheme: dark)');
const listeners = new Set<(theme: Theme) => void>();

export function savedTheme(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return value === 'oscuro' || value === 'sistema' ? value : 'claro';
  } catch { return 'claro'; }
}

export function setTheme(theme: Theme) {
  try { localStorage.setItem(KEY, theme); } catch { /* sin almacenamiento el cambio dura la visita */ }
  applyTheme(theme);
  listeners.forEach(listener => listener(theme));
}

export function onThemeChange(listener: (theme: Theme) => void) { listeners.add(listener); }

export function initTheme() {
  applyTheme(savedTheme());
  system.addEventListener('change', () => { if (savedTheme() === 'sistema') applyTheme('sistema'); });
  // Si otra pestaña cambia el tema, esta lo sigue.
  window.addEventListener('storage', event => { if (event.key === KEY) { const theme = savedTheme(); applyTheme(theme); listeners.forEach(listener => listener(theme)); } });
}

function applyTheme(theme: Theme) {
  const dark = theme === 'oscuro' || (theme === 'sistema' && system.matches);
  if (dark) buildDarkSheet();
  const root = document.documentElement;
  root.dataset.theme = dark ? 'oscuro' : 'claro';
  root.dataset.themeReady = '';
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? DARK_PAGE : '#f3f5f9');
}

// ---- Colores --------------------------------------------------------------------------

type Rgba = [number, number, number, number];
type Role = 'bg' | 'text' | 'border' | 'accent' | 'highlight' | 'keep';

const COLOR = /#[0-9a-f]{3,8}\b|rgba?\([^)]*\)|\b(?:white|black)\b/gi;

function parse(token: string): Rgba | null {
  const lower = token.toLowerCase();
  if (lower === 'white') return [255, 255, 255, 1];
  if (lower === 'black') return [0, 0, 0, 1];
  if (lower.startsWith('#')) {
    let hex = lower.slice(1);
    if (hex.length === 3 || hex.length === 4) hex = [...hex].map(char => char + char).join('');
    if (hex.length !== 6 && hex.length !== 8) return null;
    const value = (index: number) => parseInt(hex.slice(index, index + 2), 16);
    return [value(0), value(2), value(4), hex.length === 8 ? value(6) / 255 : 1];
  }
  const parts = lower.slice(lower.indexOf('(') + 1, -1).split(/[\s,/]+/).filter(Boolean);
  if (parts.length < 3) return null;
  const channel = (part: string) => part.endsWith('%') ? parseFloat(part) * 2.55 : parseFloat(part);
  const alpha = parts[3] === undefined ? 1 : parts[3].endsWith('%') ? parseFloat(parts[3]) / 100 : parseFloat(parts[3]);
  const rgba: Rgba = [channel(parts[0]), channel(parts[1]), channel(parts[2]), alpha];
  return rgba.some(Number.isNaN) ? null : rgba;
}

// OKLab: la claridad que da es la que percibe el ojo, así un amarillo y un azul con el
// mismo valor se ven igual de claros (con HSL no pasa).
const toLinear = (value: number) => { const c = value / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const fromLinear = (value: number) => 255 * (value <= 0.0031308 ? 12.92 * value : 1.055 * value ** (1 / 2.4) - 0.055);

function toOklch([r, g, b]: Rgba): [number, number, number] {
  const [lr, lg, lb] = [toLinear(r), toLinear(g), toLinear(b)];
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  const L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
  const a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const bb = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  return [L, Math.hypot(a, bb), Math.atan2(bb, a)];
}

function fromOklch(L: number, C: number, h: number): [number, number, number] {
  const a = C * Math.cos(h), b = C * Math.sin(h);
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const rgb = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  return rgb.map(value => Math.round(Math.min(255, Math.max(0, fromLinear(value))))) as [number, number, number];
}

function darken(color: Rgba, role: Role): Rgba | null {
  const [L, C, h] = toOklch(color);
  let next: [number, number] | null = null;
  // Un velo casi transparente (el blanco al 15 % sobre la barra azul) depende de lo que tiene
  // debajo: se deja como está.
  if (role === 'bg' && L >= 0.6 && color[3] >= 0.35) next = [0.19 + (1 - L) * 0.42, C * 0.55];
  else if (role === 'border' && L >= 0.6) next = [0.31 + (1 - L) * 0.4, C * 0.6];
  else if (role === 'text' && L <= 0.62) next = [0.95 - (L / 0.62) * 0.25, Math.min(C, 0.14)];
  // Un acento en variable sirve a la vez de texto y de fondo de botón con letra blanca: se
  // aclara solo un poco, lo justo para leerse sobre el fondo oscuro sin perder el blanco.
  else if (role === 'accent' && L < 0.66 && C > 0.06) next = [L + (0.66 - L) * 0.6, C];
  // El resaltador amarillo se apaga para que la letra clara se lea encima.
  else if (role === 'highlight' && L >= 0.6) next = [0.46, C * 0.75];
  if (!next) return null;
  return [...fromOklch(next[0], next[1], h), color[3]];
}

const format = ([r, g, b, a]: Rgba) => a >= 1 ? `rgb(${r} ${g} ${b})` : `rgb(${r} ${g} ${b} / ${Math.round(a * 1000) / 1000})`;

function convert(value: string, role: Role): string | null {
  if (role === 'keep' || !COLOR.test(value)) return null;
  COLOR.lastIndex = 0;
  let changed = false;
  const result = value.replace(COLOR, token => {
    const color = parse(token);
    const dark = color && darken(color, role);
    if (!dark) return token;
    changed = true;
    return format(dark);
  });
  return changed ? result : null;
}

// El papel de cada propiedad. Las variables se reconocen por su nombre (`--note-paper`,
// `--folder-ink`); una que no se reconoce es un acento y se deja.
function roleOf(property: string): Role {
  if (property.startsWith('--')) {
    // Las carpetas conservan el color que eligió la persona; las sombras ya son oscuras.
    if (/folder|sombra|shadow/.test(property)) return 'keep';
    if (/resaltador|highlight/.test(property)) return 'highlight';
    if (/ink|tinta|muted|lapiz|text|fg/.test(property)) return 'text';
    if (/bg|paper|papel|hoja|light|luz|back|fold|soft|fondo|surface/.test(property)) return 'bg';
    if (/line|border/.test(property)) return 'border';
    return 'accent';
  }
  if (property.startsWith('background')) return 'bg';
  if (property.startsWith('border') || property.startsWith('outline') || property === 'column-rule-color') return 'border';
  if (property === 'color' || property === 'fill' || property === 'stroke' || property === 'caret-color'
    || property === 'text-decoration-color' || property === '-webkit-text-fill-color') return 'text';
  if (property === 'box-shadow') return 'bg';
  return 'keep';
}

// ---- Reglas ---------------------------------------------------------------------------

const SHORTHANDS = ['background', 'border', 'border-top', 'border-right', 'border-bottom', 'border-left', 'border-color', 'outline'];

const scope = (selector: string) => selector.split(/,(?![^()]*\))/).map(part => {
  const trimmed = part.trim();
  if (trimmed.startsWith(':root')) return trimmed.replace(':root', ':root[data-theme="oscuro"]');
  if (/^html\b/.test(trimmed)) return trimmed.replace(/^html/, 'html[data-theme="oscuro"]');
  return `:root[data-theme="oscuro"] ${trimmed}`;
}).join(',');

function translate(rules: CSSRuleList): string {
  let output = '';
  for (const rule of Array.from(rules)) {
    if (rule instanceof CSSStyleRule) {
      // Una regla que ya nombra un tema (las miniaturas de Preferencias) se deja tal cual.
      if (rule.selectorText.includes('data-theme=')) continue;
      const declarations: string[] = [];
      for (let index = 0; index < rule.style.length; index++) {
        const property = rule.style.item(index);
        const value = convert(rule.style.getPropertyValue(property), roleOf(property));
        if (value) declarations.push(`${property}:${value}${rule.style.getPropertyPriority(property) ? ' !important' : ''}`);
      }
      // Un atajo que mezcla una variable con colores escritos (`background: var(--hoja)
      // repeating-linear-gradient(… #edf1f9 …)`) deja vacías sus partes: se traduce entero.
      for (const shorthand of SHORTHANDS) {
        const original = rule.style.getPropertyValue(shorthand);
        const value = original.includes('var(') && convert(original, roleOf(shorthand));
        if (value) declarations.push(`${shorthand}:${value}${rule.style.getPropertyPriority(shorthand) ? ' !important' : ''}`);
      }
      if (declarations.length) output += `${scope(rule.selectorText)}{${declarations.join(';')}}\n`;
    } else if (rule instanceof CSSGroupingRule) {
      // @media, @supports, @container: se conserva la condición y se traduce lo de adentro.
      const inner = translate(rule.cssRules);
      if (inner) output += `${rule.cssText.slice(0, rule.cssText.indexOf('{'))}{\n${inner}}\n`;
    }
  }
  return output;
}

let built = false;
function buildDarkSheet() {
  if (built) return;
  let css = `:root[data-theme="oscuro"]{color-scheme:dark;background:${DARK_PAGE}}\n`;
  for (const sheet of Array.from(document.styleSheets)) {
    if ((sheet.ownerNode as HTMLElement | null)?.id === SHEET_ID) continue;
    try { css += translate(sheet.cssRules); } catch { /* hoja de otro origen: no se puede leer */ }
  }
  const style = document.createElement('style'); style.id = SHEET_ID; style.textContent = css;
  document.head.append(style);
  built = true;
}
