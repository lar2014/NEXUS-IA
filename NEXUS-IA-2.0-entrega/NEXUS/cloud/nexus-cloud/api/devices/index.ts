import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getAuthedUser } from "../../src/lib/auth";
import { supabaseForUser } from "../../src/lib/supabaseForUser";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const user = await getAuthedUser(req);
  if (!user) return res.status(401).json({ error: "no autenticado" });

  if (req.method === "GET") {
    // supabaseForUser reenvía el JWT: RLS ya garantiza que esto solo puede
    // devolver dispositivos de ESTE usuario, sin necesidad de un .eq('user_id', ...) manual.
    const db = supabaseForUser(user.accessToken);
    const { data, error } = await db
      .from("devices")
      .select("id, name, type, capabilities, permissions, connected, last_seen, linked_at")
      .order("linked_at", { ascending: false });

    if (error) return res.status(500).json({ error: error.message });
    return res.status(200).json({ devices: data });
  }

  res.setHeader("Allow", "GET");
  return res.status(405).json({ error: "método no permitido" });
}
