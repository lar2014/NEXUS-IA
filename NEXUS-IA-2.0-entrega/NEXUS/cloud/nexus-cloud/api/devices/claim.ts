import type { VercelRequest, VercelResponse } from "@vercel/node";
import crypto from "node:crypto";
import { supabaseAdmin } from "../../src/lib/supabaseAdmin";

/**
 * Lo llama el AGENT, no el usuario — en este punto el Agent todavía no tiene
 * ninguna sesión de usuario, solo el código de vinculación que el usuario le
 * mostró (generado por pairing.ts). Por eso usa supabaseAdmin() en vez de
 * supabaseForUser(): es la única ruta de todo este backend donde bypassear
 * RLS está justificado, y aun así solo puede tocar la fila cuyo
 * pairing_code coincide exactamente y no ha expirado.
 */
export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "método no permitido" });
  }

  const { pairing_code, capabilities } = (req.body ?? {}) as {
    pairing_code?: string;
    capabilities?: string[];
  };
  if (!pairing_code) {
    return res.status(400).json({ error: "pairing_code es obligatorio" });
  }

  const admin = supabaseAdmin();
  const { data: device, error: findError } = await admin
    .from("devices")
    .select("id, pairing_expires_at")
    .eq("pairing_code", pairing_code)
    .maybeSingle();

  if (findError) return res.status(500).json({ error: findError.message });
  if (!device) return res.status(404).json({ error: "código de vinculación inválido" });
  if (!device.pairing_expires_at || new Date(device.pairing_expires_at) < new Date()) {
    return res.status(410).json({ error: "código de vinculación caducado" });
  }

  const deviceSecret = crypto.randomBytes(32).toString("base64url");
  const secretHash = crypto.createHash("sha256").update(deviceSecret).digest("hex");

  const { error: updateError } = await admin
    .from("devices")
    .update({
      connected: true,
      last_seen: new Date().toISOString(),
      capabilities: capabilities ?? [],
      pairing_code: null,
      pairing_expires_at: null,
      device_secret_hash: secretHash,
    })
    .eq("id", device.id);

  if (updateError) return res.status(500).json({ error: updateError.message });

  // El secreto en claro se devuelve UNA sola vez, aquí. El Agent debe
  // guardarlo localmente (p. ej. junto a config/api_keys.json) — Nexus Cloud
  // a partir de ahora solo conserva su hash, nunca el valor.
  return res.status(200).json({ device_id: device.id, device_secret: deviceSecret });
}
