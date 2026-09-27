import type { VercelRequest, VercelResponse } from "@vercel/node";
import { supabaseAdmin } from "../src/lib/supabaseAdmin";

/**
 * Comprobación de conectividad REAL, no un 200 fijo: hace una consulta de
 * verdad a Postgres a través del cliente admin. Si Supabase no responde, o
 * faltan las variables de entorno, este endpoint lo refleja en vez de
 * devolver un "ok" vacío que no demuestra nada. Es el endpoint pensado para
 * "cómo probar que Supabase y Nexus Cloud están conectados correctamente".
 */
export default async function handler(_req: VercelRequest, res: VercelResponse) {
  const startedAt = Date.now();
  try {
    const { error } = await supabaseAdmin()
      .from("devices")
      .select("id", { count: "exact", head: true });

    if (error) {
      // El error de Postgrest es un objeto plano (no una instancia de Error),
      // así que se leen sus campos directamente en vez de relanzarlo y
      // convertirlo a texto — eso era el bug: "throw error" + String(err)
      // producía literalmente "[object Object]" y ocultaba el mensaje real.
      return res.status(503).json({
        status: "error",
        supabase: "unreachable",
        detail: error.message,
        details: error.details || undefined,
        hint: error.hint || undefined,
        code: error.code,
        timestamp: new Date().toISOString(),
      });
    }

    return res.status(200).json({
      status: "ok",
      supabase: "connected",
      latency_ms: Date.now() - startedAt,
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    // Aquí solo llegan fallos genuinamente inesperados (red caída, variable
    // de entorno ausente vía requireEnv, etc.) — esos sí suelen ser
    // instancias reales de Error.
    return res.status(503).json({
      status: "error",
      supabase: "unreachable",
      detail: err instanceof Error ? err.message : JSON.stringify(err),
      timestamp: new Date().toISOString(),
    });
  }
}
