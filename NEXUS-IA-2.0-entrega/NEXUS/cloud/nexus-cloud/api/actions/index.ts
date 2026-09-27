import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getAuthedUser } from "../../src/lib/auth";
import { supabaseForUser } from "../../src/lib/supabaseForUser";
import { validateAction } from "../../src/lib/actionsSchema";
import type { Json } from "../../src/lib/database.types";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const user = await getAuthedUser(req);
  if (!user) return res.status(401).json({ error: "no autenticado" });
  const db = supabaseForUser(user.accessToken);

  if (req.method === "GET") {
    const { data, error } = await db
      .from("actions_log")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(50);
    if (error) return res.status(500).json({ error: error.message });
    return res.status(200).json({ actions: data });
  }

  if (req.method === "POST") {
    const validated = validateAction(req.body);
    if (!validated.ok) return res.status(400).json({ error: validated.error });
    const { action } = validated;

    // RLS ya impide leer un dispositivo ajeno, así que un "no encontrado"
    // aquí cubre tanto "no existe" como "no es tuyo" sin distinguirlos —
    // adrede, para no filtrar si un device_id ajeno existe o no.
    const { data: device, error: deviceError } = await db
      .from("devices")
      .select("id, permissions")
      .eq("id", action.device_id)
      .maybeSingle();
    if (deviceError) return res.status(500).json({ error: deviceError.message });
    if (!device) return res.status(404).json({ error: "dispositivo no encontrado o no es tuyo" });

    const permissions = (device.permissions ?? {}) as Record<string, string>;
    const explicit = permissions[action.action];
    const status =
      explicit === "BLOQUEADO"
        ? "blocked"
        : explicit === "REQUIERE_CONFIRMACION"
          ? "awaiting_confirmation"
          // 'pending': sin permiso explícito de ESTE dispositivo, el Agent
          // aplicará su propia política de Security (nexus_core/security.py)
          // al recibirla — ver NEXUS_CLOUD_ARCHITECTURE.md.
          : "pending";

    const { data: logged, error: insertError } = await db
      .from("actions_log")
      .insert({
        user_id: user.userId,
        device_id: action.device_id,
        action_type: action.action,
        target: action.target,
        // action.params ya fue validado como un objeto JSON-serializable por
        // validateAction() — el cast a Json es seguro, no una forma de
        // silenciar un error real.
        params: action.params as Json,
        status,
      })
      .select("*")
      .single();

    if (insertError) return res.status(500).json({ error: insertError.message });

    // IMPORTANTE (ver NEXUS_CLOUD_ARCHITECTURE.md): esto registra la acción y
    // aplica el permiso por dispositivo, pero todavía NO la entrega en
    // tiempo real al Agent — no existe aún el transporte (WebSocket/cola)
    // entre Nexus Cloud y un Agent en otra red. `delivered: false` lo dice
    // sin ambigüedad en vez de fingir un 200 de éxito completo.
    return res.status(202).json({ action_log: logged, delivered: false });
  }

  res.setHeader("Allow", "GET, POST");
  return res.status(405).json({ error: "método no permitido" });
}
