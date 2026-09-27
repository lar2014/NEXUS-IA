/**
 * Espejo, en TypeScript, del vocabulario de nexus_core/actions_schema.py del
 * Agent (Windows) — mismo vocabulario exacto, para que Cloud y Agent hablen
 * el mismo idioma sin traducir nombres por el camino. Nexus Cloud VALIDA y
 * ENRUTA una Action; quien la EJECUTA de verdad es siempre el Agent, nunca
 * este backend.
 */
export const ACTION_TYPES = [
  "OPEN_APP",
  "OPEN_URL",
  "OPEN_FILE",
  "CREATE_FILE",
  "CREATE_FOLDER",
  "SEARCH_WEB",
  "SEND_MESSAGE",
  "READ_NOTIFICATION",
  "TAKE_SCREENSHOT",
  "CONTROL_MEDIA",
  "SET_VOLUME",
  "LOCK_DEVICE",
  "SHUTDOWN_DEVICE",
] as const;

export type ActionType = (typeof ACTION_TYPES)[number];

export interface Action {
  action: ActionType;
  device_id: string;
  target: string;
  params: Record<string, unknown>;
  action_id?: string;
}

export type ValidationResult =
  | { ok: true; action: Action }
  | { ok: false; error: string };

/** Nunca lanza — un body mal formado es un 400 normal, no una excepción. */
export function validateAction(body: unknown): ValidationResult {
  if (typeof body !== "object" || body === null) {
    return { ok: false, error: "el cuerpo debe ser un objeto JSON" };
  }
  const b = body as Record<string, unknown>;

  if (typeof b.action !== "string" || !(ACTION_TYPES as readonly string[]).includes(b.action)) {
    return { ok: false, error: `action_type desconocido: ${String(b.action)}` };
  }
  if (typeof b.device_id !== "string" || !b.device_id) {
    return { ok: false, error: "device_id es obligatorio" };
  }

  return {
    ok: true,
    action: {
      action: b.action as ActionType,
      device_id: b.device_id,
      target: typeof b.target === "string" ? b.target : "",
      params:
        typeof b.params === "object" && b.params !== null
          ? (b.params as Record<string, unknown>)
          : {},
      action_id: typeof b.action_id === "string" ? b.action_id : undefined,
    },
  };
}
