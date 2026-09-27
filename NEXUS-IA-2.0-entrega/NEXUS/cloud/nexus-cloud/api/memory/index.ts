import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getAuthedUser } from "../../src/lib/auth";
import { supabaseForUser } from "../../src/lib/supabaseForUser";

// Mismas 7 categorías que memory/memory_manager.py ya usa en el Agent local
// — no se inventa un esquema nuevo, se traslada el mismo modelo (ver MEMORY.md).
const CATEGORIES = [
  "identity",
  "preferences",
  "projects",
  "relationships",
  "wishes",
  "notes",
  "procedural",
];

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const user = await getAuthedUser(req);
  if (!user) return res.status(401).json({ error: "no autenticado" });
  const db = supabaseForUser(user.accessToken);

  if (req.method === "GET") {
    const category = typeof req.query.category === "string" ? req.query.category : undefined;
    let query = db.from("memory_entries").select("*");
    if (category) query = query.eq("category", category);
    const { data, error } = await query;
    if (error) return res.status(500).json({ error: error.message });
    return res.status(200).json({ entries: data });
  }

  if (req.method === "POST") {
    const { category, key, value } = (req.body ?? {}) as {
      category?: string;
      key?: string;
      value?: string;
    };
    if (!category || !CATEGORIES.includes(category)) {
      return res.status(400).json({ error: `category debe ser una de: ${CATEGORIES.join(", ")}` });
    }
    if (!key || typeof value !== "string") {
      return res.status(400).json({ error: "key y value son obligatorios" });
    }

    const { data, error } = await db
      .from("memory_entries")
      .upsert(
        { category, key, value, updated_at: new Date().toISOString(), user_id: user.userId },
        { onConflict: "user_id,category,key" }
      )
      .select("*")
      .single();
    if (error) return res.status(500).json({ error: error.message });
    return res.status(200).json({ entry: data });
  }

  if (req.method === "DELETE") {
    const { category, key } = (req.body ?? {}) as { category?: string; key?: string };
    if (!category || !key) {
      return res.status(400).json({ error: "category y key son obligatorios" });
    }
    const { error } = await db.from("memory_entries").delete().eq("category", category).eq("key", key);
    if (error) return res.status(500).json({ error: error.message });
    return res.status(200).json({ ok: true });
  }

  res.setHeader("Allow", "GET, POST, DELETE");
  return res.status(405).json({ error: "método no permitido" });
}
