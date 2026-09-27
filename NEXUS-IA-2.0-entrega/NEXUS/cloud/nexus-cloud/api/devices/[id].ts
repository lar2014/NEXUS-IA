import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getAuthedUser } from "../../src/lib/auth";
import { supabaseForUser } from "../../src/lib/supabaseForUser";

const PERMISSION_LEVELS = ["PERMITIDO", "REQUIERE_CONFIRMACION", "BLOQUEADO"];

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const user = await getAuthedUser(req);
  if (!user) return res.status(401).json({ error: "no autenticado" });

  const { id } = req.query;
  if (typeof id !== "string") return res.status(400).json({ error: "id de dispositivo inválido" });

  const db = supabaseForUser(user.accessToken);

  if (req.method === "PATCH") {
    const { permissions } = (req.body ?? {}) as { permissions?: Record<string, string> };
    if (!permissions || typeof permissions !== "object") {
      return res.status(400).json({ error: "permissions es obligatorio" });
    }
    for (const [actionType, level] of Object.entries(permissions)) {
      if (!PERMISSION_LEVELS.includes(level)) {
        return res.status(400).json({
          error: `nivel de permiso inválido para ${actionType}: ${level} (debe ser ${PERMISSION_LEVELS.join(" | ")})`,
        });
      }
    }

    // RLS impide que esto toque un dispositivo que no sea del usuario — un
    // update sin filas afectadas (id ajeno) no es un error, simplemente no
    // cambia nada, por eso se comprueba data tras el update.
    const { data, error } = await db
      .from("devices")
      .update({ permissions })
      .eq("id", id)
      .select("id")
      .maybeSingle();

    if (error) return res.status(500).json({ error: error.message });
    if (!data) return res.status(404).json({ error: "dispositivo no encontrado o no es tuyo" });
    return res.status(200).json({ ok: true });
  }

  if (req.method === "DELETE") {
    const { data, error } = await db.from("devices").delete().eq("id", id).select("id").maybeSingle();
    if (error) return res.status(500).json({ error: error.message });
    if (!data) return res.status(404).json({ error: "dispositivo no encontrado o no es tuyo" });
    return res.status(200).json({ ok: true });
  }

  res.setHeader("Allow", "PATCH, DELETE");
  return res.status(405).json({ error: "método no permitido" });
}
