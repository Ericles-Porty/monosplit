"""Environment variables that hold API keys.

On Windows, a variable saved with "setx" or in the system settings reaches only processes
started afterwards. When it is missing from this process, the user's registry entry
(HKEY_CURRENT_USER\\Environment) is read too, so a server started from an older terminal
still finds a key created later. Values are never logged or returned by the API.
"""

from __future__ import annotations

import os
import sys


def env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                stored, _kind = winreg.QueryValueEx(key, name)
        except OSError:
            return None
        return str(stored) or None
    return None


def has_env(name: str) -> bool:
    return bool(env_value(name))
