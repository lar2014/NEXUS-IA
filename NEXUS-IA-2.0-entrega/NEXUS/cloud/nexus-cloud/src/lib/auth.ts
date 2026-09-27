import type { VercelRequest } from "@vercel/node";
import { supabaseAdmin } from "./supabaseAdmin";

export interface AuthedUser {
  userId: string;
  accessToken: string;
}

/**
 * Extrae y valida el usuario autenticado de la cabecera Authorization
 * ("Bearer <access_token>", el JWT que Supabase Auth ya emite al iniciar
 * sesión). Devuelve null si no hay token o no es válido — el propio
 * endpoint decide qué responder (normalmente 401); este helper nunca lanza
 * por un token ausente o inválido, solo por fallos genuinamente inesperados
 * de la llamada a Supabase.
 */
export async function getAuthedUser(req: VercelRequest): Promise<AuthedUser | null> {
  const header = req.headers.authorization;
  if (!header?.startsWith("Bearer ")) return null;
  const accessToken = header.slice("Bearer ".length).trim();
  if (!accessToken) return null;

  const { data, error } = await supabaseAdmin().auth.getUser(accessToken);
  if (error || !data?.user) return null;

  return { userId: data.user.id, accessToken };
}
