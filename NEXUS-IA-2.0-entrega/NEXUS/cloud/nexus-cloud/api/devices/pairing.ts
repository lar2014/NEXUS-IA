import type { VercelRequest, VercelResponse } from "@vercel/node";
import crypto from "node:crypto";
import { getAuthedUser } from "../../src/lib/auth";
import { supabaseForUser } from "../../src/lib/supabaseForUser";

// Sin 0/O/1/I/L — mismo alfabeto sin ambigüedades que ya usa
// dashboard/server.py::_KEY_CHARS en el Agent local.
const CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";

function generatePairingCode(): string {
  const bytes = crypto.randomBytes(6);
  let out = "";
  for (let i = 0; i < 6; i++) out += CODE_CHARS[bytes[i] % CODE_CHARS.length];
  return `${out.slice(0, 3)}-${out.slice(3)}`;
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "método no permitido" });
  }

  const user = await getAuthedUser(req);
  if (!user) return res.status(401).json({ error: "no autenticado" });

  const { name, type } = (req.body ?? {}) as { name?: string; type?: string };
  if (!name || !type) {
    return res.status(400).json({ error: "name y type son obligatorios" });
  }

  const db = supabaseForUser(user.accessToken);
  const code = generatePairingCode();
  // 10 minutos — mismo orden de magnitud que el PIN de 600s del dashboard
  // actual del Agent local (dashboard/server.py).
  const expiresAt = new Date(Date.now() + 10 * 60 * 1000).toISOString();

  const { data, error } = await db
    .from("devices")
    .insert({
      user_id: user.userId,
      name,
      type,
      pairing_code: code,
      pairing_expires_at: expiresAt,
      connected: false,
    })
    .select("id, pairing_code, pairing_expires_at")
    .single();

  if (error) return res.status(500).json({ error: error.message });

  return res.status(201).json({
    device_id: data.id,
    pairing_code: data.pairing_code,
    expires_at: data.pairing_expires_at,
  });
}
