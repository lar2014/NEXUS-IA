import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { requireEnv } from "./env";
import type { Database } from "./database.types";

/**
 * Cliente que actúa COMO el usuario autenticado: usa la clave pública
 * (anon/publishable) pero reenvía el JWT del usuario en cada petición, así
 * que Row Level Security aplica auth.uid() = el usuario real. Este es el
 * camino preferido para casi todo — nunca bypassea RLS. Para operaciones que
 * de verdad necesitan saltárselo (p. ej. api/devices/claim.ts, donde el
 * Agent aún no tiene sesión de usuario), está supabaseAdmin(), a usar con
 * mucha más cautela y siempre acotando manualmente qué fila se toca.
 */
export function supabaseForUser(accessToken: string): SupabaseClient<Database> {
  const url = requireEnv("SUPABASE_URL");
  const anonKey = requireEnv("SUPABASE_ANON_KEY");
  return createClient<Database>(url, anonKey, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { Authorization: `Bearer ${accessToken}` } },
  });
}
