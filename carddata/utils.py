# carddata/utils.py
from __future__ import annotations
import re
from typing import Dict, Any

# Use the single source of truth from carddata/__init__.py
from . import ELEMENTS, ADV  # element list + advantage chart

# Optional: cute element emojis for formatting
ELEMENT_EMOJI = {
    "Fire":  "🔥",
    "Water": "💧",
    "Earth": "⛰️",
    "Wind":  "🌪️",
    "Light": "✨",
    "Dark":  "🌑",
    "Tech": "🤖",
    "Dragon": "🐉", 
    "Spirit": "🌀"
}

def slugify(text: str) -> str:
    """kinda-url-safe id from a name."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text

def element_multiplier(attacker: str, defender: str,
                       adv_mult: float = 1.20, disadv_mult: float = 0.80) -> float:
    """
    Returns the damage multiplier based on elemental advantage.
    > attacker beats defender -> adv_mult
    > defender beats attacker -> disadv_mult
    > otherwise -> 1.0
    """
    if defender in ADV.get(attacker, []):
        return adv_mult
    if attacker in ADV.get(defender, []):
        return disadv_mult
    return 1.0

def short_card(c: Dict[str, Any]) -> str:
    """Compact one-line string for a card dict."""
    e = c.get("element", "?")
    emj = ELEMENT_EMOJI.get(e, "")
    atk = c.get("atk", "?")
    de  = c.get("def", "?")
    name = c.get("name", "?")
    return f"{emj}{name} [{e}] ATK {atk} / DEF {de}"