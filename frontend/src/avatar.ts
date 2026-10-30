// Avatar de una cuenta: su foto si la subió, o sus iniciales sobre el color de siempre.

export const initialsOf = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2)
  .map(word => word[0]).join('').toLocaleUpperCase('es');

/** `version` es la que manda la API (0 = sin foto); va en la URL para no ver una foto vieja. */
export function paintAvatar(node: HTMLElement, name: string, userId?: string | null, version = 0) {
  const initials = initialsOf(name) || '?';
  if (!userId || !version) {
    node.classList.remove('has-photo'); node.textContent = initials; return;
  }
  const src = `/api/users/${encodeURIComponent(userId)}/avatar?v=${version}`;
  if (node.querySelector('img')?.getAttribute('src') === src) return;
  const image = document.createElement('img');
  image.alt = ''; image.decoding = 'async'; image.src = src;
  // Si la foto ya no está (la quitaron en otra sesión), vuelven las iniciales.
  image.addEventListener('error', () => { node.classList.remove('has-photo'); node.textContent = initials; }, { once: true });
  node.classList.add('has-photo'); node.replaceChildren(image);
}

const PHOTO_SIZE = 320;

/** Recorta al centro, reduce a 320 px y comprime. Así la foto pesa decenas de KB y no
 *  viaja la original del celular (con su ubicación y demás datos EXIF). */
export async function preparePhoto(file: File): Promise<Blob> {
  if (!file.type.startsWith('image/')) throw new Error('Elige una imagen (JPG, PNG o WebP).');
  let bitmap: ImageBitmap;
  try { bitmap = await createImageBitmap(file); } catch {
    throw new Error('No se pudo abrir esa imagen. Prueba con una foto JPG o PNG.');
  }
  const side = Math.min(bitmap.width, bitmap.height);
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = PHOTO_SIZE;
  const context = canvas.getContext('2d')!;
  context.imageSmoothingQuality = 'high';
  context.drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, PHOTO_SIZE, PHOTO_SIZE);
  bitmap.close();
  const encode = (type: string) => new Promise<Blob | null>(resolve => canvas.toBlob(resolve, type, 0.86));
  // Un navegador que no sabe escribir WebP devuelve PNG; en ese caso se prefiere JPG, que pesa menos.
  const webp = await encode('image/webp');
  const blob = webp?.type === 'image/webp' ? webp : await encode('image/jpeg');
  if (!blob) throw new Error('No se pudo preparar la foto. Prueba con otra.');
  return blob;
}
