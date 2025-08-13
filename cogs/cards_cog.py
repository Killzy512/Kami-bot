# cogs/cards_cog.py
from __future__ import annotations
import json, os, random
from pathlib import Path
from typing import Dict, Any, List, Optional

import discord
from discord.ext import commands

# ---- safety helpers (robust JSON I/O) ----
def _normalize_cards_data(data: Any) -> Dict[str, Any]:
    """Always return a dict like: {'guilds': {...}}."""
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get("guilds"), dict):
        data["guilds"] = {}
    return data

def _read_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"guilds": {}}
    except Exception:
        # corrupted/empty file -> start fresh
        return {"guilds": {}}
    return _normalize_cards_data(data)

def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_normalize_cards_data(data), f, indent=2)

# ---- bank helpers (your bank.py lives in cogs/) ----
from .bank import (
    bank_load, bank_save, set_path as bank_set_path,
    get_balance, add_balance, get_pity, set_pity,
    get_last_daily, set_last_daily,
)

# ---- card pools + element chart + stat ranges ----
# carddata is the top-level folder sitting next to bot.py
from carddata import ALL_CARDS, STAT_RANGES, ADV

DATA_DIR = Path("data") / "cards"
DATA_FILE = DATA_DIR / "cards.json"

# gacha settings
PULL_COST = 100
DISCOUNTS = {5: 0.05, 10: 0.10}  # 5% and 10% off
LEGENDARY_RATE = 0.005           # 0.5% base
PITY_MAX = 100                   # guaranteed legendary on 100th pity

RARITY_ORDER = ["legendary", "epic", "rare", "uncommon", "common"]
BASE_RATES = {                    # will get normalized after pity check
    "legendary": LEGENDARY_RATE,
    "epic": 0.04,
    "rare": 0.10,
    "uncommon": 0.25,
    "common": 0.60,
}

def _load_cards() -> Dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_cards(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _user_inv(data: Dict[str, Any], gid: int, uid: int) -> List[Dict[str, Any]]:
    g = data.setdefault(str(gid), {})
    return g.setdefault(str(uid), [])

def _roll_stats(rarity: str) -> Dict[str, int]:
    r = STAT_RANGES.get(rarity, {"atk": (100, 100), "def": (100, 100)})
    atk = random.randint(*r["atk"])
    de  = random.randint(*r["def"])
    return {"atk": atk, "def": de}

def _pick_rarity(gid: int, uid: int) -> str:
    pity = get_pity(gid, uid)
    if pity >= PITY_MAX - 1:
        return "legendary"

    # normalize rates to sum=1 (legendary base gets a tiny bump from pity if you want)
    rates = dict(BASE_RATES)
    # optional gentle pity curve:
    rates["legendary"] = LEGENDARY_RATE + (pity / PITY_MAX) * LEGENDARY_RATE

    total = sum(rates.values())
    roll = random.random() * total
    acc = 0.0
    for r in RARITY_ORDER[::-1]:  # check from common up, or reverse — doesn’t matter with acc
        acc += rates[r]
        if roll <= acc:
            return r
    return "common"

def _pick_card(rarity: str) -> Dict[str, Any]:
    pool = ALL_CARDS.get(rarity, [])
    if not pool:
        raise commands.CommandError(f"No cards defined for rarity '{rarity}'.")
    base = random.choice(pool)
    stats = _roll_stats(rarity)
    return {
        "name": base["name"],
        "element": base["element"],
        "rarity": rarity,
        **stats,
    }

class Cards(commands.Cog, name="Cards"):
    """Gacha pulls + inventory."""

    def __init__(self, bot: commands.Bot, bank_path: Optional[str] = None):
        self.bot = bot

        # wire up the bank file if provided
        if bank_path:
            bank_set_path(bank_path)
        bank_load()

        # ensure folder exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # 20-second safeguard: always load a valid structure
        data = _normalize_cards_data(_read_json(DATA_FILE))
        _write_json(DATA_FILE, data)   # write back the healed structure
        self._cards = data

    @commands.command(name="initcards", aliases=["initcard"])
    async def init_cmd(self, ctx: commands.Context):
        """Create folders/files needed by the cards system."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not DATA_FILE.exists():
            _save_cards({})
        await ctx.send("✅ Cards system initialized.")

    @commands.command(name="inventory", aliases=["inv"])
    async def inv_cmd(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show your (or another member's) pulled cards."""
        member = member or ctx.author
        data = _load_cards()
        inv = _user_inv(data, ctx.guild.id, member.id)

        if not inv:
            await ctx.send(f"📦 {member.display_name} has no cards yet.")
            return

        # group by rarity for prettier display
        by_r = {"legendary": [], "epic": [], "rare": [], "uncommon": [], "common": []}
        for c in inv:
            by_r.get(c.get("rarity", "common"), []).append(c)

        lines = []
        for r in RARITY_ORDER[::-1]:  # show common -> legendary
            bucket = by_r[r]
            if not bucket:
                continue
            lines.append(f"**{r.title()}** ({len(bucket)}):")
            for card in bucket[:10]:
                n = card["name"]; e = card["element"]; a = card.get("atk", "?"); d = card.get("def", "?")
                lines.append(f"• {n} — {e}  *(ATK {a} / DEF {d})*")
            if len(bucket) > 10:
                lines.append(f"…and {len(bucket)-10} more.")
        await ctx.send("\n".join(lines))

    @commands.command(name="pull")
    async def pull_cmd(self, ctx: commands.Context, amount: int = 1):
        """Pull 1/5/10 cards, pay with KamiCoins (discounts for 5/10)."""
        if amount not in (1, 5, 10):
            return await ctx.send("Choose 1, 5, or 10 pulls.")

        # cost with discount
        cost = PULL_COST * amount
        disc = DISCOUNTS.get(amount, 0.0)
        if disc:
            cost = int(round(cost * (1.0 - disc)))

        bal = get_balance(ctx.guild.id, ctx.author.id)
        if bal < cost:
            return await ctx.send(f"❌ You need {cost} KamiCoins, you have {bal}.")

        # pay
        add_balance(ctx.guild.id, ctx.author.id, -cost)

        data = _load_cards()
        inv = _user_inv(data, ctx.guild.id, ctx.author.id)

        pulls: List[Dict[str, Any]] = []
        pity = get_pity(ctx.guild.id, ctx.author.id)

        for _ in range(amount):
            rarity = _pick_rarity(ctx.guild.id, ctx.author.id)
            card = _pick_card(rarity)
            pulls.append(card)
            inv.append(card)

            # pity update
            if rarity == "legendary":
                pity = 0
            else:
                pity = min(PITY_MAX, pity + 1)

        set_pity(ctx.guild.id, ctx.author.id, pity)
        _save_cards(data)
        bank_save()

        # show results
        by_r = {}
        for c in pulls:
            by_r.setdefault(c["rarity"], []).append(c)

        lines = [f"🪄 **You pulled {amount}!** *(paid {cost} KamiCoins)*"]
        for r in RARITY_ORDER:  # legendary first
            if r not in by_r: continue
            lines.append(f"\n**{r.title()}** ×{len(by_r[r])}:")
            for c in by_r[r]:
                lines.append(f"• {c['name']} — {c['element']} *(ATK {c['atk']} / DEF {c['def']})*")

        await ctx.send("\n".join(lines))