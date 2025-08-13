# cogs/duel.py
from __future__ import annotations
import json, random
from pathlib import Path
from typing import Dict, Any, List, Tuple

import discord
from discord.ext import commands
from carddata import ADV  # element advantages

CARDS_FILE = Path("data") / "cards" / "cards.json"
ADV_MULT = 1.20     # winner element vs loser
DISADV_MULT = 0.80  # loser vs winner
RNG_SWAY = 0.05     # ±5% randomness

def _load_cards() -> Dict[str, Any]:
    if CARDS_FILE.exists():
        import json
        with open(CARDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _inv(data: Dict[str, Any], gid: int, uid: int) -> List[Dict[str, Any]]:
    return data.get(str(gid), {}).get(str(uid), [])

def _elem_mult(a_el: str, b_el: str) -> float:
    if b_el in ADV.get(a_el, []):
        return ADV_MULT
    if a_el in ADV.get(b_el, []):
        return DISADV_MULT
    return 1.0

def _score(attacker: Dict[str, Any], defender: Dict[str, Any]) -> float:
    atk = attacker.get("atk", 100)
    de  = defender.get("def", 100)
    mult = _elem_mult(attacker.get("element",""), defender.get("element",""))
    base = (atk * mult) - (de * 0.5)
    sway = 1.0 + random.uniform(-RNG_SWAY, RNG_SWAY)
    return base * sway

def _best_card(inv: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not inv: return {}
    # pick the highest simple “power”
    return max(inv, key=lambda c: c.get("atk",0) + c.get("def",0))

class Duel(commands.Cog, name="Duel"):
    """Duel using card ATK/DEF and elemental advantage."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="duel", aliases=["battle"])
    async def duel_cmd(self, ctx: commands.Context, member: discord.Member):
        """Duel a member. Uses each side's best card in inventory."""
        if member.bot:
            return await ctx.send("Be nice. Don’t bully bots.")

        data = _load_cards()
        a = _inv(data, ctx.guild.id, ctx.author.id)
        b = _inv(data, ctx.guild.id, member.id)

        if not a:
            return await ctx.send("You have no cards. Pull some first!")
        if not b:
            return await ctx.send(f"{member.display_name} has no cards.")

        A = _best_card(a)
        B = _best_card(b)

        a_score = _score(A, B)
        b_score = _score(B, A)

        if abs(a_score - b_score) < 1e-6:
            result = "It's a draw!"
        elif a_score > b_score:
            result = f"**{ctx.author.display_name}** wins!"
        else:
            result = f"**{member.display_name}** wins!"

        def line(c: Dict[str, Any], who: str) -> str:
            return (f"**{who}** — {c.get('name','?')}  "
                    f"*{c.get('element','?')}*  "
                    f"ATK **{c.get('atk','?')}** / DEF **{c.get('def','?')}**")

        lines = [
            "⚔️ **Duel!**",
            line(A, ctx.author.display_name),
            line(B, member.display_name),
            "",
            result,
        ]
        await ctx.send("\n".join(lines))