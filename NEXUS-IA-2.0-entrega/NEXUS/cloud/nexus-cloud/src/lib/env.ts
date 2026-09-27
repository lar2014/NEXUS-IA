/**
 * Acceso perezoso a variables de entorno. Ninguna se lee al cargar el
 * módulo — cada función solo falla si REALMENTE necesita esa variable y no
 * está puesta, para que desplegar sin todos los secretos configurados no
 * rompa el build ni los endpoints que no la necesitan.
 */
export function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Falta la variable de entorno ${name}. Configúrala en Vercel → ` +
      `Project Settings → Environment Variables.`
    );
  }
  return value;
}
