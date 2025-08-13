# carddata/__init__.py
from __future__ import annotations

# ---------- Elements ----------
# Base six + your custom trio
ELEMENTS = [
    "Fire", "Water", "Earth", "Wind", "Light", "Dark",
    "Tech", "Dragon", "Spirit",
]

# ---------- Element advantage map ----------
# A beats everything in its list
ADV = {
    # classic 6-cycle
    "Fire":  ["Wind"],
    "Wind":  ["Earth"],
    "Earth": ["Water"],
    "Water": ["Fire"],
    "Light": ["Dark"],
    "Dark":  ["Light"],
    # custom triangle
    "Tech":   ["Dragon"],
    "Dragon": ["Spirit"],
    "Spirit": ["Tech"],
}

# ---------- Stat ranges per rarity (inclusive) ----------
# Commons you asked for: 100–200 ATK/DEF
STAT_RANGES = {
    "common":    {"atk": (100, 200), "def": (100, 200)},
    "uncommon":  {"atk": (180, 280), "def": (180, 280)},
    "rare":      {"atk": (250, 350), "def": (250, 350)},
    "epic":      {"atk": (330, 450), "def": (330, 450)},
    "legendary": {"atk": (420, 600), "def": (420, 600)},
}

# Base pull weights (you can tweak in your cog if you prefer)
RARITY_WEIGHTS = {
    "common": 60.0,
    "uncommon": 25.0,
    "rare": 12.0,
    "epic": 2.5,
    "legendary": 0.5,  # pity logic still applies on top
}

# ---------- Card pools ----------
from .common import COMMON_CARDS
from .uncommon import UNCOMMON_CARDS
from .rare import RARE_CARDS
from .epic import EPIC_CARDS
from .legendary import LEGENDARY_CARDS

ALL_CARDS = {
    "common": COMMON_CARDS,
    "uncommon": UNCOMMON_CARDS,
    "rare": RARE_CARDS,
    "epic": EPIC_CARDS,
    "legendary": LEGENDARY_CARDS,
}

# Order matters: lowest -> highest
RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]

__all__ = [
    "ELEMENTS", "ADV",
    "STAT_RANGES", "RARITY_WEIGHTS",
    "ALL_CARDS", "RARITIES",
    "COMMON_CARDS", "UNCOMMON_CARDS", "RARE_CARDS", "EPIC_CARDS", "LEGENDARY_CARDS",
]