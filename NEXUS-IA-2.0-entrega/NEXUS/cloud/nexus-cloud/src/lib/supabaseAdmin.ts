import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { requireEnv } from "./env";
import type { Database } from "./database.types";

let _admin: SupabaseClient<Database> | null = null;

/**
 * Cliente con la service_role key — se salta RLS por completo. SOLO para uso
 * del propio backend (nunca se expone al frontend, nunca se manda en una
 * respuesta HTTP). Perezoso: si SUPABASE_SERVICE_ROLE_KEY no está
 * configurada, el error solo ocurre cuando de verdad se necesita este
 * cliente, no al arrancar el proceso — así un despliegue sin todos los
 * secretos todavía no rompe endpoints que no lo necesitan (p. ej. los que
 * usan supabaseForUser()).
 */
export function supabaseAdmin(): SupabaseClient<Database> {
  if (_admin) return _admin;
  const url = requireEnv("SUPABASE_URL");
  const key = requireEnv("SUPABASE_SERVICE_ROLE_KEY");
  _admin = createClient<Database>(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return _admin;
}
