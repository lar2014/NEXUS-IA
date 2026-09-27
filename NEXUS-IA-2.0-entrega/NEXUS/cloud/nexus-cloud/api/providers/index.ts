import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getAuthedUser } from "../../src/lib/auth";
import { supabaseForUser } from "../../src/lib/supabaseForUser";

const PROVIDERS = ["anthropic", "openai", "gemini", "openrouter", "custom"];

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const user = await getAuthedUser(req);
  if (!user) return res.status(401).json({ error: "no autenticado" });
  const db = supabaseForUser(user.accessToken);

  if (req.method === "GET") {
    // Nunca se selecciona api_key_vault_id: ni siquiera la referencia al
    // secreto hace falta en el frontend, y así queda imposible devolverla
    // por error en el futuro si alguien añade un campo a la consulta.
    const { data, error } = await db
      .from("provider_configs")
      .select("id, provider, label, is_default, created_at");
    if (error) return res.status(500).json({ error: error.message });
    return res.status(200).json({ providers: data });
  }

  if (req.method === "POST") {
    const { provider, label, api_key } = (req.body ?? {}) as {
      provider?: string;
      label?: string;
      api_key?: string;
    };
    if (!provider || !PROVIDERS.includes(provider)) {
      return res.status(400).json({ error: `provider debe ser uno de: ${PROVIDERS.join(", ")}` });
    }
    if (!api_key) return res.status(400).json({ error: "api_key es obligatoria" });

    // create_provider_secret (función de Postgres, security definer) cifra
    // api_key en Supabase Vault y devuelve solo el id de la fila en
    // provider_configs — la key en sí nunca vuelve a aparecer en ninguna
    // respuesta HTTP desde este punto en adelante. Ver SECURITY.md / cloud/schema.sql.
    const { data, error } = await db.rpc("create_provider_secret", {
      p_provider: provider,
      p_label: label ?? "",
      p_api_key: api_key,
    });
    if (error) return res.status(500).json({ error: error.message });
    return res.status(201).json({ provider_config_id: data });
  }

  res.setHeader("Allow", "GET, POST");
  return res.status(405).json({ error: "método no permitido" });
}
