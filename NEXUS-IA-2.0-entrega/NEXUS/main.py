"""
main.py — NEXUS IA 2.0 entry point.

This used to be a 2283-line file holding the entire assistant: audio I/O,
tool discovery, tool dispatch, memory access, the avatar's viseme math, the
reconnect state machine — all of it. It is now what NEXUS asked for it to
become: a small bootstrap that builds the UI, builds NexusCore (which wires
together Brain / Memory / Planner / AgentManager / ToolManager / Perception
/ Voice / Security / EventBus / DeviceManager — see nexus_core/__init__.py),
and runs it.

Everything this file used to do line-by-line now lives in nexus_core/,
mostly in nexus_core/voice.py (which is main.py's old JarvisLive class,
moved and rewired, not rewritten — see that file's docstring for the exact
list of what changed). This file keeps only what genuinely belongs at a
process's entry point:

  * the Windows Popen patch and the UTF-8 console reconfiguration, which
    MUST run before any other module in the process does its first
    subprocess call or console print — see the comments below, carried
    over unchanged from the old main.py;
  * building the Qt UI and NexusCore, and starting the asyncio loop on a
    background thread the same way the old main() did.
"""
import platform as _platform
import subprocess as _subprocess

# ── Nuclear: force CREATE_NO_WINDOW on EVERY subprocess call on Windows ───────
# This patches Popen itself, so no per-file flag is needed anywhere.
if _platform.system() == "Windows":
    _OrigPopen = _subprocess.Popen

    class _Popen(_OrigPopen):
        def __init__(self, args, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | _subprocess.CREATE_NO_WINDOW
            kw.pop("startupinfo", None)   # drop any stale/shared STARTUPINFO
            super().__init__(args, **                       kw)

    _subprocess.Popen = _Popen


# ── Console must survive non-UTF-8 code pages ────────────────────────────────
# Every status line carries an emoji, and on a legacy Windows console the
# active code page is the system one — cp1254 in Turkey, cp1251 in Russia,
# cp932 in Japan. Printing an emoji there raises UnicodeEncodeError, and
# because most of these prints sit inside the receive loop it takes the
# session down on startup. Reconfiguring to UTF-8 with a replacement
# fallback costs nothing and makes the app launch the same way in every
# locale. This has to happen here, before nexus_core.voice (which prints
# emoji-carrying status lines from the moment it's imported) is loaded.
import sys

for _stream in ("stdout", "stderr"):
    try:
        _s = getattr(sys, _stream, None)
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass          # pythonw / redirected pipes / anything exotic — never fatal

# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import threading

from ui import JarvisUI
from nexus_core.core import NexusCore


def main():
    ui = JarvisUI("face.png")

    def runner():
        ui.wait_for_api_key()
        nexus = NexusCore(ui)
        try:
            asyncio.run(nexus.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
