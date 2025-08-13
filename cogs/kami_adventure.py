# cogs/kami_adventure.py
# Kami Adventure v2 — RPG + Bank/Global XP + Inventory/Shop + Guilds + Co-op Raids
# + Roles/Officers, Raid Keys & Weekly Lockouts, Leaderboards (Wins/Fastest + Seasonal),
#   Daily Rewards, Crafting, Trading Post, Boss Mechanics, Guild Perks, Invites, Weekly Affixes
#   BADGES (tiered), Interactive Raid Queue Panel (Buttons + Ready check),
#   Auto Monster Spawns (configurable channel/rate) & Races.
#
# Hybrid commands (prefix & slash). Per-server persistence at data_dir/<guild_id>.json

from __future__ import annotations

import json
import os
import random
import math
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord.ext import commands, tasks

# =========================
# Config / constants
# =========================
KAMICOIN_NAME = "Kami Coins"
EMO_KAMICOIN = "🪙"
EMO_HP = "❤️"
EMO_ATK = "⚔️"
EMO_DEF = "🛡️"
EMO_CRIT = "💥"
EMO_LOOT = "🎁"
EMO_EXPLORE = "🧭"
EMO_SPARK = "✨"
EMO_POTION = "🧪"
EMO_GUILD = "🏯"
EMO_RAID = "🐉"
EMO_SHARD = "🔹"
EMO_CORE = "🔷"
EMO_TRADE = "🏪"
DEFAULT_COLOR = 0x00B3FF

RARITY_COLORS = {
    "Common": 0x95A5A6,
    "Uncommon": 0x2ECC71,
    "Rare": 0x3498DB,
    "Epic": 0x9B59B6,
    "Legendary": 0xF1C40F,
}

# ====== Races ======
RACES: Dict[str, Dict[str, Any]] = {
    "Human":  {"desc": "Balanced wanderers of the isekai.", "perks": {"atk": 0, "def": 0, "max_hp": 0, "crit": 0}},
    "Kitsune":{"desc": "Cunning fox spirits. +1 ATK, +3% Crit.", "perks": {"atk": 1, "def": 0, "max_hp": 0, "crit": 3}},
    "Oni":    {"desc": "Fierce brutes. +10 Max HP.", "perks": {"atk": 0, "def": 0, "max_hp": 10, "crit": 0}},
    "Tengu":  {"desc": "Sky duelists. +1 DEF, +1 ATK.", "perks": {"atk": 1, "def": 1, "max_hp": 0, "crit": 0}},
    "Yokai":  {"desc": "Mysterious. +2% Crit, +1 DEF.", "perks": {"atk": 0, "def": 1, "max_hp": 0, "crit": 2}},
}

# ====== Items (expanded) ======
# (name, stat, rarity, price) for weapons/armor
BASE_WEAPONS = [
    ("Bamboo Practice Sword", 2, "Common", 25),
    ("Kami-Tempered Tanto", 4, "Uncommon", 120),
    ("Isekai Katana of Fresh Starts", 7, "Rare", 350),
    ("Stormcaller Naginata", 11, "Epic", 900),
    ("Mythic Sunsplitter", 16, "Legendary", 2000),

    ("Sapphire Wakizashi", 5, "Uncommon", 150),
    ("Echo-Tuned Nodachi", 8, "Rare", 420),
    ("Moonlit Uchigatana", 9, "Rare", 480),
    ("Thunder Fanblade", 12, "Epic", 960),
    ("Blazing Oni Club", 13, "Epic", 1100),
    ("Skyweaver Glaive", 14, "Epic", 1250),
    ("Kitsune Trickblade", 6, "Uncommon", 210),
    ("Pilgrim's Spear", 3, "Common", 55),
    ("Shrinekeeper's Staff", 4, "Uncommon", 130),
    ("Raiju Clawknife", 10, "Rare", 520),
    ("Azure Tempest Saber", 15, "Epic", 1500),
    ("Solaris Edge", 18, "Legendary", 2600),
    ("Aetherglass Blade", 19, "Legendary", 2900),
    ("Dragonvein Harpoon", 17, "Legendary", 2400),
    ("Windsong Tonfa", 7, "Rare", 390),
    ("Dawnbreaker Katana", 20, "Legendary", 3200),
    ("Verdant Kodachi", 8, "Rare", 410),
    ("Oni Splitter Kanabo", 16, "Epic", 1700),
    ("Gale Spiral Spear", 12, "Epic", 1050),
    ("Karmic Edge", 9, "Rare", 450),
    ("Lotus Petal Dagger", 6, "Uncommon", 190),
    ("Mirage Katana", 13, "Epic", 1150),
    ("Starforge Blade", 22, "Legendary", 3800),
    ("Void Petal Scythe", 21, "Legendary", 3400),
    ("Jade River Saber", 10, "Rare", 530),
]

BASE_ARMOR = [
    ("Traveler Cloak", 1, "Common", 20),
    ("Ronin Vest", 3, "Uncommon", 110),
    ("Dragonweave Haori", 5, "Rare", 320),
    ("Heavenward Yoroi", 8, "Epic", 850),
    ("Kami Aegis", 12, "Legendary", 1900),

    ("Moonweft Robe", 4, "Uncommon", 160),
    ("Stormguard Lamellar", 6, "Rare", 380),
    ("Riverstone Do-maru", 5, "Rare", 330),
    ("Aetherlinked Jacket", 7, "Rare", 520),
    ("Foxfire Garb", 6, "Rare", 410),
    ("Raiju Carapace", 9, "Epic", 980),
    ("Sky Tyrant Coat", 10, "Epic", 1150),
    ("Oni Bulwark Plate", 11, "Epic", 1400),
    ("Verdant Scale Hauberk", 7, "Rare", 500),
    ("Mirage Vestments", 8, "Epic", 900),
    ("Sunsteel Harness", 13, "Legendary", 2100),
    ("Voidweave Mantle", 14, "Legendary", 2400),
    ("Tengu Skycloak", 9, "Epic", 1020),
    ("Jade Ward Jacket", 6, "Rare", 440),
    ("Lotus Guard Jerkin", 5, "Rare", 360),
    ("Clockwork Oni Harness", 12, "Epic", 1600),
    ("Astral Guardian Plate", 15, "Legendary", 2800),
    ("Seastone Coat", 4, "Uncommon", 150),
    ("Driftwood Brigandine", 3, "Uncommon", 120),
    ("Karmic Layered Robe", 8, "Epic", 930),
    ("Windshell Vest", 7, "Rare", 520),
    ("Celestial Warplate", 16, "Legendary", 3200),
]

# (name, (effect, amount), price)
CONSUMABLES = [
    ("Small Potion", ("heal", 25), 40),
    ("Medium Potion", ("heal", 60), 140),
    ("Elixir", ("heal", 120), 360),
]

HEAL_COIN_RATE = 0.5  # coins per HP

# ----- Guilds (player clans) -----
CLAN_CREATE_COST = 750
CLAN_XP_BASE = 150  # xp needed per guild level ~ level * CLAN_XP_BASE

# ----- Raids -----
RAID_MIN = 2
RAID_MAX = 6
RAID_JOIN_DEFAULT = 90  # seconds join window (UX hint only)

# boss pools by difficulty: (name, hp, atk, def, crit, coin_range, rpg_xp_base, clan_xp)
BOSS_POOLS: Dict[str, List[Tuple[str, int, int, int, int, Tuple[int, int], int, int]]] = {
    "easy": [
        ("Nest Matriarch Slime", 250, 18, 6, 8, (80, 140), 80, 30),
    ],
    "normal": [
        ("Wastes Basilisk", 420, 26, 10, 10, (150, 240), 140, 55),
        ("Clockwork Oni", 480, 28, 12, 12, (170, 260), 160, 60),
    ],
    "hard": [
        ("Storm King Raiju", 700, 36, 16, 14, (260, 400), 240, 90),
    ],
    "legendary": [
        ("Aether Dragon of Lost Shrines", 1200, 48, 22, 16, (420, 650), 380, 140),
    ],
}
RAID_SCALE_PER_LEVEL = 0.06  # +6% boss stats per avg party level above 1

# Raid keys (host needs one to start Normal/Hard/Legendary)
RAID_KEYS_REQUIRED = {"easy": 0, "normal": 1, "hard": 1, "legendary": 1}

# ----- Raid Queue (matchmaking) -----
QUEUE_TARGET = 4            # preferred party size; bot will still run with >= RAID_MIN
QUEUE_READY_TIMEOUT = 45    # seconds for players to confirm "ready"
QUEUE_REJOIN_COOLDOWN = 60  # seconds ban if a player fails ready-check
LEVEL_SPREAD_MAX = 6        # optional balance target; not strictly enforced

# =========================
# Seasonal/weekly helpers
# =========================
def current_week_id() -> str:
    import datetime as _dt
    iso = _dt.date.today().isocalendar()
    # Support both tuple and namedtuple styles (3.7 vs 3.8+)
    try:
        year, week = iso.year, iso.week
    except AttributeError:
        year, week, _ = iso
    return f"{year}-W{week:02d}"

def current_season_id() -> str:
    import datetime as _dt
    d = _dt.datetime.utcnow()
    q = (d.month - 1)//3 + 1
    return f"{d.year}Q{q}"

def today_str() -> str:
    import datetime as _dt
    return _dt.date.today().isoformat()

# Weekly raid affixes (C feature): deterministic by week id
AFFIXES = [
    ("Fortified", "Boss DEF +15%"),
    ("Tyrannical", "Boss HP/ATK +10%"),
    ("Volcanic", "Small extra AoE each round"),
    ("Icy Veins", "Crit chance +4%"),
    ("Wind Skin", "Boss takes -8% damage"),
]
def weekly_affix() -> Tuple[str, str]:
    wid = current_week_id()
    rnd = random.Random(wid)
    return rnd.choice(AFFIXES)

# Guild perks by level (A feature)
def guild_perks(level: int) -> Dict[str, float]:
    return {
        "shop_discount": 0.05 if level >= 2 else 0.0,   # 5% off at Lv2+
        "raid_hp_buff": 0.10 if level >= 3 else 0.0,    # +10% temp HP in raids at Lv3+
        "extra_loot": 0.15 if level >= 5 else 0.0,      # 15% chance extra Shards at Lv5+
    }

# =========================
# Achievements (BADGES)
# =========================
BADGES = {
    "first_blood": {"emoji":"🥇","title":"First Blood","desc":"Defeat your first monster."},
    "slayer_i":    {"emoji":"🗡️","title":"Monster Slayer I","desc":"Defeat 10 monsters."},
    "slayer_ii":   {"emoji":"🗡️","title":"Monster Slayer II","desc":"Defeat 50 monsters."},
    "slayer_iii":  {"emoji":"🗡️","title":"Monster Slayer III","desc":"Defeat 200 monsters."},
    "raider_i":    {"emoji":"🐲","title":"Raider I","desc":"Win 1 raid."},
    "raider_ii":   {"emoji":"🐲","title":"Raider II","desc":"Win 10 raids."},
    "raider_iii":  {"emoji":"🐲","title":"Raider III","desc":"Win 50 raids."},
    "crafter_i":   {"emoji":"🔧","title":"Crafter I","desc":"Craft 1 item."},
    "crafter_ii":  {"emoji":"🔧","title":"Crafter II","desc":"Craft 5 items."},
    "crafter_iii": {"emoji":"🔧","title":"Crafter III","desc":"Craft 20 items."},
    "trader_i":    {"emoji":"💱","title":"Trader I","desc":"Complete 1 trade."},
    "trader_ii":   {"emoji":"💱","title":"Trader II","desc":"Complete 5 trades."},
    "trader_iii":  {"emoji":"💱","title":"Trader III","desc":"Complete 20 trades."},
    "wealth_i":    {"emoji":"💰","title":"Wealth I","desc":"Earn 1,000 coins."},
    "wealth_ii":   {"emoji":"💰","title":"Wealth II","desc":"Earn 10,000 coins."},
    "wealth_iii":  {"emoji":"💰","title":"Wealth III","desc":"Earn 100,000 coins."},
    "kami_chosen": {"emoji":"🌬️","title":"Kami’s Chosen","desc":"Choose your race."},
}
STAT_DEFAULTS = {"kills":0, "raid_wins":0, "coins_earned":0, "crafts":0, "trades":0}

# =========================
# Small utils
# =========================
def now_ts() -> int:
    import time as _t
    return int(_t.time())

def roll_pct(p: float) -> bool:
    return random.random() < (p / 100.0)

def color_for_rarity(rarity: str) -> int:
    return RARITY_COLORS.get(rarity, DEFAULT_COLOR)

def kami_embed(title: str, desc: str = "", color: int = DEFAULT_COLOR) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="Forged in isekai, blessed by Kami.")
    return e

