"""
nexus_core/actions_schema.py — Sistema de acciones estructuradas (evolución
Nexus Cloud/Agent, PROMPT 3 §3 y §6-7).

POR QUÉ EXISTE
    La especificación pide explícitamente que Nexus NO dependa de que la IA
    genere comandos arbitrarios, sino de una acción estructurada:

        {"action": "OPEN_APP", "target": "whatsapp", "device_id": "..."}

    Hoy, el "action" más parecido que existe es el nombre de un tool de
    ToolManager (ver TOOLS.md) — pero esos nombres son libres, específicos de
    cada action/plugin, y no anuncian de forma estandarizada qué sabe hacer un
    dispositivo. Este módulo NO sustituye a ToolManager ni a Security — es una
    capa de TRADUCCIÓN por encima de ambos, en un fichero nuevo, sin que nada
    existente lo importe todavía. Añadirlo no puede romper nada que ya
    funcione: es exactamente el mismo principio que ya se aplicó al dejar
    DeviceManager sin conectar (ver su propio docstring) — una interfaz lista,
    sin forzar todavía al único llamador que la usaría de verdad.

QUÉ HACE
    1. Define el vocabulario ACTION_TYPES pedido en la especificación §3.
    2. Mapea cada ACTION_TYPE, cuando es posible, al tool real que ya lo
       implementa hoy en este Agent (ver ACTION_TO_TOOL más abajo) — leído
       del código real de actions/*.py, no adivinado.
    3. `capabilities_for(tool_manager)` construye el JSON de capacidades que
       un Agent anunciaría a Nexus Cloud (spec §3):
           {"device": "...", "capabilities": ["OPEN_APP", "OPEN_URL", ...]}
    4. `to_tool_call(action)` traduce una Action entrante en (tool_name,
       parameters) — lo que YA sabe ejecutar `ToolManager.run(...)`, con
       Security aplicándose exactamente igual que a cualquier otro tool.

QUÉ NO HACE (todavía)
    No hay ningún transporte de red aquí (eso es Nexus Cloud, sección 10 de la
    especificación) ni ninguna llamada a `ToolManager.run()` — quien reciba una
    Action de la red decide cuándo y con qué contexto ejecutarla; este módulo
    solo la traduce a algo que ToolManager ya entiende.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Vocabulario de acciones (spec §3) ────────────────────────────────────────
# Los 8 primeros ya tienen un tool real que los cubre hoy (columna "tool" no
# vacía) — confirmado leyendo cada actions/*.py, no supuesto. Los 5 últimos no
# tienen tool equivalente en este Agent todavía: aparecen en ACTION_TYPES para
# que el vocabulario esté completo desde ya (spec §3: "no implementes
# automáticamente todas si el sistema no está preparado"), pero
# `capabilities_for()` no los anunciará como soportados hasta que exista un
# tool real detrás.
#
# action_type          -> (tool real que lo implementa hoy, o None)
#
# Cada mapeo está verificado contra el "parameters" real declarado en el TOOL
# dict del action correspondiente (actions/*.py) — no supuesto por el nombre.
ACTION_TO_TOOL: dict[str, Optional[str]] = {
    "OPEN_APP":           "open_app",
    "OPEN_URL":           "browser_control",
    "OPEN_FILE":          "file_controller",
    "CREATE_FILE":        "file_controller",
    "CREATE_FOLDER":      "file_controller",
    "SEARCH_WEB":         "web_search",
    "SEND_MESSAGE":       "send_message",
    "TAKE_SCREENSHOT":    "screen_process",     # tool inline, no de ToolManager — ver nota en to_tool_call()
    "CONTROL_MEDIA":      "computer_settings",  # pause_video / next_tab / etc. — cobertura parcial, no un control de medios genérico
    "SET_VOLUME":         "computer_settings",  # action=volume_set — confirmado en el schema real del tool
    "LOCK_DEVICE":        "computer_settings",  # action=lock_screen — SÍ existe (no estaba en mi primer borrador; corregido tras leer el schema real)
    "SHUTDOWN_DEVICE":    "computer_settings",  # action=shutdown
    # -- sin tool equivalente hoy en este Agent (confirmado, no supuesto) --
    "READ_NOTIFICATION":  None,
}

ACTION_TYPES = tuple(ACTION_TO_TOOL.keys())

# Tools inline (ver TOOLS.md) que ToolManager.run() NO despacha directamente —
# los ejecuta VoiceEngine. to_tool_call() debe poder decirle a su llamador
# cuál de las dos rutas usar.
_INLINE_ACTION_TOOLS = {"screen_process"}


@dataclass
class Action:
    """La forma estructurada pedida en la especificación §3, tal cual —
    ningún campo inventado encima de lo que pide el documento."""
    action: str                          # uno de ACTION_TYPES
    device_id: str
    target: str = ""
    params: dict = field(default_factory=dict)
    action_id: Optional[str] = None      # para que Nexus Cloud pueda casar la respuesta con la petición

    def validate(self) -> Optional[str]:
        """None si es válida; si no, el motivo (nunca lanza — quien reciba
        una Action de la red no debe poder tumbar el Agent con un campo mal
        formado)."""
        if self.action not in ACTION_TYPES:
            return f"unknown action type: {self.action!r}"
        if not self.device_id:
            return "device_id is required"
        return None


def capabilities_for(tool_manager, device_name: str = "", device_type: str = "") -> dict:
    """El JSON exacto de la spec §3: qué ACTION_TYPES puede ejecutar de verdad
    ESTE Agent ahora mismo, según lo que `tool_manager` tiene realmente
    registrado — no según lo que ACTION_TO_TOOL dice en teoría. Si un tool
    fue rechazado en el descubrimiento (ver core/action_loader.py) o un
    plugin está deshabilitado, esa capability no aparece."""
    caps = []
    for action_type, tool_name in ACTION_TO_TOOL.items():
        if tool_name and (tool_name in _INLINE_ACTION_TOOLS
                           or tool_manager.has(tool_name)):
            caps.append(action_type)
    return {
        "device": device_name or "unknown",
        "device_type": device_type or "unknown",
        "capabilities": sorted(caps),
    }


def to_tool_call(action: Action) -> tuple[str, dict, bool]:
    """Traduce una Action a lo que ToolManager (o VoiceEngine, para las
    inline) necesita: (tool_name, parameters, is_inline).

    Lanza ValueError si la acción no tiene tool detrás todavía — el llamador
    decide cómo comunicar eso a Nexus Cloud; este módulo no inventa un
    resultado de éxito falso."""
    err = action.validate()
    if err:
        raise ValueError(err)

    tool_name = ACTION_TO_TOOL.get(action.action)
    if not tool_name:
        raise ValueError(
            f"'{action.action}' is a known action type but no tool in this "
            f"Agent implements it yet — see ACTION_TO_TOOL in this module."
        )

    # El mapeo params -> argumentos del tool real es deliberadamente mínimo y
    # explícito por acción, no una copia genérica de `params`: cada tool
    # existente ya tiene su propio contrato de parámetros (verificado contra
    # el "parameters" real de cada actions/*.py, no adivinado), y copiar
    # `params` a ciegas sería el tipo de acoplamiento frágil que la propia
    # especificación pide evitar con un sistema estructurado.
    if action.action == "OPEN_APP":
        params = {"app_name": action.target}
    elif action.action == "OPEN_URL":
        params = {"action": "go_to", "url": action.target, **action.params}
    elif action.action == "OPEN_FILE":
        params = {"action": "read", "path": action.target, **action.params}
    elif action.action == "CREATE_FILE":
        params = {"action": "create_file", "path": action.target, **action.params}
    elif action.action == "CREATE_FOLDER":
        params = {"action": "create_folder", "path": action.target, **action.params}
    elif action.action == "SEARCH_WEB":
        params = {"query": action.target, **action.params}
    elif action.action == "SEND_MESSAGE":
        # 'target' se usa como destinatario; la plataforma (WhatsApp,
        # Telegram...) va en params — el tool la exige y no tiene un valor
        # por defecto razonable que este módulo pueda inventar.
        params = {"receiver": action.target, "message_text": action.params.get("message", ""),
                  **{k: v for k, v in action.params.items() if k != "message"}}
    elif action.action == "TAKE_SCREENSHOT":
        params = {"angle": "screen", **action.params}
    elif action.action == "SET_VOLUME":
        params = {"action": "volume_set", "value": action.target or action.params.get("value", ""), **action.params}
    elif action.action == "LOCK_DEVICE":
        params = {"action": "lock_screen"}
    elif action.action == "SHUTDOWN_DEVICE":
        params = {"action": "shutdown"}
    elif action.action == "CONTROL_MEDIA":
        params = {"action": action.target or action.params.get("action", "pause_video"), **action.params}
    else:
        params = dict(action.params)

    return tool_name, params, tool_name in _INLINE_ACTION_TOOLS
