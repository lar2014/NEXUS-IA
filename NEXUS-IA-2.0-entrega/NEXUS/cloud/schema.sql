-- ═══════════════════════════════════════════════════════════════════════════
-- Nexus Cloud — esquema inicial (Supabase / Postgres)
-- PROMPT 3 §5, §6, §8, §9, §10
--
-- ESTADO: diseño, NO desplegado. No se ha creado ningún proyecto de Supabase
-- real para esto — ver NEXUS_CLOUD_ARCHITECTURE.md, sección "siguiente paso".
--
-- PRINCIPIO CENTRAL (spec §5): "nunca debe existir la posibilidad de que una
-- petición del usuario A termine ejecutándose en el dispositivo del usuario B".
-- Esto se garantiza aquí en DOS capas independientes, no solo en la aplicación:
--   1. Toda tabla de datos de usuario tiene user_id NOT NULL con FK a
--      auth.users(id) (el sistema de autenticación que Supabase ya trae).
--   2. Row Level Security (RLS) activado en todas ellas, con una policy que
--      exige auth.uid() = user_id — así, aunque un bug de la aplicación
--      construyera mal una query, la base de datos igualmente no devolvería
--      ni dejaría escribir filas de otro usuario.
-- ═══════════════════════════════════════════════════════════════════════════

-- ── Dispositivos vinculados (spec §6-7) ──────────────────────────────────────
create table if not exists public.devices (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null references auth.users(id) on delete cascade,
    name          text not null,
    type          text not null check (type in ('pc', 'android', 'ios', 'mac', 'linux', 'nexus_room')),
    capabilities  jsonb not null default '[]'::jsonb,   -- lista de ACTION_TYPES que este Agent soporta (ver nexus_core/actions_schema.py)
    permissions   jsonb not null default '{}'::jsonb,   -- {action_type: "PERMITIDO"|"REQUIERE_CONFIRMACION"|"BLOQUEADO"} — mismo vocabulario que DeviceManager
    connected     boolean not null default false,
    last_seen     timestamptz,
    linked_at     timestamptz not null default now(),
    pairing_code  text unique,        -- código "7F4-K92" mientras el emparejamiento está pendiente; NULL una vez vinculado
    pairing_expires_at timestamptz    -- el código deja de ser válido pasado este instante (mismo criterio que el PIN de 600s del dashboard actual)
);

alter table public.devices enable row level security;

create policy "devices: solo el propio usuario" on public.devices
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── Configuración de proveedores de IA (spec §8) ─────────────────────────────
-- La API key NUNCA se guarda en texto plano aquí. Recomendado: Supabase Vault
-- (extensión `supabase_vault`), que cifra el secreto y solo lo descifra bajo
-- una función security-definer del lado del servidor — nunca llega tal cual
-- a una query normal ni al cliente. `api_key_vault_id` guarda la REFERENCIA
-- al secreto en el vault, no el secreto.
create table if not exists public.provider_configs (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references auth.users(id) on delete cascade,
    provider         text not null check (provider in ('anthropic', 'openai', 'gemini', 'openrouter', 'custom')),
    label            text,                       -- nombre que le da el usuario, ej. "mi Gemini personal"
    api_key_vault_id uuid,                       -- referencia a supabase_vault.secrets, NUNCA el valor real
    is_default       boolean not null default false,
    created_at       timestamptz not null default now(),
    unique (user_id, provider, label)
);

alter table public.provider_configs enable row level security;

create policy "provider_configs: solo el propio usuario" on public.provider_configs
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── Memoria del usuario (spec §9 — separada de memoria del sistema/temporal) ─
-- Mismas 7 categorías que ya usa memory/memory_manager.py en el Agent local
-- (identity, preferences, projects, relationships, wishes, notes, procedural)
-- — no se inventa un esquema nuevo, se traslada el mismo modelo a multiusuario.
create table if not exists public.memory_entries (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null references auth.users(id) on delete cascade,
    category   text not null check (category in
                 ('identity', 'preferences', 'projects', 'relationships', 'wishes', 'notes', 'procedural')),
    key        text not null,
    value      text not null,
    updated_at timestamptz not null default now(),
    unique (user_id, category, key)
);

alter table public.memory_entries enable row level security;

create policy "memory_entries: solo el propio usuario" on public.memory_entries
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── Conversaciones (spec §9) — datos de sesión, no memoria permanente ────────
create table if not exists public.conversations (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null references auth.users(id) on delete cascade,
    device_id  uuid references public.devices(id) on delete set null,
    started_at timestamptz not null default now(),
    ended_at   timestamptz,
    summary    text
);

alter table public.conversations enable row level security;

create policy "conversations: solo el propio usuario" on public.conversations
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── Registro de acciones ejecutadas (auditoría — spec §3-4) ──────────────────
create table if not exists public.actions_log (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid not null references auth.users(id) on delete cascade,
    device_id    uuid not null references public.devices(id) on delete cascade,
    action_type  text not null,          -- uno de ACTION_TYPES (nexus_core/actions_schema.py)
    target       text,
    params       jsonb not null default '{}'::jsonb,
    status       text not null default 'pending'
                 check (status in ('pending', 'awaiting_confirmation', 'confirmed', 'executed', 'failed', 'blocked')),
    result       text,
    created_at   timestamptz not null default now(),
    executed_at  timestamptz
);

alter table public.actions_log enable row level security;

create policy "actions_log: solo el propio usuario" on public.actions_log
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- ── Índices para las consultas obvias ─────────────────────────────────────────
create index if not exists idx_devices_user            on public.devices(user_id);
create index if not exists idx_devices_pairing_code     on public.devices(pairing_code) where pairing_code is not null;
create index if not exists idx_memory_entries_user_cat  on public.memory_entries(user_id, category);
create index if not exists idx_actions_log_user_device  on public.actions_log(user_id, device_id, created_at desc);
