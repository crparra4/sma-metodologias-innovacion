export type AuthLanguage = 'es' | 'en';

const es = {
  loginTitle: 'Tu espacio para las ideas.', registerTitle: 'Haz espacio para tus ideas.',
  loginIntro: 'Inicia sesión en tu cuenta de Hilo', registerIntro: 'Crea tu cuenta de Hilo',
  name: 'Tu nombre', namePlaceholder: 'Como quieres aparecer en el chat',
  username: 'Usuario', usernamePlaceholder: 'Escribe tu nombre de usuario…',
  usernameHint: 'Usa el usuario de tu cuenta en esta computadora.',
  password: 'Contraseña', passwordPlaceholder: 'Escribe tu contraseña…',
  passwordHint: 'Usa al menos 10 caracteres.', confirmPassword: 'Confirma tu contraseña',
  continue: 'Continuar', login: 'Iniciar sesión', register: 'Crear cuenta', back: 'Cambiar usuario',
  alternatives: 'Otros métodos de acceso', divider: 'o continúa con', soon: 'Próximamente',
  providersHint: 'Estos accesos estarán disponibles próximamente.',
  newUser: '¿Es tu primera vez?', existingUser: '¿Ya tienes una cuenta?',
  loginNote: 'Tus datos permanecen en esta computadora.',
  registerNote: 'La primera cuenta conservará los proyectos que ya están en esta computadora. Cada nueva cuenta tendrá su propio cuaderno.',
  language: 'Idioma', creating: 'Creando cuenta…', entering: 'Entrando…',
  invalidUsername: 'Usa de 3 a 40 letras, números, puntos, guiones o guiones bajos para el usuario.',
  missingName: 'Escribe tu nombre.', shortPassword: 'La contraseña necesita al menos 10 caracteres.',
  passwordMismatch: 'Las contraseñas no coinciden.', missingPassword: 'Escribe tu contraseña.',
  wrongCredentials: 'Usuario o contraseña incorrectos.', duplicateUser: 'Ese usuario ya existe. Elige otro.',
  sessionError: 'No se pudo comprobar tu sesión.', reload: 'Recarga la página.',
  requestError: 'No se pudo completar el acceso. Inténtalo de nuevo.',
};
export type AuthTextKey = keyof typeof es;
const en: Record<AuthTextKey, string> = {
  loginTitle: 'Your space for ideas.', registerTitle: 'Make room for your ideas.',
  loginIntro: 'Log in to your Hilo account', registerIntro: 'Create your Hilo account',
  name: 'Your name', namePlaceholder: 'How you want to appear in the chat',
  username: 'Username', usernamePlaceholder: 'Enter your username…',
  usernameHint: 'Use your account username on this computer.',
  password: 'Password', passwordPlaceholder: 'Enter your password…',
  passwordHint: 'Use at least 10 characters.', confirmPassword: 'Confirm your password',
  continue: 'Continue', login: 'Log in', register: 'Sign up', back: 'Change username',
  alternatives: 'Other sign-in methods', divider: 'or continue with', soon: 'Coming soon',
  providersHint: 'These sign-in methods will be available soon.',
  newUser: 'New here?', existingUser: 'Already have an account?',
  loginNote: 'Your data stays on this computer.',
  registerNote: 'The first account will keep the projects already on this computer. Each new account will have its own notebook.',
  language: 'Language', creating: 'Creating account…', entering: 'Logging in…',
  invalidUsername: 'Use 3–40 letters, numbers, periods, hyphens or underscores for your username.',
  missingName: 'Enter your name.', shortPassword: 'Your password needs at least 10 characters.',
  passwordMismatch: 'Passwords do not match.', missingPassword: 'Enter your password.',
  wrongCredentials: 'Incorrect username or password.', duplicateUser: 'This username is already taken. Choose another.',
  sessionError: 'Unable to check your session.', reload: 'Reload the page.',
  requestError: 'Unable to complete sign-in. Please try again.',
};

export function authText(language: AuthLanguage, key: AuthTextKey): string {
  return (language === 'en' ? en : es)[key];
}

export function translateAuthError(message: string, language: AuthLanguage): string {
  const key = (Object.keys(es) as AuthTextKey[]).find(key => es[key] === message || en[key] === message);
  return key ? authText(language, key) : language === 'es' ? message : en.requestError;
}

export function loadAuthLanguage(): AuthLanguage {
  try { return localStorage.getItem('hilo-language') === 'en' ? 'en' : 'es'; }
  catch { return 'es'; }
}

export function saveAuthLanguage(language: AuthLanguage): void {
  try { localStorage.setItem('hilo-language', language); } catch { /* Sigue funcionando sin almacenamiento local. */ }
}
