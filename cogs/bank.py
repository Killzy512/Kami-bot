# cogs/bank.py
from __future__ import annotations
import json, os
from typing import Dict

# JSON layout per guild:
# {
#   "<guild_id>": {
#     "balances": { "<user_id>": int, ... },
#     "daily":    { "<user_id>": int_unix, ... },
#     "pity":     { "<user_id>": int, ... }   # for gacha pity counters
#   }, ...
# }

_BANK_PATH = "bank.json"
_DATA: Dict[str, Dict[str, Dict[str, int]]] = {}  # gid -> {balances, daily, pity}

def set_path(path: str) -> None:
    """Change JSON path (call once at startup)."""
    global _BANK_PATH
    _BANK_PATH = path

def bank_load() -> None:
    """Load from disk (safe if file is missing)."""
    global _DATA
    if os.path.exists(_BANK_PATH):
        with open(_BANK_PATH, "r", encoding="utf-8") as f:
            _DATA = json.load(f)
    else:
        _DATA = {}

def bank_save() -> None:
    """Atomic save to disk."""
    tmp = _BANK_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_DATA, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _BANK_PATH)

def _guild(gid: int) -> Dict[str, Dict[str, int]]:
    g = _DATA.setdefault(str(gid), {})
    g.setdefault("balances", {})
    g.setdefault("daily", {})
    g.setdefault("pity", {})
    return g

# ------------ balances ------------
def get_balance(gid: int, uid: int) -> int:
    g = _guild(gid)
    return int(g["balances"].get(str(uid), 0))

def add_balance(gid: int, uid: int, delta: int) -> int:
    g = _guild(gid)
    key = str(uid)
    new = int(g["balances"].get(key, 0)) + int(delta)
    g["balances"][key] = new
    return new

# ------------ daily timestamps ------------
def get_last_daily(gid: int, uid: int) -> int | None:
    g = _guild(gid)
    v = g["daily"].get(str(uid))
    return int(v) if v is not None else None

def set_last_daily(gid: int, uid: int, ts: int) -> None:
    g = _guild(gid)
    g["daily"][str(uid)] = int(ts)

# ------------ pity counters (for gacha) ------------
def get_pity(gid: int, uid: int) -> int:
    """Return current pity counter (defaults to 0)."""
    g = _guild(gid)
    return int(g["pity"].get(str(uid), 0))

def set_pity(gid: int, uid: int, value: int) -> int:
    """Set pity to an exact value; returns the stored value."""
    g = _guild(gid)
    g["pity"][str(uid)] = int(value)
    return int(value)

def add_pity(gid: int, uid: int, delta: int = 1) -> int:
    """Increment pity by delta; returns new pity."""
    g = _guild(gid)
    key = str(uid)
    new = int(g["pity"].get(key, 0)) + int(delta)
    g["pity"][key] = new
    return new

def reset_pity(gid: int, uid: int) -> None:
    """Reset pity to 0."""
    g = _guild(gid)
    g["pity"][str(uid)] = 0
