# cogs/xp.py
from __future__ import annotations
import json, os, time, random
from typing import Dict, Any, Tuple

import discord
from discord.ext import commands, tasks

# ---------- config ----------
XP_FILE = "xp.json"

MSG_XP_RANGE = (15, 25)     # per message, on cooldown
MSG_COOLDOWN = 60           # seconds per-user

REACT_XP = 5                # when someone reacts (cooldown’d)
REACT_COOLDOWN = 30         # seconds per-user

VOICE_XP_PER_MIN = 5        # per active minute
VOICE_TICK_SEC = 60         # how often to credit ongoing sessions

# leveling curve: XP needed to go from L -> L+1
def xp_needed_for(level: int) -> int:
    # mild quadratic; tweak as you like
    return 5 * level * level + 50 * level + 100

# ---------- storage ----------
DATA: Dict[str, Any] = {"guilds": {}}          # persisted
_msg_cd: Dict[Tuple[int, int], float] = {}     # (gid, uid) -> last msg ts
_react_cd: Dict[Tuple[int, int], float] = {}   # (gid, uid) -> last reaction ts
_voice_join: Dict[Tuple[int, int], float] = {} # (gid, uid) -> joined ts (active session)

def _g(gid: int) -> Dict[str, Any]:
    g = DATA["guilds"].setdefault(str(gid), {})
    g.setdefault("users", {})
    return g

def _u(gid: int, uid: int) -> Dict[str, Any]:
    users = _g(gid)["users"]
    return users.setdefault(str(uid), {"xp": 0})

def xp_load(path: str = XP_FILE) -> None:
    global DATA
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            DATA = json.load(f)
    else:
        DATA = {"guilds": {}}
        xp_save(path)

def xp_save(path: str = XP_FILE) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(DATA, f, indent=2)

# helpers
def total_xp(gid: int, uid: int) -> int:
    return int(_u(gid, uid)["xp"])

def set_total_xp(gid: int, uid: int, value: int) -> int:
    _u(gid, uid)["xp"] = max(0, int(value))
    return _u(gid, uid)["xp"]

def add_xp(gid: int, uid: int, amount: int) -> int:
    return set_total_xp(gid, uid, total_xp(gid, uid) + int(amount))

def level_from_total(xp: int) -> Tuple[int, int, int]:
    """returns (level, xp_into_level, needed_for_next)"""
    level = 0
    rem = xp
    while True:
        need = xp_needed_for(level + 1)
        if rem < need:
            return level, rem, need
        rem -= need
        level += 1

# ---------- Cog ----------
class XP(commands.Cog):
    def __init__(self, bot: commands.Bot, *, file_path: str = XP_FILE):
        self.bot = bot
        self.file_path = file_path
        xp_load(self.file_path)
        # start loops inside cogs (discord.py 2.x)
        if not self.autosave.is_running():
            self.autosave.start()
        if not self.voice_tick.is_running():
            self.voice_tick.start()

    # ===== Loops =====
    @tasks.loop(minutes=5)
    async def autosave(self):
        xp_save(self.file_path)

    @tasks.loop(seconds=VOICE_TICK_SEC)
    async def voice_tick(self):
        now = time.time()
        for (gid, uid), joined in list(_voice_join.items()):
            member = self.bot.get_guild(gid).get_member(uid) if self.bot.get_guild(gid) else None
            if not member or not member.voice or not member.voice.channel:
                # ended elsewhere; finalize and drop
                minutes = max(0, int((now - joined) // 60))
                if minutes:
                    add_xp(gid, uid, minutes * VOICE_XP_PER_MIN)
                _voice_join.pop((gid, uid), None)
                continue

            # still in voice; credit last tick interval
            minutes = VOICE_TICK_SEC // 60
            if minutes:
                add_xp(gid, uid, minutes * VOICE_XP_PER_MIN)

    # ===== Events =====
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot or not msg.guild:
            return
        key = (msg.guild.id, msg.author.id)
        last = _msg_cd.get(key, 0.0)
        now = time.time()
        if now - last < MSG_COOLDOWN:
            return
        _msg_cd[key] = now
        add_xp(msg.guild.id, msg.author.id, random.randint(*MSG_XP_RANGE))

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User | discord.Member):
        if user.bot or not reaction.message.guild:
            return
        key = (reaction.message.guild.id, user.id)
        last = _react_cd.get(key, 0.0)
        now = time.time()
        if now - last < REACT_COOLDOWN:
            return
        _react_cd[key] = now
        add_xp(reaction.message.guild.id, user.id, REACT_XP)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        gid, uid = member.guild.id, member.id
        key = (gid, uid)
        now = time.time()

        before_ch = before.channel.id if before and before.channel else None
        after_ch = after.channel.id if after and after.channel else None

        # joined
        if not before_ch and after_ch:
            _voice_join[key] = now
            return

        # left
        if before_ch and not after_ch:
            joined = _voice_join.pop(key, None)
            if joined:
                minutes = max(0, int((now - joined) // 60))
                if minutes:
                    add_xp(gid, uid, minutes * VOICE_XP_PER_MIN)
            return

        # moved channels: treat as continuous
        if before_ch and after_ch and before_ch != after_ch:
            # nothing special; session continues
            return

    # ===== Commands =====
    @commands.command(name="level", aliases=["xp"])
    async def level_cmd(self, ctx: commands.Context, member: discord.Member | None = None):
        """Show your (or someone’s) level + XP."""
        member = member or ctx.author
        txp = total_xp(ctx.guild.id, member.id)
        lvl, into, need = level_from_total(txp)
        await ctx.send(f"⭐ **{member.display_name}** — Level **{lvl}** ({into}/{need} XP into next) • Total XP: **{txp}**")

    @commands.command(name="xptop", aliases=["levels", "leaderboard"])
    async def xptop_cmd(self, ctx: commands.Context, limit: int = 10):
        """Top XP users in this server."""
        g = _g(ctx.guild.id)
        users = [(int(uid), data.get("xp", 0)) for uid, data in g["users"].items()]
        users.sort(key=lambda t: t[1], reverse=True)
        lines = []
        for i, (uid, txp) in enumerate(users[:max(1, min(25, limit))], start=1):
            m = ctx.guild.get_member(uid)
            name = m.display_name if m else f"<left:{uid}>"
            lvl, into, need = level_from_total(txp)
            lines.append(f"**{i}.** {name} — L{lvl} ({txp} XP)")
        if not lines:
            lines = ["Nobody has XP yet."]
        await ctx.send("\n".join(lines))

    # --- admin ---
    def _is_admin():
        async def predicate(ctx: commands.Context):
            return ctx.author.guild_permissions.administrator
        return commands.check(predicate)

    @commands.command(name="xpadd")
    @_is_admin()
    async def xpadd_cmd(self, ctx: commands.Context, member: discord.Member, amount: int):
        new = add_xp(ctx.guild.id, member.id, amount)
        await ctx.send(f"✅ Added **{amount}** XP to **{member.display_name}** (now {new} total).")

    @commands.command(name="xpset")
    @_is_admin()
    async def xpset_cmd(self, ctx: commands.Context, member: discord.Member, total: int):
        new = set_total_xp(ctx.guild.id, member.id, total)
        await ctx.send(f"🛠️ Set **{member.display_name}** total XP to **{new}**.")

    @commands.command(name="xpsave")
    @_is_admin()
    async def xpsave_cmd(self, ctx: commands.Context):
        xp_save(self.file_path)
        await ctx.message.add_reaction("💾")