# =========================
# Per-guild persistence manager
# =========================
class DataManager:
    """Stores each Discord server in its own JSON: <base_dir>/<guild_id>.json"""
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _path(self, gid: int) -> str:
        return os.path.join(self.base_dir, f"{gid}.json")

    # ---------- safe atomic write ----------
    def _atomic_write(self, path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)

    # ---------- schema normalizers ----------
    def _normalize_player(self, p: Dict[str, Any]) -> bool:
        """Ensure a player dict has all required keys. Returns True if mutated."""
        changed = False
        def setdef(k, v):
            nonlocal changed
            if k not in p:
                p[k] = v
                changed = True

        setdef("name", "Traveler")
        setdef("rpg_xp", 0)
        setdef("rpg_level", 1)
        setdef("max_hp", 50)
        # clamp hp to max
        cur_max = int(p.get("max_hp", 50))
        setdef("hp", min(int(p.get("hp", 50)), cur_max))
        setdef("atk", 5)
        setdef("def", 2)
        setdef("crit", 5)
        setdef("weapon", None)
        setdef("armor", None)
        setdef("inventory", [])
        setdef("last_explore", 0)
        setdef("clan", None)
        setdef("race", "Human")
        return changed

    def _normalize_guild_blob(self, g: Dict[str, Any]) -> bool:
        """Ensure required top-level keys exist. Returns True if mutated."""
        changed = False
        def setdef(d, k, v):
            nonlocal changed
            if k not in d:
                d[k] = v
                changed = True
            return d[k]

        setdef(g, "players", {})
        setdef(g, "fallback_balances", {})
        setdef(g, "shop_seed", random.randint(1, 10_000))
        setdef(g, "clans", {})
        setdef(g, "market", {"next_id": 1, "listings": {}})

        # leaderboards
        setdef(g, "leaderboard", {"users": {}})
        cur_season = current_season_id()
        lb_season = g.get("leaderboard_season")
        if not isinstance(lb_season, dict) or "season" not in lb_season or "users" not in lb_season:
            g["leaderboard_season"] = {"season": cur_season, "users": {}}
            changed = True

        # keys/lockouts/daily
        setdef(g, "raid_keys", {})
        setdef(g, "weekly_lockouts", {})
        setdef(g, "daily", {})

        # stats/badges
        setdef(g, "stats", {})
        setdef(g, "badges", {})

        # spawns
        sp = setdef(g, "spawns", {})
        setdef(sp, "enabled", False)
        setdef(sp, "channel_id", None)
        setdef(sp, "min_sec", 900)
        setdef(sp, "max_sec", 1800)
        setdef(sp, "next_ts", 0)
        setdef(sp, "active", None)

        # normalize every player present
        for p in list(g["players"].values()):
            if isinstance(p, dict) and self._normalize_player(p):
                changed = True

        return changed

    # ---------- ensure/save (with auto-migrate) ----------
    def _ensure(self, gid: int) -> Dict[str, Any]:
        key = str(gid)
        if key not in self._cache:
            path = self._path(gid)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self._cache[key] = json.load(f)
            else:
                # brand-new file with current schema
                self._cache[key] = {
                    "players": {},
                    "fallback_balances": {},
                    "shop_seed": random.randint(1, 10_000),
                    "clans": {},
                    "market": {"next_id": 1, "listings": {}},
                    "leaderboard": {"users": {}},
                    "leaderboard_season": {"season": current_season_id(), "users": {}},
                    "raid_keys": {},
                    "weekly_lockouts": {},
                    "daily": {},
                    "stats": {},
                    "badges": {},
                    "spawns": {
                        "enabled": False,
                        "channel_id": None,
                        "min_sec": 900,
                        "max_sec": 1800,
                        "next_ts": 0,
                        "active": None,
                    },
                }
            # auto-migrate older blobs up to date
            if self._normalize_guild_blob(self._cache[key]):
                self.save(gid)
        return self._cache[key]

    def save(self, gid: int) -> None:
        path = self._path(gid)
        payload = self._ensure(gid)
        self._atomic_write(path, payload)

    # ---- player helpers ----
    def _migrate_player_schema(self, p: Dict[str, Any]) -> None:
        """Ensure old saves have all required keys."""
        self._normalize_player(p)

    def get_player(self, gid: int, uid: int, name_if_create: str | None = None) -> Dict[str, Any]:
        g = self._ensure(gid)
        key = str(uid)
        p = g["players"].get(key)
        if p is None and name_if_create:
            base = {"hp": 50, "max_hp": 50, "atk": 5, "def": 2, "crit": 5}
            race = "Human"
            perks = RACES[race]["perks"]
            max_hp = base["max_hp"] + int(perks.get("max_hp", 0))
            p = {
                "name": name_if_create,
                "rpg_xp": 0,
                "rpg_level": 1,
                "hp": max_hp, "max_hp": max_hp,
                "atk": base["atk"] + int(perks.get("atk", 0)),
                "def": base["def"] + int(perks.get("def", 0)),
                "crit": base["crit"] + int(perks.get("crit", 0)),
                "weapon": None, "armor": None,
                "inventory": [],
                "last_explore": 0,
                "clan": None,
                "race": race,
            }
            g["players"][key] = p
            self.save(gid)
        elif p is not None:
            self._migrate_player_schema(p)
        return p

    # ---- stats & badges ----
    def _stats_bucket(self, gid: int) -> Dict[str, Any]:
        return self._ensure(gid)

    def stats_get(self, gid: int, uid: int) -> Dict[str, int]:
        g = self._ensure(gid)
        stats = g.setdefault("stats", {})
        s = stats.setdefault(str(uid), {})
        for k, v in STAT_DEFAULTS.items():
            s.setdefault(k, v)
        return s

    def stats_add(self, gid: int, uid: int, **delta):
        s = self.stats_get(gid, uid)
        for k, v in delta.items():
            s[k] = int(s.get(k, 0)) + int(v)
        self.save(gid)

    def badges_get(self, gid: int, uid: int) -> Dict[str, int]:
        g = self._ensure(gid)
        return g.setdefault("badges", {}).setdefault(str(uid), {})

    def badge_unlock(self, gid: int, uid: int, badge_id: str) -> bool:
        bag = self.badges_get(gid, uid)
        if badge_id in bag:
            return False
        bag[badge_id] = now_ts()
        self.save(gid)
        return True

    def badges_eval(self, gid: int, uid: int) -> List[str]:
        s = self.stats_get(gid, uid)
        p = self.get_player(gid, uid)  # used for race check
        newly = []
        checks = [
            ("first_blood",  s["kills"] >= 1),
            ("slayer_i",     s["kills"] >= 10),
            ("slayer_ii",    s["kills"] >= 50),
            ("slayer_iii",   s["kills"] >= 200),
            ("raider_i",     s["raid_wins"] >= 1),
            ("raider_ii",    s["raid_wins"] >= 10),
            ("raider_iii",   s["raid_wins"] >= 50),
            ("crafter_i",    s["crafts"] >= 1),
            ("crafter_ii",   s["crafts"] >= 5),
            ("crafter_iii",  s["crafts"] >= 20),
            ("trader_i",     s["trades"] >= 1),
            ("trader_ii",    s["trades"] >= 5),
            ("trader_iii",   s["trades"] >= 20),
            ("wealth_i",     s["coins_earned"] >= 1_000),
            ("wealth_ii",    s["coins_earned"] >= 10_000),
            ("wealth_iii",   s["coins_earned"] >= 100_000),
            ("kami_chosen",  (p or {}).get("race", "Human") != "Human"),
        ]
        for bid, ok in checks:
            if ok and self.badge_unlock(gid, uid, bid):
                newly.append(bid)
        return newly

    # ---- clan helpers ----
    def clans(self, gid: int) -> Dict[str, Any]:
        return self._ensure(gid)["clans"]

    def clan_of(self, gid: int, uid: int) -> Optional[str]:
        p = self.get_player(gid, uid)
        return p.get("clan") if p else None

    def set_clan(self, gid: int, uid: int, name: Optional[str]):
        p = self.get_player(gid, uid)
        if p:
            p["clan"] = name
            self.save(gid)

    def clan_create(self, gid: int, owner_id: int, name: str) -> bool:
        c = self.clans(gid)
        if name in c:
            return False
        c[name] = {
            "owner_id": int(owner_id),
            "officers": [],
            "members": [int(owner_id)],
            "xp": 0,
            "level": 1,
            "created": now_ts(),
            "invites": {},  # uid -> ts
        }
        self.set_clan(gid, owner_id, name)
        self.save(gid)
        return True

    def clan_is_officer_or_owner(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        return bool(c and (uid == c["owner_id"] or uid in c["officers"]))

    def clan_add_member(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        if not c:
            return False
        if uid in c["members"]:
            return True
        c["members"].append(int(uid))
        self.set_clan(gid, uid, name)
        c["invites"].pop(str(uid), None)
        self.save(gid)
        return True

    def clan_remove_member(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        if not c:
            return False
        if uid in c["members"]:
            c["members"].remove(uid)
        p = self.get_player(gid, uid)
        if p:
            p["clan"] = None
        if not c["members"]:
            del self.clans(gid)[name]
        self.save(gid)
        return True

    def clan_promote(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        if not c or uid not in c["members"]:
            return False
        if uid == c["owner_id"]:
            return True
        if uid not in c["officers"]:
            c["officers"].append(uid)
            self.save(gid)
        return True

    def clan_demote(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        if not c:
            return False
        if uid in c["officers"]:
            c["officers"].remove(uid)
            self.save(gid)
        return True

    def clan_transfer(self, gid: int, name: str, new_owner_id: int) -> bool:
        c = self.clans(gid).get(name)
        if not c or new_owner_id not in c["members"]:
            return False
        c["owner_id"] = int(new_owner_id)
        if new_owner_id in c["officers"]:
            c["officers"].remove(new_owner_id)
        self.save(gid)
        return True

    def clan_invite(self, gid: int, name: str, uid: int):
        c = self.clans(gid).get(name)
        if not c:
            return False
        c["invites"][str(uid)] = now_ts()
        self.save(gid)
        return True

    def clan_uninvite(self, gid: int, name: str, uid: int):
        c = self.clans(gid).get(name)
        if not c:
            return False
        c["invites"].pop(str(uid), None)
        self.save(gid)
        return True

    def clan_award_xp(self, gid: int, name: str, amount: int) -> Tuple[int, int]:
        c = self.clans(gid).get(name)
        if not c:
            return (0, 0)
        c["xp"] += int(amount)
        ups = 0
        while c["xp"] >= c["level"] * CLAN_XP_BASE:
            c["xp"] -= c["level"] * CLAN_XP_BASE
            c["level"] += 1
            ups += 1
        self.save(gid)
        return (c["level"], ups)

    # ---- Bank fallback ----
    def fb_get(self, gid: int, uid: int) -> int:
        g = self._ensure(gid)
        return int(g["fallback_balances"].get(str(uid), 0))

    def fb_add(self, gid: int, uid: int, delta: int) -> int:
        g = self._ensure(gid)
        key = str(uid)
        g["fallback_balances"][key] = int(g["fallback_balances"].get(key, 0)) + int(delta)
        self.save(gid)
        return g["fallback_balances"][key]

    # ---- raid keys, lockouts, leaderboards ----
    def add_raid_key(self, gid: int, uid: int, difficulty: str, qty: int = 1):
        g = self._ensure(gid)
        keys = g["raid_keys"].setdefault(str(uid), {})
        keys[difficulty] = int(keys.get(difficulty, 0)) + int(qty)
        self.save(gid)

    def get_raid_keys(self, gid: int, uid: int) -> Dict[str, int]:
        return self._ensure(gid)["raid_keys"].get(str(uid), {})

    def spend_raid_key(self, gid: int, uid: int, difficulty: str) -> bool:
        keys = self.get_raid_keys(gid, uid)
        have = int(keys.get(difficulty, 0))
        if have <= 0:
            return False
        keys[difficulty] = have - 1
        self._ensure(gid)["raid_keys"][str(uid)] = keys
        self.save(gid)
        return True

    def set_lockout(self, gid: int, uid: int, difficulty: str, week_id: str):
        g = self._ensure(gid)
        lock = g["weekly_lockouts"].setdefault(str(uid), {})
        lock[difficulty] = week_id
        self.save(gid)

    def has_lockout(self, gid: int, uid: int, difficulty: str, week_id: str) -> bool:
        g = self._ensure(gid)
        return g["weekly_lockouts"].get(str(uid), {}).get(difficulty) == week_id

    def _ensure_season(self, gid: int):
        g = self._ensure(gid)
        cur = current_season_id()
        if g["leaderboard_season"].get("season") != cur:
            g["leaderboard_season"] = {"season": cur, "users": {}}
            self.save(gid)

    def lb_user_all(self, gid: int, uid: int) -> Dict[str, Any]:
        g = self._ensure(gid)
        return g["leaderboard"]["users"].setdefault(str(uid), {"raid_wins": 0, "fastest": None})

    def lb_user_season(self, gid: int, uid: int) -> Dict[str, Any]:
        self._ensure_season(gid)
        g = self._ensure(gid)
        return g["leaderboard_season"]["users"].setdefault(str(uid), {"raid_wins": 0, "fastest": None})

    def lb_record_win(self, gid: int, uid: int, rounds: int):
        secs = rounds * 6  # rough time model
        for bucket in (self.lb_user_all(gid, uid), self.lb_user_season(gid, uid)):
            bucket["raid_wins"] = int(bucket.get("raid_wins", 0)) + 1
            fastest = bucket.get("fastest")
            if fastest is None or secs < fastest:
                bucket["fastest"] = secs
        self.save(gid)

    def daily_can_claim(self, gid: int, uid: int) -> bool:
        g = self._ensure(gid)
        last = g["daily"].get(str(uid), {}).get("last_claim")
        return last != today_str()

    def daily_set_claimed(self, gid: int, uid: int):
        g = self._ensure(gid)
        g["daily"][str(uid)] = {"last_claim": today_str()}
        self.save(gid)

    # ---- market ----
    def market_new_listing(self, gid: int, item: Dict[str, Any], seller_id: int, price: int) -> int:
        g = self._ensure(gid)
        lid = g["market"]["next_id"]
        g["market"]["next_id"] += 1
        g["market"]["listings"][str(lid)] = {
            "id": lid,
            "item": item,
            "seller_id": int(seller_id),
            "price": int(price),
            "created": now_ts(),
        }
        self.save(gid)
        return lid

    def market_listings(self, gid: int) -> Dict[str, Any]:
        return self._ensure(gid)["market"]["listings"]

    def market_pop(self, gid: int, lid: int) -> Optional[Dict[str, Any]]:
        g = self._ensure(gid)
        listing = g["market"]["listings"].pop(str(lid), None)
        self.save(gid)
        return listing

    # ---- clan helpers ----
    def clans(self, gid: int) -> Dict[str, Any]:
        return self._ensure(gid)["clans"]

    def clan_of(self, gid: int, uid: int) -> Optional[str]:
        p = self.get_player(gid, uid)
        return p.get("clan") if p else None

    def set_clan(self, gid: int, uid: int, name: Optional[str]):
        p = self.get_player(gid, uid)
        p["clan"] = name
        self.save(gid)

    def clan_create(self, gid: int, owner_id: int, name: str) -> bool:
        c = self.clans(gid)
        if name in c:
            return False
        c[name] = {
            "owner_id": int(owner_id),
            "officers": [],
            "members": [int(owner_id)],
            "xp": 0,
            "level": 1,
            "created": now_ts(),
            "invites": {},  # uid -> ts
        }
        self.set_clan(gid, owner_id, name)
        self.save(gid)
        return True

    def clan_is_officer_or_owner(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        return bool(c and (uid == c["owner_id"] or uid in c["officers"]))

    def clan_add_member(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        if not c: return False
        if uid in c["members"]: return True
        c["members"].append(int(uid))
        self.set_clan(gid, uid, name)
        c["invites"].pop(str(uid), None)
        self.save(gid)
        return True

    def clan_remove_member(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        if not c: return False
        if uid in c["members"]:
            c["members"].remove(uid)
        p = self.get_player(gid, uid)
        if p: p["clan"] = None
        if not c["members"]:
            del self.clans(gid)[name]
        self.save(gid)
        return True

    def clan_promote(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        if not c: return False
        if uid not in c["members"]: return False
        if uid == c["owner_id"]: return True
        if uid not in c["officers"]:
            c["officers"].append(uid)
            self.save(gid)
        return True

    def clan_demote(self, gid: int, name: str, uid: int) -> bool:
        c = self.clans(gid).get(name)
        if not c: return False
        if uid in c["officers"]:
            c["officers"].remove(uid)
            self.save(gid)
        return True

    def clan_transfer(self, gid: int, name: str, new_owner_id: int) -> bool:
        c = self.clans(gid).get(name)
        if not c: return False
        if new_owner_id not in c["members"]:
            return False
        c["owner_id"] = int(new_owner_id)
        if new_owner_id in c["officers"]:
            c["officers"].remove(new_owner_id)
        self.save(gid)
        return True

    def clan_invite(self, gid: int, name: str, uid: int):
        c = self.clans(gid).get(name)
        if not c: return False
        c["invites"][str(uid)] = now_ts()
        self.save(gid)
        return True

    def clan_uninvite(self, gid: int, name: str, uid: int):
        c = self.clans(gid).get(name)
        if not c: return False
        c["invites"].pop(str(uid), None)
        self.save(gid)
        return True

    def clan_award_xp(self, gid: int, name: str, amount: int) -> Tuple[int, int]:
        c = self.clans(gid).get(name)
        if not c: return (0, 0)
        c["xp"] += int(amount)
        ups = 0
        while c["xp"] >= c["level"] * CLAN_XP_BASE:
            c["xp"] -= c["level"] * CLAN_XP_BASE
            c["level"] += 1
            ups += 1
        self.save(gid)
        return (c["level"], ups)

    # ---- Bank fallback ----
    def fb_get(self, gid: int, uid: int) -> int:
        g = self._ensure(gid)
        return int(g["fallback_balances"].get(str(uid), 0))

    def fb_add(self, gid: int, uid: int, delta: int) -> int:
        g = self._ensure(gid)
        key = str(uid)
        g["fallback_balances"][key] = int(g["fallback_balances"].get(key, 0)) + int(delta)
        self.save(gid)
        return g["fallback_balances"][key]

    # ---- raid keys, lockouts, leaderboards ----
    def add_raid_key(self, gid: int, uid: int, difficulty: str, qty: int = 1):
        g = self._ensure(gid)
        keys = g["raid_keys"].setdefault(str(uid), {})
        keys[difficulty] = int(keys.get(difficulty, 0)) + int(qty)
        self.save(gid)

    def get_raid_keys(self, gid: int, uid: int) -> Dict[str, int]:
        return self._ensure(gid)["raid_keys"].get(str(uid), {})

    def spend_raid_key(self, gid: int, uid: int, difficulty: str) -> bool:
        keys = self.get_raid_keys(gid, uid)
        have = int(keys.get(difficulty, 0))
        if have <= 0: return False
        keys[difficulty] = have - 1
        self._ensure(gid)["raid_keys"][str(uid)] = keys
        self.save(gid)
        return True

    def set_lockout(self, gid: int, uid: int, difficulty: str, week_id: str):
        g = self._ensure(gid)
        lock = g["weekly_lockouts"].setdefault(str(uid), {})
        lock[difficulty] = week_id
        self.save(gid)

    def has_lockout(self, gid: int, uid: int, difficulty: str, week_id: str) -> bool:
        g = self._ensure(gid)
        return g["weekly_lockouts"].get(str(uid), {}).get(difficulty) == week_id

    def _ensure_season(self, gid: int):
        g = self._ensure(gid)
        cur = current_season_id()
        if g["leaderboard_season"].get("season") != cur:
            g["leaderboard_season"] = {"season": cur, "users": {}}
            self.save(gid)

    def lb_user_all(self, gid: int, uid: int) -> Dict[str, Any]:
        g = self._ensure(gid)
        return g["leaderboard"]["users"].setdefault(str(uid), {"raid_wins": 0, "fastest": None})

    def lb_user_season(self, gid: int, uid: int) -> Dict[str, Any]:
        self._ensure_season(gid)
        g = self._ensure(gid)
        return g["leaderboard_season"]["users"].setdefault(str(uid), {"raid_wins": 0, "fastest": None})

    def lb_record_win(self, gid: int, uid: int, rounds: int):
        secs = rounds * 6  # rough time model
        for bucket in (self.lb_user_all(gid, uid), self.lb_user_season(gid, uid)):
            bucket["raid_wins"] = int(bucket.get("raid_wins", 0)) + 1
            fastest = bucket.get("fastest")
            if fastest is None or secs < fastest:
                bucket["fastest"] = secs
        self.save(gid)

    def daily_can_claim(self, gid: int, uid: int) -> bool:
        g = self._ensure(gid)
        last = g["daily"].get(str(uid), {}).get("last_claim")
        return last != today_str()

    def daily_set_claimed(self, gid: int, uid: int):
        g = self._ensure(gid)
        g["daily"][str(uid)] = {"last_claim": today_str()}
        self.save(gid)

    # ---- market ----
    def market_new_listing(self, gid: int, item: Dict[str, Any], seller_id: int, price: int) -> int:
        g = self._ensure(gid)
        lid = g["market"]["next_id"]
        g["market"]["next_id"] += 1
        g["market"]["listings"][str(lid)] = {
            "id": lid,
            "item": item,
            "seller_id": int(seller_id),
            "price": int(price),
            "created": now_ts(),
        }
        self.save(gid)
        return lid

    def market_listings(self, gid: int) -> Dict[str, Any]:
        return self._ensure(gid)["market"]["listings"]

    def market_pop(self, gid: int, lid: int) -> Optional[Dict[str, Any]]:
        g = self._ensure(gid)
        listing = g["market"]["listings"].pop(str(lid), None)
        self.save(gid)
        return listing
# =========================
# Bank adapter (uses your bank cog; falls back to DataManager)
# =========================
class BankAdapter:
    def __init__(self, bot: commands.Bot, dm: DataManager):
        self.bot = bot
        self.dm = dm
        try:
            import importlib
            self._ok = False
            for name in ("cogs.bank", "bank"):
                try:
                    mod = importlib.import_module(name)
                    self._get = getattr(mod, "get_balance", None)
                    self._add = getattr(mod, "add_balance", None)
                    if callable(self._get) and callable(self._add):
                        self._ok = True
                        break
                except Exception:
                    continue
        except Exception:
            self._ok = False

    def get_balance(self, gid: int, uid: int) -> int:
        if getattr(self, "_ok", False):
            try:
                return int(self._get(gid, uid))  # type: ignore
            except Exception:
                pass
        cog = self.bot.get_cog("Bank")
        if cog:
            for fn in ("get_balance", "balance_of", "get", "fetch_balance"):
                func = getattr(cog, fn, None)
                if callable(func):
                    try:
                        return int(func(gid, uid))
                    except Exception:
                        continue
        return self.dm.fb_get(gid, uid)

    def add_balance(self, gid: int, uid: int, delta: int) -> int:
        if getattr(self, "_ok", False):
            try:
                return int(self._add(gid, uid, int(delta)))  # type: ignore
            except Exception:
                pass
        cog = self.bot.get_cog("Bank")
        if cog:
            for fn in ("add_balance", "give", "add", "deposit"):
                func = getattr(cog, fn, None)
                if callable(func):
                    try:
                        return int(func(gid, uid, int(delta)))
                    except Exception:
                        continue
        return self.dm.fb_add(gid, uid, delta)

# =========================
# Global Bot XP adapter (uses your XP cog or module)
# =========================
def try_award_global_xp(bot: commands.Bot, member: discord.Member, amount: int) -> None:
    try:
        cog = bot.get_cog("XP") or bot.get_cog("GlobalXP") or bot.get_cog("Levels")
        for attr in ("add_xp", "award_xp", "give_xp", "grant_xp"):
            fn = getattr(cog, attr, None)
            if callable(fn):
                try:
                    fn(member.guild.id, member.id, int(amount))  # type: ignore
                    return
                except Exception:
                    pass
                try:
                    fn(member, int(amount))  # type: ignore
                    return
                except Exception:
                    pass
        try:
            import importlib
            for name in ("cogs.xp", "xp"):
                try:
                    xpmod = importlib.import_module(name)
                    add_fn = getattr(xpmod, "add_xp", None)
                    if callable(add_fn):
                        add_fn(member.guild.id, member.id, int(amount))
                        return
                except Exception:
                    continue
        except Exception:
            pass
    except Exception:
        pass

# =========================
# Cog
# =========================
class KamiAdventure(commands.Cog, name="Kami Adventure"):
    """Kami/Isekai-themed mini-RPG (coins + RPG XP + Guilds + Raids + extras)."""

    # ========== UI Views ==========

    class QueuePanelView(discord.ui.View):
        def __init__(self, cog: "KamiAdventure", ctx: commands.Context, difficulty: str):
            super().__init__(timeout=600)
            self.cog = cog
            self.ctx = ctx
            self.difficulty = difficulty

        async def on_timeout(self):
            st = self.cog.queue_panels.get(self.ctx.guild.id)
            if st and st.get("msg_id"):
                try:
                    await self.ctx.channel.send("⏳ Raid queue panel expired.")
                except Exception:
                    pass
                self.cog.queue_panels.pop(self.ctx.guild.id, None)

        @discord.ui.button(label="Join", style=discord.ButtonStyle.success, emoji="➕")
        async def join(self, itx: discord.Interaction, btn: discord.ui.Button):
            await itx.response.defer(ephemeral=True)
            st = self.cog.queue_panels.get(self.ctx.guild.id)
            if not st or st["difficulty"] != self.difficulty:
                return
            st["members"].add(itx.user.id)
            await self._refresh_panel()
            await itx.followup.send("Joined the queue!", ephemeral=True)

        @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary, emoji="➖")
        async def leave(self, itx: discord.Interaction, btn: discord.ui.Button):
            await itx.response.defer(ephemeral=True)
            st = self.cog.queue_panels.get(self.ctx.guild.id)
            if not st: return
            st["members"].discard(itx.user.id)
            await self._refresh_panel()
            await itx.followup.send("Left the queue.", ephemeral=True)

        @discord.ui.button(label="Start", style=discord.ButtonStyle.danger, emoji="🚀")
        async def start(self, itx: discord.Interaction, btn: discord.ui.Button):
            await itx.response.defer(ephemeral=True)
            st = self.cog.queue_panels.get(self.ctx.guild.id)
            if not st: return
            if itx.user.id != st["host"]:
                return await itx.followup.send("Only the queue host can start.", ephemeral=True)
            mems = list(st["members"])
            if len(mems) < RAID_MIN:
                return await itx.followup.send(f"Need at least {RAID_MIN} players.", ephemeral=True)
            # switch to ready-check
            view = KamiAdventure.ReadyCheckView(self.cog, self.ctx, self.difficulty, mems)
            try:
                msg = await self.ctx.channel.fetch_message(st["msg_id"])
                await msg.edit(content="**Ready-check!** Click Ready within 45s.", view=view, embed=None)
            except Exception:
                pass

        async def _refresh_panel(self):
            st = self.cog.queue_panels.get(self.ctx.guild.id)
            if not st: return
            names = []
            for uid in list(st["members"]):
                m = self.ctx.guild.get_member(uid)
                names.append(m.display_name if m else f"ID {uid}")
            desc = (
                f"Host: <@{st['host']}> • Difficulty: **{self.difficulty.title()}**\n"
                f"Members ({len(st['members'])}/{RAID_MAX}): " + (", ".join(names) or "none")
            )
            try:
                msg = await self.ctx.channel.fetch_message(st["msg_id"])
                await msg.edit(embed=kami_embed(title=f"{EMO_RAID} Raid Queue Panel", desc=desc))
            except Exception:
                pass

    class ReadyCheckView(discord.ui.View):
        def __init__(self, cog: "KamiAdventure", ctx: commands.Context, difficulty: str, party: List[int]):
            super().__init__(timeout=QUEUE_READY_TIMEOUT)
            self.cog = cog; self.ctx = ctx; self.diff = difficulty
            self.party = set(party); self.ready: set[int] = set()

        async def on_timeout(self):
            await self._finish()

        @discord.ui.button(label="Ready", style=discord.ButtonStyle.success, emoji="✅")
        async def ready(self, itx: discord.Interaction, btn: discord.ui.Button):
            if itx.user.id not in self.party:
                return await itx.response.send_message("You're not in this party.", ephemeral=True)
            self.ready.add(itx.user.id)
            await itx.response.send_message("Ready!", ephemeral=True)
            if self.ready == self.party:
                await self._finish()

        async def _finish(self):
            mems = list(self.ready)[:RAID_MAX]
            if len(mems) < RAID_MIN:
                await self.ctx.send("Not enough players ready. Queue remains open.")
                st = self.cog.queue_panels.get(self.ctx.guild.id)
                if st:
                    panel = KamiAdventure.QueuePanelView(self.cog, self.ctx, st["difficulty"])
                    try:
                        msg = await self.ctx.channel.fetch_message(st["msg_id"])
                        await msg.edit(content=None, embed=kami_embed(
                            title=f"{EMO_RAID} Raid Queue Panel", desc="Reopened."
                        ), view=panel)
                    except Exception:
                        pass
                return
            # keys if needed
            host_id = None
            if RAID_KEYS_REQUIRED.get(self.diff, 0) > 0:
                for uid in mems:
                    if self.cog.dm.get_raid_keys(self.ctx.guild.id, uid).get(self.diff, 0) > 0:
                        host_id = uid; break
                if host_id is None:
                    await self.ctx.send("Nobody in the ready group has a required key. Queue continues.")
                    return
                self.cog.dm.spend_raid_key(self.ctx.guild.id, host_id, self.diff)
            await self.cog._run_raid_simulation(self.ctx, self.diff, mems)
            self.cog.queue_panels.pop(self.ctx.guild.id, None)

    class SpawnFightView(discord.ui.View):
        def __init__(self, cog: "KamiAdventure", monster: Dict[str, Any], msg_id: int):
            super().__init__(timeout=90)
            self.cog = cog
            self.monster = monster
            self.msg_id = msg_id
            self.claimed_by: Optional[int] = None

        async def on_timeout(self):
            # Despawn if still active
            for gid, g in list(self.cog.dm._cache.items()):
                sp = g.get("spawns")
                if sp and sp.get("active") and sp["active"].get("msg_id") == self.msg_id:
                    sp["active"] = None
                    self.cog.dm.save(int(gid))

        @discord.ui.button(label="Fight!", style=discord.ButtonStyle.primary, emoji="⚔️")
        async def fight(self, itx: discord.Interaction, btn: discord.ui.Button):
            await itx.response.defer(ephemeral=True)
            if self.claimed_by and self.claimed_by != itx.user.id:
                return await itx.followup.send("Someone already claimed this fight!", ephemeral=True)
            self.claimed_by = itx.user.id
            # Create a visible message in the spawn channel as the battle anchor
            anchor_msg = await self.cog.bot.get_channel(itx.channel_id).send(
                f"{itx.user.mention} engages **{self.monster['name']}**!"
            )
            ctx = await self.cog.bot.get_context(anchor_msg)
            # Run battle against a copy of the monster
            p = self.cog.dm.get_player(itx.guild_id, itx.user.id, itx.user.display_name)
            await self.cog._battle(ctx, itx.user, p, forced_monster=dict(self.monster))
            # mark despawn
            g = self.cog.dm._ensure(itx.guild_id)
            if g["spawns"].get("active", {}).get("msg_id") == self.msg_id:
                g["spawns"]["active"] = None
                self.cog.dm.save(itx.guild_id)

    def __init__(self, bot: commands.Bot, *, data_dir: str = "data/kami"):
        # --- core wiring ---
        self.bot = bot

        # ensure a stable data dir is available to everything
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        # persistence & bank
        self.dm = DataManager(self.data_dir)
        self.bank = BankAdapter(bot, self.dm)

        # ---------- Monster pool (JSON first, fallback to built-in) ----------
        # Expecting: data/kami/monsters.json
        # Format: [{"name": "...", "hp": 120, "atk": 15, "def": 6, "crit": 12, "coin_drop": [100, 200], "rpg_xp": 110}, ...]
        monsters_path = os.path.join(self.data_dir, "monsters.json")
        self.monsters: List[Dict[str, Any]] = []
        try:
            if os.path.exists(monsters_path):
                with open(monsters_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # light validation / normalization
                    normd: List[Dict[str, Any]] = []
                    for m in loaded:
                        if not isinstance(m, dict):  # skip garbage
                            continue
                        name = str(m.get("name", "Unknown"))
                        hp = int(m.get("hp", 50))
                        atk = int(m.get("atk", 5))
                        deff = int(m.get("def", 2))
                        crit = int(m.get("crit", 5))
                        coin = m.get("coin_drop", [10, 20])
                        if isinstance(coin, (list, tuple)) and len(coin) == 2:
                            coin = [int(coin[0]), int(coin[1])]
                        else:
                            coin = [10, 20]
                        rpgxp = int(m.get("rpg_xp", 20))
                        normd.append({
                            "name": name, "hp": hp, "atk": atk, "def": deff,
                            "crit": crit, "coin_drop": coin, "rpg_xp": rpgxp
                        })
                    self.monsters = normd
                    (getattr(bot, "logger", None) or print)(
                        f"[Kami] Loaded {len(self.monsters)} monsters from {monsters_path}"
                    )
            else:
                # fallback: use inline MONSTERS constant if present
                try:
                    # MONSTERS may be a list of tuples from your earlier code
                    self.monsters = [
                        {
                            "name": n, "hp": hp, "atk": a, "def": d, "crit": c,
                            "coin_drop": [coins[0], coins[1]], "rpg_xp": xp
                        }
                        for (n, hp, a, d, c, coins, xp) in MONSTERS
                    ]
                    (getattr(bot, "logger", None) or print)(
                        f"[Kami] monsters.json not found; using built-in pool ({len(self.monsters)} monsters)"
                    )
                except Exception:
                    self.monsters = []
                    (getattr(bot, "logger", None) or print)(
                        f"[Kami] monsters.json not found and no built-in MONSTERS available — pool is empty"
                    )
        except Exception as e:
            self.monsters = []
            (getattr(bot, "logger", None) or print)(
                f"[Kami] Failed to load monsters.json ({e!r}); pool is empty"
            )

        # ---------- raid & queue state ----------
        # one active raid per guild
        self.active_raids: Dict[int, Dict[str, Any]] = {}

        # legacy text queue (still supported)
        self.queues: Dict[int, Dict[str, deque[int]]] = {}
        self.queue_cooldown: Dict[int, Dict[int, int]] = {}
        self.queue_lock: Dict[int, bool] = {}

        # interactive queue panel state
        # {gid: {"msg_id": int, "difficulty": str, "members": set[int], "host": int}}
        self.queue_panels: Dict[int, Dict[str, Any]] = {}

        # ---------- auto-spawns ----------
        # background spawn loop; safe-start (avoid double start on cog reloads)
        try:
            loop_task = getattr(self.spawn_loop, "is_running", None)
            if callable(loop_task):
                if not self.spawn_loop.is_running():
                    self.spawn_loop.start()
            else:
                # older discord.py: just start
                self.spawn_loop.start()
        except Exception as e:
            (getattr(bot, "logger", None) or print)(
                f"[Kami] spawn_loop start failed: {e!r}"
            )

    # ---- internal helpers ----
    def _award_rpg_xp(self, member: discord.Member, amount: int) -> Tuple[int, int]:
        p = self.dm.get_player(member.guild.id, member.id, member.display_name)
        p["rpg_xp"] += int(amount)
        leveled = 0
        while p["rpg_xp"] >= 50 * p["rpg_level"]:
            p["rpg_xp"] -= 50 * p["rpg_level"]
            p["rpg_level"] += 1
            leveled += 1
            p["max_hp"] += 5
            p["atk"] += 1
            if p["rpg_level"] % 3 == 0:
                p["def"] += 1
        self.dm.save(member.guild.id)
        return p["rpg_level"], leveled

    def _player_power(self, p: Dict[str, Any]) -> Tuple[int, int, int]:
        atk = p["atk"] + (p["weapon"]["atk"] if p.get("weapon") else 0)
        deff = p["def"] + (p["armor"]["def"] if p.get("armor") else 0)
        crit = p["crit"]
        return atk, deff, crit

    def _monster_pick(self, level: int) -> Dict[str, Any]:
        """Pick a monster from JSON pool (or fallback), scaling by player level."""
        if not self.monsters:
            # ultra-safe fallback
            return {"name": "Training Dummy", "hp": 10, "atk": 1, "def": 0, "crit": 0, "coin_drop": [1, 1], "rpg_xp": 1}

        m = random.choice(self.monsters)
        scale = max(1.0, 1.0 + (level - 1) * 0.07)
        return {
            "name": m["name"],
            "hp": int(m["hp"] * scale),
            "atk": int(m["atk"] * scale),
            "def": int(m["def"] * scale),
            "crit": int(m["crit"]),
            "coin_drop": (int(m["coin_drop"][0]), int(m["coin_drop"][1])),
            "rpg_xp": int(m["rpg_xp"]),
        }

    async def _announce_badges(self, ctx: commands.Context, uid: int, new_ids: List[str]):
        if not new_ids:
            return
        parts = [f"{BADGES[i]['emoji']} **{BADGES[i]['title']}**" for i in new_ids if i in BADGES]
        if parts:
            await ctx.send("🎖️ New badge unlocked: " + " • ".join(parts))

    def _stats_embed(self, member: discord.Member, p: Dict[str, Any]) -> discord.Embed:
        atk, deff, crit = self._player_power(p)
        bal = self.bank.get_balance(member.guild.id, member.id)
        e = kami_embed(
            title=f"{EMO_SPARK} {member.display_name}'s Kami Adventurer Card",
            desc="A traveler between worlds—guided by Kami winds and anime logic.",
        )
        e.add_field(name="Level", value=f"{p['rpg_level']} ({p['rpg_xp']}/{50*p['rpg_level']})", inline=True)
        e.add_field(name="HP", value=f"{EMO_HP} {p['hp']}/{p['max_hp']}", inline=True)
        e.add_field(name="Wealth", value=f"{EMO_KAMICOIN} {bal} {KAMICOIN_NAME}", inline=True)
        e.add_field(name="Offense", value=f"{EMO_ATK} **{atk}**", inline=True)
        e.add_field(name="Defense", value=f"{EMO_DEF} **{deff}**", inline=True)
        e.add_field(name="Crit", value=f"{EMO_CRIT} **{crit}%**", inline=True)
        w = p.get("weapon"); a = p.get("armor")
        e.add_field(name="Weapon", value=w["name"] if w else "None", inline=True)
        e.add_field(name="Armor", value=a["name"] if a else "None", inline=True)
        e.add_field(name="Inventory", value=f"{len(p.get('inventory', []))} items", inline=True)
        clan = p.get("clan") or "None"
        e.add_field(name="Guild (Clan)", value=f"{EMO_GUILD} {clan}", inline=True)
        e.add_field(name="Race", value=p.get("race","Human"), inline=True)

        bag = self.dm.badges_get(member.guild.id, member.id)
        if bag:
            shown = []
            for bid in sorted(bag.keys()):
                meta = BADGES.get(bid)
                if meta:
                    shown.append(f"{meta['emoji']} {meta['title']}")
            if shown:
                e.add_field(name="Badges", value=" • ".join(shown[:10]), inline=False)
        return e

    # ===== Inventory helpers (stacking for mats & potions) =====
    def _shop_catalog(self, gid: int) -> List[Dict[str, Any]]:
        """Weekly-rotating shop catalog, deterministic per-guild via shop_seed."""
        g = self.dm._ensure(gid)
        rnd = random.Random(g.get("shop_seed", 1))
        items: List[Dict[str, Any]] = []

        # rotate across the full pools by ISO week for variety
        weekly = int(current_week_id().split("W")[1])
        wlen = max(1, len(BASE_WEAPONS))
        alen = max(1, len(BASE_ARMOR))
        wrot = weekly % wlen
        arot = (weekly * 2) % alen
        wpool = BASE_WEAPONS[wrot:] + BASE_WEAPONS[:wrot]
        apool = BASE_ARMOR[arot:] + BASE_ARMOR[:arot]

        # sample a curated set (avoid ValueError by bounding k)
        wpick = rnd.sample(wpool + BASE_WEAPONS, k=min(8, wlen))
        apick = rnd.sample(apool + BASE_ARMOR, k=min(8, alen))

        for name, atk, rarity, price in wpick:
            items.append({"t": "weapon", "name": name, "atk": int(atk), "rarity": rarity, "price": int(price)})
        for name, df, rarity, price in apick:
            items.append({"t": "armor", "name": name, "def": int(df), "rarity": rarity, "price": int(price)})
        for name, eff, price in CONSUMABLES:
            items.append({"t": "consumable", "name": name, "effect": eff, "rarity": "Uncommon", "price": int(price), "qty": 1})

        rarity_rank = {"Common":0, "Uncommon":1, "Rare":2, "Epic":3, "Legendary":4}
        items.sort(key=lambda o: (rarity_rank.get(o.get("rarity","Common"), 0), o["name"]))
        return items[:20]

    def _inv_add(self, p: Dict[str, Any], item: Dict[str, Any], qty: int = 1):
        """Add item(s) to inventory; stack mats/consumables by name."""
        if qty <= 0:
            return
        it = dict(item)
        it_qty = max(1, int(it.get("qty", 1))) * int(qty)
        stackable = it.get("t") in ("mat", "consumable")
        inv = p.setdefault("inventory", [])

        if stackable:
            name = it.get("name")
            for cur in inv:
                if cur.get("t") == it.get("t") and cur.get("name") == name:
                    cur["qty"] = int(cur.get("qty", 1)) + it_qty
                    return
            it["qty"] = it_qty
            inv.append(it)
        else:
            # add N distinct copies (no qty field)
            for _ in range(int(qty)):
                cp = dict(it); cp.pop("qty", None)
                inv.append(cp)

    def _inv_remove_mats(self, p: Dict[str, Any], name: str, qty: int) -> bool:
        """Remove material stacks by name; returns True if fully satisfied."""
        need = max(0, int(qty))
        if need == 0:
            return True
        inv = p.get("inventory", [])
        for it in inv:
            if it.get("t") == "mat" and it.get("name") == name:
                have = int(it.get("qty", 0))
                if have <= 0:
                    continue
                take = min(have, need)
                it["qty"] = have - take
                need -= take
                if need <= 0:
                    break
        p["inventory"] = [
            it for it in inv
            if not (it.get("t") == "mat" and it.get("name") == name and int(it.get("qty", 0)) <= 0)
        ]
        return need <= 0

    # ---------- Battle (solo) ----------
    async def _battle(self, ctx: commands.Context, member: discord.Member, p: Dict[str, Any],
                      forced_monster: Optional[Dict[str, Any]] = None) -> None:
        monster = forced_monster or self._monster_pick(p["rpg_level"])
        atk, deff, crit = self._player_power(p)

        # Special intro for rarer monsters (fallback-safe)
        rarity = str(monster.get("rarity", "")).lower()
        rarity_emoji = monster.get("emoji", "🐾")
        if rarity == "legendary":
            await ctx.send(embed=kami_embed(
                title=f"🌟 Legendary Encounter! {monster['name']} Appears!",
                desc="The ground trembles as a legendary foe approaches...",
                color=0xFFD700
            ))
        elif rarity == "epic":
            await ctx.send(embed=kami_embed(
                title=f"🔥 Epic Monster! {monster['name']} Appears!",
                desc="You feel a surge of energy as an epic battle begins!",
                color=0xFF4500
            ))

        m_hp = int(monster["hp"])
        p_hp = int(p["hp"])
        log: List[str] = [f"{rarity_emoji} **A wild {monster['name']} appears!**"]

        turn = 1
        MAX_TURNS = 15
        while m_hp > 0 and p_hp > 0 and turn <= MAX_TURNS:
            # Player attack
            dmg = max(1, atk - int(monster["def"]) // 2)
            if roll_pct(crit):
                dmg = int(dmg * 1.7)
                log.append(f"Turn {turn}: You crit for **{dmg}**! {EMO_CRIT}")
            else:
                log.append(f"Turn {turn}: You strike for **{dmg}**. {EMO_ATK}")
            m_hp -= dmg
            if m_hp <= 0:
                break

            # Monster attack
            mdmg = max(1, int(monster["atk"]) - deff // 2)
            if roll_pct(int(monster.get("crit", 0))):
                mdmg = int(mdmg * 1.6)
                log.append(f"Turn {turn}: {monster['name']} CRITS you for **{mdmg}**! {EMO_CRIT}")
            else:
                log.append(f"Turn {turn}: {monster['name']} hits you for **{mdmg}**.")
            p_hp = max(0, p_hp - mdmg)
            turn += 1

        desc = "\n".join(log[:18])

        # Victory
        if m_hp <= 0 and p_hp > 0:
            coin_reward = random.randint(*monster["coin_drop"])
            self.bank.add_balance(member.guild.id, member.id, coin_reward)
            level_now, leveled = self._award_rpg_xp(member, monster["rpg_xp"])
            try_award_global_xp(self.bot, member, max(1, monster["rpg_xp"] // 3))
            p["hp"] = max(1, p_hp)
            self.dm.save(member.guild.id)

            # Stats/badges
            self.dm.stats_add(member.guild.id, member.id, kills=1, coins_earned=coin_reward)
            new_badges = self.dm.badges_eval(member.guild.id, member.id)
            await self._announce_badges(ctx, member.id, new_badges)

            # Clan XP trickle
            clan = self.dm.clan_of(member.guild.id, member.id)
            if clan:
                self.dm.clan_award_xp(member.guild.id, clan, 5)

            e = discord.Embed(title=f"Victory! {monster['name']} is defeated!",
                              description=desc, color=0x2ECC71)
            e.add_field(name="Loot", value=f"{EMO_LOOT} +{coin_reward} {KAMICOIN_NAME}", inline=True)
            e.add_field(name="RPG XP", value=f"+{monster['rpg_xp']} (Level {level_now})", inline=True)
            if leveled:
                e.add_field(name="Level Up!", value=f"Leveled up **{leveled}** time(s)! {EMO_SPARK}", inline=False)
            await ctx.send(embed=e)

        # Defeat
        elif p_hp <= 0 and m_hp > 0:
            p["hp"] = max(1, p["max_hp"] // 3)
            self.dm.save(member.guild.id)
            e = discord.Embed(
                title=f"Defeat... {monster['name']} stands tall.",
                description=desc + f"\nYou awaken at a roadside shrine with {p['hp']} HP.",
                color=0xE74C3C,
            )
            await ctx.send(embed=e)

        # Stalemate
        else:
            p["hp"] = p_hp
            self.dm.save(member.guild.id)
            e = discord.Embed(
                title=f"Stalemate with {monster['name']}",
                description=desc + "\nBoth sides retreat to lick their wounds.",
                color=0xF39C12,
            )
            await ctx.send(embed=e)

    # ========= Raid Queue helpers (legacy) =========
    def _q_for(self, gid: int) -> Dict[str, deque[int]]:
        if gid not in self.queues:
            self.queues[gid] = {k: deque() for k in BOSS_POOLS.keys()}
        return self.queues[gid]

    def _q_cd_for(self, gid: int) -> Dict[int, int]:
        return self.queue_cooldown.setdefault(gid, {})

    def _q_in_any(self, gid: int, uid: int) -> Optional[str]:
        q = self._q_for(gid)
        for diff, dq in q.items():
            if uid in dq:
                return diff
        return None

    def _q_remove(self, gid: int, uid: int) -> None:
        q = self._q_for(gid)
        for dq in q.values():
            try:
                dq.remove(uid)
            except ValueError:
                pass

    def _q_pick_party(self, gid: int, difficulty: str) -> Optional[List[int]]:
        q_all = self._q_for(gid)
        if difficulty not in q_all:
            return None
        q = q_all[difficulty]
        if len(q) < RAID_MIN:
            return None

        size_goal = min(QUEUE_TARGET, RAID_MAX)
        picked: List[int] = []
        for uid in list(q):
            if len(picked) >= size_goal:
                break
            picked.append(uid)
        if len(picked) < RAID_MIN:
            return None

        # ensure at least one key holder if keys are required
        need_key = RAID_KEYS_REQUIRED.get(difficulty, 0) > 0
        if need_key:
            has_key = None
            for uid in picked:
                keys = self.dm.get_raid_keys(gid, uid)
                if int(keys.get(difficulty, 0)) > 0:
                    has_key = uid
                    break
            if has_key is None:
                for uid in list(q)[len(picked):]:
                    keys = self.dm.get_raid_keys(gid, uid)
                    if int(keys.get(difficulty, 0)) > 0:
                        picked.pop()
                        picked.append(uid)
                        has_key = uid
                        break
            if has_key is None:
                return None
        return picked

    async def _q_ready_check(self, ctx: commands.Context, difficulty: str, party: List[int]) -> List[int]:
        mentions = " ".join(f"<@{uid}>" for uid in party)
        msg = await ctx.send(
            f"🪄 **Raid Queue Ready-Check** ({difficulty.title()})\n"
            f"{mentions}\n"
            f"Type **ready** (or **r**/**y**) within **{QUEUE_READY_TIMEOUT}s** to join this run."
        )
        ready: set[int] = set()

        def check(m: discord.Message):
            if m.channel.id != ctx.channel.id: return False
            if m.author.bot: return False
            if m.author.id not in party: return False
            txt = m.content.strip().lower()
            return txt in ("ready", "r", "y")

        try:
            end_ts = now_ts() + QUEUE_READY_TIMEOUT
            while now_ts() < end_ts and len(ready) < len(party):
                timeout = max(1, end_ts - now_ts())
                m = await ctx.bot.wait_for("message", timeout=timeout, check=check)
                ready.add(m.author.id)
        except Exception:
            pass

        failed = set(party) - ready
        cd = self._q_cd_for(ctx.guild.id)
        for uid in failed:
            cd[uid] = now_ts() + QUEUE_REJOIN_COOLDOWN

        await ctx.send(
            f"✅ Ready: {', '.join(f'<@{u}>' for u in ready) or 'none'}\n"
            f"⏳ Not ready: {', '.join(f'<@{u}>' for u in failed) or 'none'}"
        )
        return list(ready)

    async def _run_raid_simulation(self, ctx: commands.Context, difficulty: str, party: List[int]):
        players = [self.dm.get_player(ctx.guild.id, uid) for uid in party]
        lvls = [p["rpg_level"] for p in players if p]
        avg_lvl = sum(lvls) / max(1, len(lvls))
        boss = self._pick_boss(difficulty, avg_lvl)

        mech = boss["mech"]
        team_temp_hp: Dict[int, int] = {}
        team_atk: Dict[int, int] = {}
        team_def: Dict[int, int] = {}
        team_crit: Dict[int, int] = {}
        log: List[str] = [f"**Raid begins against {boss['name']}!** (Temporary HP used for fairness)"]

        # party snapshot
        for uid in party:
            p = self.dm.get_player(ctx.guild.id, uid)
            a, d, c = self._player_power(p)
            base_hp = max(30, p["max_hp"])
            clan = self.dm.clan_of(ctx.guild.id, uid)
            hp_mult = 1.0
            if clan:
                cl = self.dm.clans(ctx.guild.id).get(clan)
                if cl:
                    hp_mult += guild_perks(cl["level"])["raid_hp_buff"]
            team_temp_hp[uid] = int(base_hp * hp_mult)
            team_atk[uid] = a; team_def[uid] = d; team_crit[uid] = c

        rnd = 1; MAX_R = 20; original_scaled_hp = boss["hp"]
        while boss["hp"] > 0 and any(hp > 0 for hp in team_temp_hp.values()) and rnd <= MAX_R:
            # party dps
            total = 0
            for uid, a in team_atk.items():
                if team_temp_hp[uid] <= 0: continue
                dmg = max(1, a - boss["def"] // 2)
                if roll_pct(team_crit[uid]): dmg = int(dmg * 1.6)
                if mech.get("resist") in ("iron_hide", "wind_skin"): dmg = int(dmg * 0.90)
                total += dmg
            if mech["shield_active"]:
                total = int(total * 0.70); mech["shield_rounds"] -= 1
                if mech["shield_rounds"] <= 0:
                    mech["shield_active"] = False; log.append("Boss shield **breaks**! Damage returns to normal.")
            total = int(total * mech.get("affix_damage_taken_mult", 1.0))
            boss["hp"] = max(0, boss["hp"] - total)
            log.append(f"Round {rnd}: Party deals **{total}** damage.")
            if boss["hp"] <= 0: break

            # enrage check
            if not mech["enraged"] and boss["hp"] <= int(mech["enrage_at"] * original_scaled_hp):
                mech["enraged"] = True; log.append("The boss **ENRAGES**! Its attacks grow fiercer.")

            # boss aoe
            b_atk = int(boss["atk"] * (1.35 if mech["enraged"] else 1.0))
            b_dmg_base = max(1, b_atk - int(sum(team_def.values())/max(1,len(team_def))) // 2)
            for uid in list(team_temp_hp.keys()):
                if team_temp_hp[uid] <= 0: continue
                spl = int(b_dmg_base * random.uniform(0.8, 1.2))
                if roll_pct(boss["crit"]): spl = int(spl * 1.4)
                team_temp_hp[uid] = max(0, team_temp_hp[uid] - spl)

            # weekly affix: volcanic tick
            if mech.get("affix_volcanic"):
                extra = random.randint(4, 7)
                for uid in list(team_temp_hp.keys()):
                    if team_temp_hp[uid] > 0: team_temp_hp[uid] = max(0, team_temp_hp[uid] - extra)
                log.append(f"Volcanic erupts! Extra **{extra}** damage to everyone.")

            alive = sum(1 for v in team_temp_hp.values() if v > 0)
            log.append(f"Round {rnd}: {boss['name']} strikes! Survivors: **{alive}/{len(team_temp_hp)}**.")
            rnd += 1

        party_members: List[discord.Member] = [ctx.guild.get_member(uid) for uid in party if ctx.guild.get_member(uid)]
        week = current_week_id(); diff = difficulty
        full_reward = {m.id: not self.dm.has_lockout(ctx.guild.id, m.id, diff, week) for m in party_members}

        if boss["hp"] <= 0 and any(team_temp_hp.values()):
            coin_lo, coin_hi = boss["coin_drop"]; per_player_coins = random.randint(coin_lo, coin_hi)
            per_player_rpgxp = boss["rpg_xp"]; clan_xp = boss.get("clan_xp", 25)
            for m in party_members:
                if full_reward[m.id]:
                    self.bank.add_balance(ctx.guild.id, m.id, per_player_coins)
                    self._award_rpg_xp(m, per_player_rpgxp)
                    try_award_global_xp(self.bot, m, max(1, per_player_rpgxp // 3))
                    self.dm.set_lockout(ctx.guild.id, m.id, diff, week)
                    # mats & chance bonus via guild perk
                    shard_q = random.randint(2, 5)
                    core_q = 1 if diff in ("hard","legendary") and random.random() < (0.6 if diff=="legendary" else 0.35) else 0
                    clan_name = self.dm.clan_of(ctx.guild.id, m.id)
                    if clan_name:
                        cl = self.dm.clans(ctx.guild.id).get(clan_name)
                        if cl and roll_pct(guild_perks(cl["level"])["extra_loot"]*100):
                            shard_q += random.randint(1,2)
                    p = self.dm.get_player(ctx.guild.id, m.id)
                    if shard_q: self._inv_add(p, {"t":"mat","name":"Shard","qty":shard_q}, 1)
                    if core_q:  self._inv_add(p, {"t":"mat","name":"Core","qty":core_q}, 1)
                    self.dm.save(ctx.guild.id)
                    # achievements
                    self.dm.stats_add(ctx.guild.id, m.id, raid_wins=1, coins_earned=per_player_coins)
                    nb = self.dm.badges_eval(ctx.guild.id, m.id); await self._announce_badges(ctx, m.id, nb)
                else:
                    # consolation
                    cons = max(1, per_player_coins // 4)
                    self.bank.add_balance(ctx.guild.id, m.id, cons)
                    self.dm.stats_add(ctx.guild.id, m.id, coins_earned=cons)
                # leaderboard win & time
                self.dm.lb_record_win(ctx.guild.id, m.id, rnd)
                clan = self.dm.clan_of(ctx.guild.id, m.id)
                if clan:
                    self.dm.clan_award_xp(ctx.guild.id, clan, clan_xp)

            desc = "\n".join(log[:22])
            e = kami_embed(
                title=f"🔥 RAID VICTORY! {boss['name']} falls.",
                desc=desc + "\n*Full rewards granted for eligible players.*",
                color=0x2ECC71
            )
            e.add_field(
                name="Rewards (each, if eligible)",
                value=f"{EMO_KAMICOIN}{per_player_coins} • +{per_player_rpgxp} RPG XP • +{clan_xp} Guild XP\n"
                      f"Loot: {EMO_SHARD} Shards, {EMO_CORE} Cores (chance)",
                inline=False
            )
            await ctx.send(embed=e)
        else:
            desc = "\n".join(log[:22])
            await ctx.send(embed=kami_embed(
                title=f"💀 RAID FAILED... {boss['name']} endures.",
                desc=desc + "\nTrain up and try again!",
                color=0xE74C3C
            ))

    # =========================
    # Commands (hybrid)
    # =========================
    @commands.hybrid_group(
        name="kami",
        aliases=("k",),  # <-- enables !k as a prefix alias (slash can't have aliases)
        description="Kami Adventure — an isekai-flavored RPG.",
        invoke_without_command=True,
    )
    async def kami(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            return await ctx.invoke(self.kami_help)

    @kami.command(name="help", description="Show commands for Kami Adventure.")
    async def kami_help(self, ctx: commands.Context):
        affix_name, affix_desc = weekly_affix()

        base = [
            "**Register & Profile**",
            "`/kami register` • `/kami profile [user]` • `/kami race info|choose`",
            "",
            "**Action**",
            "`/kami explore` • `/kami battle` • `/kami heal [small|medium|elixir|auto]`",
            "",
            "**Inventory & Gear**",
            "`/kami inventory` • `/kami equip <index>` • `/kami unequip <weapon|armor>`",
            "",
            "**Shop**",
            "`/kami shop` • `/kami buy <name...>` • `/kami sell <index>`",
            "",
            f"**Guilds (Clans) {EMO_GUILD}**",
            "`/kami guild create <name>` • `/kami guild join <name>` • `/kami guild leave`",
            "`/kami guild info [name]` • `/kami guild list`",
            "`/kami guild promote <@user>` • `/kami guild demote <@user>` • `/kami guild transfer <@user>`",
            "`/kami guild invite <@user>` • `/kami guild invites` • `/kami guild accept <name>` • `/kami guild decline <name>`",
            "",
            f"**Raids {EMO_RAID}**",
            "`/kami raid start <easy|normal|hard|legendary>` • `/kami raid join` • `/kami raid begin`",
            "`/kami raid status` • `/kami raid cancel` • `/kami raid leaderboard [wins|fastest] [all|season]` • `/kami raid affix`",
            "`/kami raid queue panel <difficulty>` (interactive)",
            "",
            "**Crafting & Trading**",
            "`/kami craft list` • `/kami craft make <recipe>` • `/kami trade list|sell|buy`",
            "",
            "**Keys & Daily**",
            "`/kami keys` • `/kami daily`",
            "",
            "**Adventure Spawns**",
            "`/kami adventure setchannel <#channel>` • `/kami adventure spawnrate <minsec> <maxsec>` • `/kami adventure toggle <on|off>` • `/kami adventure status`",
        ]

        # show admin tools only to admins
        if ctx.author.guild_permissions.administrator:
            base += [
                "",
                "**Admin Tools**",
                "`/kami admin genmonsters [count]` • `/kami admin reloadmonsters`",
            ]

        desc = "\n".join(base + [
            "",
            f"**This Week’s Raid Affix:** **{affix_name}** — *{affix_desc}*",
        ])

        e = discord.Embed(
            title=f"{EMO_SPARK} Kami Adventure — Commands",
            color=DEFAULT_COLOR,
            description=desc,
        )
        await ctx.send(embed=e)

    # tiny convenience alias so you can just type !kamihelp
    @commands.command(name="kamihelp", aliases=("kami_help","kamih"))
    async def kamihelp_alias(self, ctx: commands.Context):
        await self.kami_help(ctx)

    # ===== Registration & Profile =====
    @kami.command(name="register", description="Register your adventurer.")
    async def kami_register(self, ctx: commands.Context):
        p = self.dm.get_player(ctx.guild.id, ctx.author.id)
        if p:
            return await ctx.send(f"{EMO_SPARK} You're already registered, {ctx.author.mention}!")
        self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        self.dm.save(ctx.guild.id)
        await ctx.send(f"{EMO_SPARK} {ctx.author.mention}, your soul drifts into a new world... Welcome to **Kami Adventure**!")

    @kami.command(name="profile", description="Show your adventurer card.")
    async def kami_profile(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        p = self.dm.get_player(ctx.guild.id, member.id, member.display_name)
        e = self._stats_embed(member, p)
        await ctx.send(embed=e)

    # ===== Races =====
    @kami.command(name="race", description="Choose or view your race.")
    async def kami_race(self, ctx: commands.Context, action: Optional[str] = None, *, value: Optional[str] = None):
        action = (action or "info").lower()
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)

        if action == "info":
            rows = [f"**{name}** — {data['desc']}" for name, data in RACES.items()]
            await ctx.send(embed=kami_embed(title="Races", desc="\n".join(rows)))
            return

        if action in ("choose", "set"):
            if not value:
                return await ctx.send("Usage: `!kami race choose <Human|Kitsune|Oni|Tengu|Yokai>`")
            key = value.strip().title()
            key = "Yokai" if key in ("Youkai", "Yōkai", "Yokai") else key
            if key not in RACES:
                return await ctx.send("Unknown race. Use `!kami race info`.")

            # Idempotent re-apply of race perks: remove previous race perks, add new race perks.
            prev = p.get("race", "Human")
            prev_perks = RACES.get(prev, {}).get("perks", {"atk": 0, "def": 0, "max_hp": 0, "crit": 0})
            new_perks  = RACES[key]["perks"]

            # remove previous
            p["atk"]  -= int(prev_perks.get("atk", 0))
            p["def"]  -= int(prev_perks.get("def", 0))
            p["crit"] -= int(prev_perks.get("crit", 0))
            p["max_hp"] -= int(prev_perks.get("max_hp", 0))

            # add new
            p["atk"]  += int(new_perks.get("atk", 0))
            p["def"]  += int(new_perks.get("def", 0))
            p["crit"] += int(new_perks.get("crit", 0))
            p["max_hp"] += int(new_perks.get("max_hp", 0))
            # clamp hp to new max
            p["hp"] = min(int(p["hp"]), int(p["max_hp"]))
            p["race"] = key

            self.dm.badge_unlock(ctx.guild.id, ctx.author.id, "kami_chosen")
            self.dm.save(ctx.guild.id)
            await ctx.send(f"{EMO_SPARK} Race set to **{key}** — {RACES[key]['desc']}")
            return

        await ctx.send("Try: `!kami race info` or `!kami race choose <race>`")

    # ======= ADMIN: generate / reload monsters.json =======
    @kami.group(name="admin", description="Kami admin tools.", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def kami_admin(self, ctx: commands.Context):
        await ctx.send("Subcommands: `/kami admin genmonsters [count]`, `/kami admin reloadmonsters`")

    @kami_admin.command(name="genmonsters", description="Generate monsters.json with N entries (default 120, max 200).")
    @commands.has_permissions(administrator=True)
    async def kami_admin_genmonsters(self, ctx: commands.Context, count: Optional[int] = 120):
        count = max(30, min(int(count or 120), 200))
        rng = random.Random("kami_monster_seed")

        adjectives = [
            "Ashen","Blighted","Clockwork","Crimson","Dawn","Duskwalker","Elder","Feral","Frost","Gale",
            "Gloom","Golden","Gravel","Howling","Ivory","Jade","Lunar","Mire","Mist","Moonlit","Night",
            "Obsidian","Quartz","Rift","River","Sable","Salt","Shade","Shattered","Silver","Sky","Solar",
            "Star","Storm","Stone","Thorn","Thunder","Umbral","Verdant","Void","Whisper","Wild","Windswept"
        ]
        creatures = [
            "Slime","Wisp","Fox Spirit","Bandit","Boar","Wolf","Kappa","Carp Spirit","Oni Bruiser","Tanuki",
            "Raiju","Tengu Duelist","Golem","Basilisk","Vine Horror","Moth Queen","Shrine Guardian","Samurai Shade",
            "Crystal Crab","Prowler","Serpent","Banshee","Cinder Imp","Mire Stalker","Storm Roc","Moon Hare",
            "Rootcaller","Mire Hydra","Bone Drake","Grove Titan","Aether Wyvern","Sky Leviathan","Mech Oni",
            "Lotus Specter","River Siren","Blight Colossus","Astral Stag","Fog Djinn","Thunder Yak","Fang Spider"
        ]

        def roll(a, b): return rng.randint(a, b)
        def pick(seq): return rng.choice(seq)

        monsters: List[Dict[str, Any]] = []
        # (n, hp, atk, def, crit, coin_lo-hi, xp_lo-hi) by tier
        tiers = [
            (40, (50, 100),  (6, 12),   (1, 4),   (5, 8),   (12, 28),  (18, 30)),   # commons
            (40, (100, 220), (12, 22),  (4, 8),   (6,10),   (30, 70),  (35, 75)),   # brutes
            (20, (220, 380), (22, 34),  (8, 12),  (8,12),   (70,120),  (80,130)),   # elites
            (15, (380, 650), (34, 48),  (12,18),  (10,14),  (120,220), (140,220)),  # epics
            (10, (650, 900), (48, 62),  (16,22),  (12,16),  (220,360), (220,320)),  # legends
        ]

        for n, hp_rng, atk_rng, def_rng, crit_rng, coin_rng, xp_rng in tiers:
            for _ in range(n):
                name = f"{pick(adjectives)} {pick(creatures)}"
                hp   = roll(*hp_rng)
                atk  = roll(*atk_rng)
                deff = roll(*def_rng)
                crit = roll(*crit_rng)
                c_lo = roll(*coin_rng)
                c_hi = max(c_lo + 1, c_lo + roll(8, max(10, coin_rng[1] - coin_rng[0])))
                rpgx = roll(*xp_rng)
                monsters.append({
                    "name": name,
                    "hp": hp,
                    "atk": atk,
                    "def": deff,
                    "crit": crit,
                    "coin_drop": [c_lo, c_hi],
                    "rpg_xp": rpgx
                })
                if len(monsters) >= count:
                    break
            if len(monsters) >= count:
                break

        path = os.path.join(self.data_dir, "monsters.json")
        os.makedirs(self.data_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(monsters, f, ensure_ascii=False, indent=2)

        self.monsters = monsters
        await ctx.send(f"✅ Generated **{len(monsters)}** monsters at `{path}` and reloaded.")

    @kami_admin.command(name="reloadmonsters", description="Reload monsters.json from disk.")
    @commands.has_permissions(administrator=True)
    async def kami_admin_reloadmonsters(self, ctx: commands.Context):
        path = os.path.join(self.data_dir, "monsters.json")
        if not os.path.exists(path):
            return await ctx.send("No monsters.json found. Run `/kami admin genmonsters` first.")
        try:
            with open(path, "r", encoding="utf-8") as f:
                monsters = json.load(f)
            # minimal validation
            good: List[Dict[str, Any]] = []
            for m in monsters:
                if not isinstance(m, dict):
                    continue
                if all(k in m for k in ("name", "hp", "atk", "def", "crit", "coin_drop", "rpg_xp")):
                    good.append(m)
            self.monsters = good
            await ctx.send(f"🔄 Reloaded **{len(good)}** monsters from file.")
        except Exception as e:
            await ctx.send(f"❗ Failed to reload: `{type(e).__name__}: {e}`")    # ===== Action =====
    @kami.command(name="explore", description="Explore the realms and see what fate brings.")
    async def kami_explore(self, ctx: commands.Context):
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        now = now_ts()
        if now - p.get("last_explore", 0) < 20:
            return await ctx.send("The Kami winds are still shifting... wait a few moments before exploring again.")
        p["last_explore"] = now

        roll = random.random()
        if roll < 0.45:
            await ctx.send(f"{EMO_EXPLORE} You stumble into a dramatic clearing... Something moves!")
            await self._battle(ctx, ctx.author, p)
        elif roll < 0.75:
            coins = random.randint(10, 40)
            new_bal = self.bank.add_balance(ctx.guild.id, ctx.author.id, coins)
            self._award_rpg_xp(ctx.author, 8)
            try_award_global_xp(self.bot, ctx.author, 3)
            clan = self.dm.clan_of(ctx.guild.id, ctx.author.id)
            if clan:
                self.dm.clan_award_xp(ctx.guild.id, clan, 2)
            extra = ""
            if random.random() < 0.30:
                q = random.randint(1, 3)
                self._inv_add(p, {"t": "mat", "name": "Shard", "qty": q}, 1)
                self.dm.save(ctx.guild.id)
                extra = f"\nYou also found {EMO_SHARD} Shards ×{q}!"
            e = discord.Embed(
                title=f"Found Treasure! {EMO_LOOT}",
                description=f"You find a suspiciously shiny chest.\n+{coins} {KAMICOIN_NAME}\nNew balance: **{new_bal}**{extra}",
                color=0xF1C40F,
            )
            await ctx.send(embed=e)
        else:
            pool = random.choice([BASE_WEAPONS, BASE_ARMOR, CONSUMABLES])
            item = random.choice(pool)
            if pool is CONSUMABLES:
                obj = {"t": "consumable", "name": item[0], "effect": item[1], "price": item[2], "rarity": "Uncommon", "qty": 1}
                rarity = "Uncommon"
            elif pool is BASE_WEAPONS:
                obj = {"t": "weapon", "name": item[0], "atk": item[1], "rarity": item[2], "price": item[3]}
                rarity = item[2]
            else:
                obj = {"t": "armor", "name": item[0], "def": item[1], "rarity": item[2], "price": item[3]}
                rarity = item[2]
            self._inv_add(p, obj, 1)
            self.dm.save(ctx.guild.id)
            e = discord.Embed(
                title="You found something!",
                description=f"**{obj['name']}** ({rarity}) added to inventory.",
                color=color_for_rarity(rarity),
            )
            await ctx.send(embed=e)

    @kami.command(name="battle", description="Fight a monster right now.")
    async def kami_battle(self, ctx: commands.Context):
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        await self._battle(ctx, ctx.author, p)

    # ======= HEAL =======
    @kami.command(name="heal", description="Use a potion (or pay coins) to restore HP.")
    async def kami_heal(self, ctx: commands.Context, choice: Optional[str] = "auto"):
        choice = (choice or "auto").lower()
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        if p["hp"] >= p["max_hp"]:
            return await ctx.send("You're already at full HP!")

        inv = p.get("inventory", [])

        def find_potion(filter_min: int | None = None) -> Optional[Tuple[int, Dict[str, Any]]]:
            best: Optional[Tuple[int, Dict[str, Any]]] = None
            for idx, it in enumerate(inv):
                if it.get("t") == "consumable" and it.get("effect", ("", 0))[0] == "heal":
                    amt = int(it["effect"][1]); q = int(it.get("qty", 1))
                    if q <= 0: continue
                    if filter_min is None or amt >= filter_min:
                        if best is None or amt < best[1]["effect"][1]:
                            best = (idx, it)
            return best

        want = {"small":25, "medium":60, "elixir":120}.get(choice, None)
        pick = find_potion(want) if choice in ("small","medium","elixir") else find_potion(None)

        need = p["max_hp"] - p["hp"]
        if pick:
            idx, it = pick
            heal_amt = min(need, int(it["effect"][1]))
            p["hp"] += heal_amt
            it["qty"] = int(it.get("qty", 1)) - 1
            if it["qty"] <= 0:
                inv.pop(idx)
            self.dm.save(ctx.guild.id)
            return await ctx.send(f"{EMO_POTION} Used **{it['name']}** and healed **{heal_amt} HP**. ({p['hp']}/{p['max_hp']})")

        # coin heal
        cost = max(1, math.ceil((p["max_hp"] - p["hp"]) * HEAL_COIN_RATE))
        bal = self.bank.get_balance(ctx.guild.id, ctx.author.id)
        if bal < cost:
            return await ctx.send(f"Not enough coins. Need {EMO_KAMICOIN}{cost}, you have {EMO_KAMICOIN}{bal}.")
        self.bank.add_balance(ctx.guild.id, ctx.author.id, -cost)
        healed = p["max_hp"] - p["hp"]
        p["hp"] = p["max_hp"]
        self.dm.save(ctx.guild.id)
        await ctx.send(f"💸 Paid {EMO_KAMICOIN}{cost} to heal **{healed} HP** to full. ({p['hp']}/{p['max_hp']})")

    # ======= INVENTORY / EQUIP =======
    @kami.command(name="inventory", description="Show your inventory.")
    async def kami_inventory(self, ctx: commands.Context):
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        e = discord.Embed(
            title=f"{ctx.author.display_name}'s Inventory",
            color=DEFAULT_COLOR,
            description="\n".join(self._inv_lines(p))[:3950],
        )
        w = p.get("weapon")
        a = p.get("armor")
        e.add_field(name="Equipped Weapon", value=w["name"] if w else "None", inline=True)
        e.add_field(name="Equipped Armor", value=a["name"] if a else "None", inline=True)
        await ctx.send(embed=e)

    def _inv_lines(self, p: Dict[str, Any]) -> List[str]:
        lines = []
        for i, it in enumerate(p.get("inventory", []), start=1):
            t = it.get("t")
            if t == "weapon":
                price = f" • {EMO_KAMICOIN}{it['price']}" if "price" in it else ""
                lines.append(f"**{i}.** {it['name']} — {EMO_ATK}+{it['atk']} • {it.get('rarity','?')}{price}")
            elif t == "armor":
                price = f" • {EMO_KAMICOIN}{it['price']}" if "price" in it else ""
                lines.append(f"**{i}.** {it['name']} — {EMO_DEF}+{it['def']} • {it.get('rarity','?')}{price}")
            elif t == "consumable":
                eff, amt = it.get("effect", ("?", 0))
                q = int(it.get("qty", 1))
                price = f" • {EMO_KAMICOIN}{it['price']}" if "price" in it else ""
                lines.append(f"**{i}.** {EMO_POTION} {it.get('name','?')} ×{q} — {eff} {amt}{price}")
            elif t == "mat":
                q = int(it.get("qty", 1))
                icon = EMO_SHARD if it.get("name") == "Shard" else EMO_CORE
                lines.append(f"**{i}.** {icon} {it.get('name','?')} ×{q}")
        return lines or ["*(inventory is empty)*"]

    @kami.command(name="equip", description="Equip an item by its inventory index.")
    async def kami_equip(self, ctx: commands.Context, index: int):
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        inv = p.get("inventory", [])
        if index < 1 or index > len(inv):
            return await ctx.send("Invalid index.")
        it = inv[index-1]
        if it.get("t") == "weapon":
            p["weapon"] = it
            await ctx.send(f"Equipped weapon: **{it['name']}** (+{it['atk']} ATK).")
        elif it.get("t") == "armor":
            p["armor"] = it
            await ctx.send(f"Equipped armor: **{it['name']}** (+{it['def']} DEF).")
        else:
            return await ctx.send("You can only equip weapons or armor.")
        self.dm.save(ctx.guild.id)

    @kami.command(name="unequip", description="Unequip a slot: weapon or armor.")
    async def kami_unequip(self, ctx: commands.Context, slot: str):
        slot = slot.lower()
        if slot not in ("weapon", "armor"):
            return await ctx.send("Slot must be `weapon` or `armor`.")
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        if not p.get(slot):
            return await ctx.send(f"No {slot} is equipped.")
        old = p[slot]
        p[slot] = None
        self.dm.save(ctx.guild.id)
        await ctx.send(f"Unequipped **{old['name']}** from {slot} slot.")

    # ===== Shop helpers with guild discount (Feature A) =====
    def _effective_price(self, gid: int, uid: int, base_price: int) -> Tuple[int, float]:
        discount = 0.0
        clan_name = self.dm.clan_of(gid, uid)
        if clan_name:
            cl = self.dm.clans(gid).get(clan_name)
            if cl:
                discount = float(guild_perks(cl["level"]).get("shop_discount", 0.0))
        final = max(1, math.floor(int(base_price) * (1.0 - discount)))
        return final, discount

    def _format_price_line(self, gid: int, uid: int, base_price: int) -> str:
        price, disc = self._effective_price(gid, uid, base_price)
        if disc > 0:
            pct = int(round(disc * 100))
            return f"{EMO_KAMICOIN} **{price}** *(~{pct}% guild discount)*"
        return f"{EMO_KAMICOIN} **{base_price}**"

    def _find_shop_item_by_name(self, catalog: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
        q = name.strip().lower()
        for it in catalog:
            if it.get("name", "").lower() == q:
                return it
        for it in catalog:
            if it.get("name", "").lower().startswith(q):
                return it
        return None

    # ======= SHOP / BUY / SELL (discount applied) =======
    @kami.command(name="shop", description="Show shop items for this guild (your price shown).")
    async def kami_shop(self, ctx: commands.Context):
        items = self._shop_catalog(ctx.guild.id)
        lines = []
        for i, it in enumerate(items, start=1):
            if it["t"] == "weapon":
                stat = f"{EMO_ATK}+{it['atk']}"
            elif it["t"] == "armor":
                stat = f"{EMO_DEF}+{it['def']}"
            else:
                eff, amt = it["effect"]; q = it.get("qty", 1)
                stat = f"{EMO_POTION} {eff} {amt} ×{q}"
            price_line = self._format_price_line(ctx.guild.id, ctx.author.id, it["price"])
            lines.append(f"**{i}.** {it['name']} — {stat} • *{it['rarity']}* • {price_line}")
        e = discord.Embed(
            title=f"🏪 Kami Shop — Week {current_week_id()}",
            description="\n".join(lines[:50]) or "Nothing in stock.",
            color=DEFAULT_COLOR,
        )
        e.set_footer(text="Use /kami buy <name> to purchase")
        await ctx.send(embed=e)

    @kami.command(name="buy", description="Buy an item by name (case-insensitive).")
    async def kami_buy(self, ctx: commands.Context, *, name: str):
        catalog = self._shop_catalog(ctx.guild.id)
        match = self._find_shop_item_by_name(catalog, name)
        if not match:
            return await ctx.send("Item not found. Use `/kami shop` to see names.")

        price, disc = self._effective_price(ctx.guild.id, ctx.author.id, match["price"])
        bal = self.bank.get_balance(ctx.guild.id, ctx.author.id)
        if bal < price:
            return await ctx.send(f"Not enough coins. Price: {EMO_KAMICOIN}{price}, you have {EMO_KAMICOIN}{bal}.")

        self.bank.add_balance(ctx.guild.id, ctx.author.id, -price)
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)

        if match["t"] == "weapon":
            self._inv_add(p, {"t":"weapon","name":match["name"],"atk":match["atk"],"rarity":match["rarity"]}, 1)
        elif match["t"] == "armor":
            self._inv_add(p, {"t":"armor","name":match["name"],"def":match["def"],"rarity":match["rarity"]}, 1)
        else:
            self._inv_add(p, {"t":"consumable","name":match["name"],"effect":match["effect"],"qty":1}, 1)

        self.dm.save(ctx.guild.id)
        disc_note = f" (after ~{int(disc*100)}% guild discount)" if disc > 0 else ""
        await ctx.send(f"Purchased **{match['name']}** for {EMO_KAMICOIN}{price}{disc_note}.")

    @kami.command(name="sell", description="Sell an inventory item by index (50% value).")
    async def kami_sell(self, ctx: commands.Context, index: int):
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        inv = p.get("inventory", [])
        if index < 1 or index > len(inv):
            return await ctx.send("Invalid index.")
        it = inv.pop(index-1)
        price = int(it.get("price", 0))
        payout = max(1, price // 2)
        self.bank.add_balance(ctx.guild.id, ctx.author.id, payout)
        self.dm.save(ctx.guild.id)
        await ctx.send(f"Sold **{it['name']}** for {EMO_KAMICOIN}{payout}.")

    # ===== Consumables use (Feature B) =====
    def _inv_remove_one_consumable(self, p: Dict[str, Any], name: str) -> bool:
        inv = p.get("inventory", [])
        q = name.strip().lower()
        for it in list(inv):
            if it.get("t") == "consumable" and it.get("name","").lower() == q:
                qty = int(it.get("qty", 0))
                if qty <= 0: continue
                it["qty"] = qty - 1
                if it["qty"] <= 0:
                    inv.remove(it)
                return True
        for it in list(inv):
            if it.get("t") == "consumable" and it.get("name","").lower().startswith(q):
                qty = int(it.get("qty", 0))
                if qty <= 0: continue
                it["qty"] = qty - 1
                if it["qty"] <= 0:
                    inv.remove(it)
                return True
        return False

    def _lookup_potion(self, label: str) -> Optional[Tuple[str, Tuple[str, int]]]:
        pots = {n.lower(): (n, eff) for n, eff, _ in CONSUMABLES}
        q = label.strip().lower()
        if q in pots:
            return (pots[q][0], pots[q][1])
        alias = {"small":"Small Potion","medium":"Medium Potion","elixir":"Elixir"}
        if q in alias:
            n = alias[q]
            return (n, pots[n.lower()][1])
        for k, (n, eff) in pots.items():
            if k.startswith(q):
                return (n, eff)
        return None

    @kami.command(name="use", description="Use a consumable (e.g., /kami use Small Potion).")
    async def kami_use(self, ctx: commands.Context, *, item: str):
        if not item or not item.strip():
            return await ctx.send("Usage: `/kami use <potion>` — e.g. `/kami use Small Potion`.")
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)

        looked = self._lookup_potion(item)
        if not looked:
            return await ctx.send("Unknown potion. Try: Small Potion, Medium Potion, or Elixir.")
        name, (eff, amt) = looked

        has_stack = any(
            it.get("t") == "consumable" and it.get("name","").lower() == name.lower() and int(it.get("qty",0)) > 0
            for it in p.get("inventory", [])
        ) or any(
            it.get("t") == "consumable" and it.get("name","").lower().startswith(name.lower()) and int(it.get("qty",0)) > 0
            for it in p.get("inventory", [])
        )
        if not has_stack:
            return await ctx.send(f"You don't have any **{name}** in your inventory.")

        if eff == "heal":
            missing = max(0, int(p["max_hp"]) - int(p["hp"]))
            if missing <= 0:
                return await ctx.send("You're already at full HP. Save the potion for later! 💡")
            heal = min(missing, int(amt))
            p["hp"] = int(p["hp"]) + heal
            self._inv_remove_one_consumable(p, name)
            self.dm.save(ctx.guild.id)

            e = kami_embed(
                title=f"{EMO_POTION} Used {name}",
                desc=f"Healed **{heal} HP**. You are now at **{p['hp']}/{p['max_hp']} HP**.",
                color=0x2ECC71
            )
            await ctx.send(embed=e)
        else:
            await ctx.send("That consumable effect isn't supported yet.")

    # ======= GUILDS =======
    @kami.group(name="guild", description="Guild (Clan) management.", invoke_without_command=True)
    async def kami_guild(self, ctx: commands.Context):
        await ctx.send("Use `/kami guild create|join|leave|info|list`.")

    @kami_guild.command(name="create", description="Create a new guild.")
    async def guild_create(self, ctx: commands.Context, *, name: str):
        name = name.strip()
        if not (3 <= len(name) <= 20):
            return await ctx.send("Guild name must be between 3 and 20 characters.")
        if self.dm.clan_of(ctx.guild.id, ctx.author.id):
            return await ctx.send("You're already in a guild.")
        if name in self.dm.clans(ctx.guild.id):
            return await ctx.send("That guild name is already taken.")
        self.dm.clan_create(ctx.guild.id, ctx.author.id, name)  # (gid, owner_id, name)
        self.dm.save(ctx.guild.id)
        await ctx.send(f"{EMO_GUILD} Guild **{name}** created with {ctx.author.mention} as leader!")

    @kami_guild.command(name="join", description="Join an existing guild.")
    async def guild_join(self, ctx: commands.Context, *, name: str):
        name = name.strip()
        if self.dm.clan_of(ctx.guild.id, ctx.author.id):
            return await ctx.send("You're already in a guild.")
        clans = self.dm.clans(ctx.guild.id)
        if name not in clans:
            return await ctx.send("No such guild.")
        self.dm.clan_add_member(ctx.guild.id, name, ctx.author.id)
        self.dm.save(ctx.guild.id)
        await ctx.send(f"You joined guild **{name}**.")

    @kami_guild.command(name="leave", description="Leave your current guild.")
    async def guild_leave(self, ctx: commands.Context):
        clan = self.dm.clan_of(ctx.guild.id, ctx.author.id)
        if not clan:
            return await ctx.send("You're not in a guild.")
        self.dm.clan_remove_member(ctx.guild.id, clan, ctx.author.id)
        self.dm.save(ctx.guild.id)
        await ctx.send(f"You have left guild **{clan}**.")

    @kami_guild.command(name="info", description="View info about a guild.")
    async def guild_info(self, ctx: commands.Context, *, name: Optional[str] = None):
        clan = name or self.dm.clan_of(ctx.guild.id, ctx.author.id)
        if not clan:
            return await ctx.send("No guild specified.")
        cl = self.dm.clans(ctx.guild.id).get(clan)
        if not cl:
            return await ctx.send("Guild not found.")
        members = [f"<@{m}>" for m in cl["members"]]
        e = kami_embed(title=f"{EMO_GUILD} {clan} — Guild Info",
                       desc=f"Leader: <@{cl['owner_id']}> • Level {cl['level']} • XP {cl['xp']}")
        e.add_field(name="Members", value=", ".join(members) or "None", inline=False)
        await ctx.send(embed=e)

    @kami_guild.command(name="list", description="List all guilds.")
    async def guild_list(self, ctx: commands.Context):
        clans = self.dm.clans(ctx.guild.id)
        if not clans:
            return await ctx.send("No guilds exist.")
        lines = [f"{name} — Lv {data['level']} ({len(data['members'])} members)"
                 for name, data in clans.items()]
        await ctx.send(embed=kami_embed(title="Guilds", desc="\n".join(lines)))

    # ======= RAID PANEL QUEUE =======
    @kami.group(name="raid", description="Raid commands.", invoke_without_command=True)
    async def kami_raid(self, ctx: commands.Context):
        await ctx.send("Use `/kami raid queuepanel <difficulty>` or `/kami raid leaderboard ...`.")

    @kami_raid.command(name="queuepanel", description="Open an interactive raid queue panel.")
    async def raid_queue_panel(self, ctx: commands.Context, difficulty: str):
        difficulty = difficulty.lower()
        if difficulty not in BOSS_POOLS:
            return await ctx.send("Invalid difficulty.")
        if ctx.guild.id in self.queue_panels:
            return await ctx.send("A panel is already open in this guild.")
        panel = KamiAdventure.QueuePanelView(self, ctx, difficulty)
        msg = await ctx.send(embed=kami_embed(title=f"{EMO_RAID} Raid Queue Panel",
                                              desc=f"Host: {ctx.author.mention} • Difficulty: {difficulty.title()}"),
                             view=panel)
        self.queue_panels[ctx.guild.id] = {
            "msg_id": msg.id,
            "difficulty": difficulty,
            "members": {ctx.author.id},
            "host": ctx.author.id
        }

    @kami_raid.command(name="leaderboard", description="Show raid leaderboard.")
    async def raid_leaderboard(self, ctx: commands.Context, metric: Optional[str] = "wins", scope: Optional[str] = "all"):
        metric = (metric or "wins").lower(); scope = (scope or "all").lower()
        if metric not in ("wins", "fastest"):
            return await ctx.send("Metric must be `wins` or `fastest`.")
        if scope not in ("all", "season"):
            return await ctx.send("Scope must be `all` or `season`.")
        lb = (self.dm._ensure(ctx.guild.id)["leaderboard"]
              if scope == "all" else self.dm._ensure(ctx.guild.id)["leaderboard_season"])
        users = lb.get("users", {})
        if not users:
            return await ctx.send("No leaderboard data yet.")
        if metric == "wins":
            sorted_users = sorted(users.items(), key=lambda kv: kv[1].get("raid_wins", 0), reverse=True)
            lines = [f"<@{uid}> — {data.get('raid_wins', 0)} wins" for uid, data in sorted_users[:10]]
        else:
            sorted_users = sorted((kv for kv in users.items() if kv[1].get("fastest")), key=lambda kv: kv[1]["fastest"])
            lines = [f"<@{uid}> — {data['fastest']}s" for uid, data in sorted_users[:10]]
        await ctx.send(embed=kami_embed(title=f"Raid Leaderboard — {metric.title()} ({scope.title()})",
                                        desc="\n".join(lines)))

    # ======= MARKET =======
    @kami.group(name="market", description="Player market for trading.")
    async def kami_market(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            return await ctx.send("Try: `/kami market list`, `/kami market buy <id>`, `/kami market sell <index> <price>`")

    @kami_market.command(name="list", description="View current player listings.")
    async def market_list(self, ctx: commands.Context):
        listings = self.dm.market_listings(ctx.guild.id)
        if not listings:
            return await ctx.send("No listings in the market.")
        lines = []
        for lid, data in listings.items():
            seller = ctx.guild.get_member(data["seller_id"])
            seller_name = seller.display_name if seller else f"ID {data['seller_id']}"
            item = data["item"]
            if item.get("t") == "weapon":
                desc = f"{EMO_ATK}+{item['atk']} {item.get('rarity','')}".strip()
            elif item.get("t") == "armor":
                desc = f"{EMO_DEF}+{item['def']} {item.get('rarity','')}".strip()
            elif item.get("t") == "consumable":
                desc = f"{item['effect'][0]} {item['effect'][1]} ({item.get('qty',1)}x)"
            else:
                desc = f"{item.get('name','?')} ×{item.get('qty',1)}"
            lines.append(f"**#{lid}** — {item.get('name','?')} ({desc}) • {EMO_KAMICOIN}{data['price']} • Seller: {seller_name}")
        await ctx.send(embed=kami_embed(title="Player Market", desc="\n".join(lines[:30])))

    @kami_market.command(name="sell", description="List an inventory item for sale.")
    async def market_sell(self, ctx: commands.Context, index: int, price: int):
        p = self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        inv = p.get("inventory", [])
        if index < 1 or index > len(inv):
            return await ctx.send("Invalid index.")
        it = inv.pop(index-1)
        lid = self.dm.market_new_listing(ctx.guild.id, it, ctx.author.id, price)
        self.dm.save(ctx.guild.id)
        await ctx.send(f"Listed **{it.get('name','?')}** for {EMO_KAMICOIN}{price} (ID #{lid}).")

    @kami_market.command(name="buy", description="Buy an item from the market by ID.")
    async def market_buy(self, ctx: commands.Context, listing_id: int):
        listing = self.dm.market_pop(ctx.guild.id, listing_id)
        if not listing:
            return await ctx.send("Listing not found.")
        bal = self.bank.get_balance(ctx.guild.id, ctx.author.id)
        if bal < listing["price"]:
            # put it back
            self.dm.market_new_listing(ctx.guild.id, listing["item"], listing["seller_id"], listing["price"])
            return await ctx.send("Not enough coins to buy this item.")
        self.bank.add_balance(ctx.guild.id, ctx.author.id, -listing["price"])
        self._inv_add(self.dm.get_player(ctx.guild.id, ctx.author.id, ctx.author.display_name), listing["item"], 1)
        self.bank.add_balance(ctx.guild.id, listing["seller_id"], listing["price"])
        self.dm.save(ctx.guild.id)
        await ctx.send(f"Purchased **{listing['item'].get('name','?')}** from the market.")

    # ======= LORE =======
    @kami.command(name="lore", description="Discover the legends of Kami Adventure.")
    async def kami_lore(self, ctx: commands.Context):
        lore_text = (
            f"In the drifting realms between worlds, Kami winds carry lost souls into an endless adventure.\n"
            f"You are one such soul — free to forge guilds, hunt monsters, and seek glory.\n"
            f"But beware... the Kami smile upon the bold and curse the careless."
        )
        await ctx.send(embed=kami_embed(title="🌸 Kami Lore", desc=lore_text))

    # ======= BADGES =======
    @kami.command(name="badges", description="View all possible badges.")
    async def kami_badges(self, ctx: commands.Context):
        lines = [f"{v['emoji']} **{v['title']}** — {v.get('desc','')}" for v in BADGES.values()]
        await ctx.send(embed=kami_embed(title="🎖️ Kami Badges", desc="\n".join(lines)))

    # ======= KEYS & DAILY =======
    @kami.command(name="keys", description="Show your raid keys by difficulty.")
    async def kami_keys(self, ctx: commands.Context):
        keys = self.dm.get_raid_keys(ctx.guild.id, ctx.author.id)
        parts = []
        for d in ("easy","normal","hard","legendary"):
            parts.append(f"{d.title()}: **{int(keys.get(d,0))}**")
        await ctx.send(embed=kami_embed(title="🔑 Your Raid Keys", desc="\n".join(parts)))

    @kami.command(name="daily", description="Claim your daily reward.")
    async def kami_daily(self, ctx: commands.Context):
        if not self.dm.daily_can_claim(ctx.guild.id, ctx.author.id):
            return await ctx.send("You already claimed your daily today. Come back tomorrow! ⌛")
        coins = random.randint(60, 120)
        self.bank.add_balance(ctx.guild.id, ctx.author.id, coins)
        self.dm.stats_add(ctx.guild.id, ctx.author.id, coins_earned=coins)
        # 20% chance at a Normal key
        if random.random() < 0.20:
            self.dm.add_raid_key(ctx.guild.id, ctx.author.id, "normal", 1)
            key_text = "\nBonus: **Normal** raid key +1!"
        else:
            key_text = ""
        self.dm.daily_set_claimed(ctx.guild.id, ctx.author.id)
        await ctx.send(embed=kami_embed(title="🌞 Daily Reward",
                                        desc=f"+{EMO_KAMICOIN}{coins}{key_text}"))

    # ======= RAID: Legacy text queue commands =======
    @kami_raid.command(name="start", description="Start/join a text queue for a difficulty.")
    async def raid_start(self, ctx: commands.Context, difficulty: str):
        difficulty = difficulty.lower()
        if difficulty not in BOSS_POOLS:
            return await ctx.send("Difficulty must be one of: easy, normal, hard, legendary.")
        q = self._q_for(ctx.guild.id)[difficulty]
        if ctx.author.id in q:
            return await ctx.send("You're already in that queue.")
        cd = self._q_cd_for(ctx.guild.id)
        if cd.get(ctx.author.id, 0) > now_ts():
            return await ctx.send("You recently failed a ready-check. Please wait a bit before re-joining.")
        q.append(ctx.author.id)
        await ctx.send(f"Queued {ctx.author.mention} for **{difficulty.title()}**. Use `/kami raid begin` when enough players are queued.")
        # auto-begin if enough & has key holder
        party = self._q_pick_party(ctx.guild.id, difficulty)
        if party:
            ready = await self._q_ready_check(ctx, difficulty, party)
            if len(ready) >= RAID_MIN:
                await self._run_raid_simulation(ctx, difficulty, ready)

    @kami_raid.command(name="join", description="Join the most recent queue you can fit in.")
    async def raid_join(self, ctx: commands.Context, difficulty: Optional[str] = None):
        if difficulty:
            difficulty = difficulty.lower()
            if difficulty not in BOSS_POOLS:
                return await ctx.send("Difficulty must be: easy, normal, hard, legendary.")
            targets = [difficulty]
        else:
            # try easier to harder
            targets = ["easy","normal","hard","legendary"]
        cd = self._q_cd_for(ctx.guild.id)
        if cd.get(ctx.author.id, 0) > now_ts():
            return await ctx.send("You recently failed a ready-check. Please wait before re-joining.")
        joined = None
        for diff in targets:
            q = self._q_for(ctx.guild.id)[diff]
            if ctx.author.id not in q:
                q.append(ctx.author.id)
                joined = diff
                break
        if not joined:
            return await ctx.send("You're already in a queue.")
        await ctx.send(f"Joined **{joined.title()}** queue.")
        party = self._q_pick_party(ctx.guild.id, joined)
        if party:
            ready = await self._q_ready_check(ctx, joined, party)
            if len(ready) >= RAID_MIN:
                await self._run_raid_simulation(ctx, joined, ready)

    @kami_raid.command(name="begin", description="Force a ready-check and attempt to start a run.")
    async def raid_begin(self, ctx: commands.Context, difficulty: Optional[str] = None):
        diff = (difficulty or "easy").lower()
        if diff not in BOSS_POOLS:
            return await ctx.send("Difficulty must be: easy, normal, hard, legendary.")
        party = self._q_pick_party(ctx.guild.id, diff)
        if not party:
            return await ctx.send("Not enough players yet.")
        ready = await self._q_ready_check(ctx, diff, party)
        if len(ready) >= RAID_MIN:
            await self._run_raid_simulation(ctx, diff, ready)

    @kami_raid.command(name="status", description="Show queued players by difficulty.")
    async def raid_status(self, ctx: commands.Context):
        q = self._q_for(ctx.guild.id)
        lines = []
        for diff, dq in q.items():
            names = []
            for uid in dq:
                m = ctx.guild.get_member(uid)
                names.append(m.display_name if m else f"ID {uid}")
            lines.append(f"**{diff.title()}** ({len(dq)}): " + (", ".join(names) or "—"))
        await ctx.send(embed=kami_embed(title=f"{EMO_RAID} Raid Queues", desc="\n".join(lines)))

    @kami_raid.command(name="cancel", description="Leave any queues you're in.")
    async def raid_cancel(self, ctx: commands.Context):
        self._q_remove(ctx.guild.id, ctx.author.id)
        await ctx.send("You were removed from all queues.")

    @kami_raid.command(name="affix", description="Show this week’s raid affix.")
    async def raid_affix(self, ctx: commands.Context):
        name, desc = weekly_affix()
        await ctx.send(embed=kami_embed(title="Weekly Raid Affix", desc=f"**{name}** — {desc}"))

    # ======= BOSS PICKER (used by raid simulation) =======
    def _pick_boss(self, difficulty: str, avg_party_level: float) -> Dict[str, Any]:
        pool = BOSS_POOLS.get(difficulty, BOSS_POOLS["easy"])
        b = random.choice(pool)
        (name, hp, atk, deff, crit, coin_rng, rpg_xp, clan_xp) = b

        # scale by party level
        scale = 1.0 + max(0.0, (avg_party_level - 1.0)) * RAID_SCALE_PER_LEVEL
        shp = int(hp * scale)
        satk = int(atk * scale)
        sdef = int(deff * scale)
        scrit = int(crit)

        # weekly affix application
        aff_name, _ = weekly_affix()
        mech = {
            "enraged": False,
            "enrage_at": 0.35,
            "shield_active": False,
            "shield_rounds": 0,
            "resist": None,
            "affix_volcanic": False,
            "affix_damage_taken_mult": 1.0,
        }
        if aff_name == "Fortified":
            sdef = int(round(sdef * 1.15))
        elif aff_name == "Tyrannical":
            shp = int(round(shp * 1.10))
            satk = int(round(satk * 1.10))
        elif aff_name == "Volcanic":
            mech["affix_volcanic"] = True
        elif aff_name == "Icy Veins":
            scrit += 4
        elif aff_name == "Wind Skin":
            mech["resist"] = "wind_skin"
            mech["affix_damage_taken_mult"] = 0.92

        # baseline mechanics by difficulty
        if difficulty in ("hard", "legendary"):
            mech["shield_active"] = True
            mech["shield_rounds"] = 2 if difficulty == "hard" else 3
            mech["resist"] = mech["resist"] or "iron_hide"

        boss = {
            "name": name,
            "hp": shp,
            "atk": satk,
            "def": sdef,
            "crit": scrit,
            "coin_drop": coin_rng,
            "rpg_xp": rpg_xp,
            "clan_xp": clan_xp,
            "mech": mech,
        }
        return boss

    # ======= ADVENTURE SPAWNS (under /kami adventure) =======
    @kami.group(
        name="adventure",
        description="Adventure spawn controls.",
        invoke_without_command=True,
    )
    async def kami_adventure(self, ctx: commands.Context):
        await ctx.send(
            "Try: `/kami adventure setchannel [#channel]`, "
            "`/kami adventure spawnrate <minsec> <maxsec>`, "
            "`/kami adventure toggle <on|off>`, "
            "`/kami adventure status`"
        )

    @kami_adventure.command(name="setchannel", description="Set the channel for auto spawns (defaults to current channel).")
    async def adv_setchannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("Please run this in a text channel or mention one.")
        g = self.dm._ensure(ctx.guild.id)
        sp = g.get("spawns", {})
        sp["channel_id"] = int(channel.id)
        # schedule next spawn
        delay = random.randint(sp.get("min_sec", 900), sp.get("max_sec", 1800))
        sp["next_ts"] = now_ts() + delay
        self.dm.save(ctx.guild.id)
        await ctx.send(f"Auto-spawns will appear in {channel.mention}.")

    @kami_adventure.command(name="spawnrate", description="Set min/max seconds between spawns.")
    async def adv_spawnrate(self, ctx: commands.Context, min_sec: int, max_sec: int):
        if min_sec < 30 or max_sec < min_sec:
            return await ctx.send("Min must be ≥ 30 and max ≥ min.")
        g = self.dm._ensure(ctx.guild.id)
        sp = g.get("spawns", {})
        sp["min_sec"] = int(min_sec)
        sp["max_sec"] = int(max_sec)
        sp["next_ts"] = 0  # recalc soon
        self.dm.save(ctx.guild.id)
        await ctx.send(f"Spawn rate set to **{min_sec}–{max_sec}s**.")

    @kami_adventure.command(name="toggle", description="Turn auto-spawns on or off.")
    async def adv_toggle(self, ctx: commands.Context, state: str):
        state = state.lower()
        if state not in ("on", "off"):
            return await ctx.send("Use `on` or `off`.")
        g = self.dm._ensure(ctx.guild.id)
        sp = g.get("spawns", {})
        sp["enabled"] = (state == "on")
        if sp["enabled"]:
            delay = random.randint(sp.get("min_sec", 900), sp.get("max_sec", 1800))
            sp["next_ts"] = now_ts() + delay
        self.dm.save(ctx.guild.id)
        await ctx.send(f"Auto-spawns **{state}**.")

    @kami_adventure.command(name="status", description="Show current auto-spawn settings.")
    async def adv_status(self, ctx: commands.Context):
        sp = self.dm._ensure(ctx.guild.id).get("spawns", {})
        ch = ctx.guild.get_channel(sp.get("channel_id")) if sp.get("channel_id") else None
        next_ts = int(sp.get("next_ts", 0))
        next_in = max(0, next_ts - now_ts()) if next_ts else 0
        desc = (
            f"Enabled: **{bool(sp.get('enabled', False))}**\n"
            f"Channel: {ch.mention if isinstance(ch, discord.TextChannel) else 'not set'}\n"
            f"Rate: **{sp.get('min_sec', 900)}–{sp.get('max_sec', 1800)}s**\n"
            f"Next spawn in: **{next_in}s**\n"
            f"Active: **{'yes' if sp.get('active') else 'no'}**"
        )
        await ctx.send(embed=kami_embed(title=f"{EMO_EXPLORE} Adventure Spawns — Status", desc=desc))

    @tasks.loop(seconds=15)
    async def spawn_loop(self):
        """Background loop that schedules and drops monsters in configured channels."""
        try:
            now = now_ts()
            for gid_str, g in list(self.dm._cache.items()):
                try:
                    gid = int(gid_str)
                except Exception:
                    continue
                sp = g.get("spawns") or {}
                if not sp.get("enabled"):
                    continue
                if sp.get("active"):
                    continue  # one at a time
                ch_id = sp.get("channel_id")
                if not ch_id:
                    continue
                # schedule
                nxt = int(sp.get("next_ts", 0))
                if nxt <= 0 or now >= nxt:
                    # compute avg player level for nicer scaling
                    players = g.get("players", {}).values()
                    lvls = [int(p.get("rpg_level", 1)) for p in players] or [1]
                    avg_lvl = sum(lvls) / len(lvls)
                    m = self._monster_pick(int(avg_lvl))
                    channel = self.bot.get_channel(int(ch_id))
                    if not isinstance(channel, discord.TextChannel):
                        # invalid channel; disable
                        sp["enabled"] = False
                        self.dm.save(gid)
                        continue
                    view = KamiAdventure.SpawnFightView(self, m, -1)
                    try:
                        msg = await channel.send(
                            embed=kami_embed(
                                title=f"⚔️ A wild {m['name']} appears!",
                                desc="Click **Fight!** to claim this encounter.",
                                color=DEFAULT_COLOR,
                            ),
                            view=view
                        )
                    except Exception:
                        continue
                    # record active
                    view.msg_id = msg.id
                    sp["active"] = {"monster": m, "msg_id": int(msg.id)}
                    # schedule next
                    delay = random.randint(sp.get("min_sec", 900), sp.get("max_sec", 1800))
                    sp["next_ts"] = now_ts() + delay
                    self.dm.save(gid)
        except Exception:
            pass

    @spawn_loop.before_loop
    async def _spawn_loop_before(self):
        await self.bot.wait_until_ready()# ---- extension entrypoint ----
async def setup(bot: commands.Bot):
    await bot.add_cog(KamiAdventure(bot))
