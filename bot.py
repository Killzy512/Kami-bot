# bot.py — KamiBot + Music + Cards/XP/Duel/Gamble/General + DM-friendly Help + KamiAdventure data_dir
from __future__ import annotations

import asyncio, time, datetime
from typing import Dict, List, Optional

import discord
from discord.ext import commands, tasks
import wavelink

from cogs.cards_cog import Cards
from cogs.xp import XP
from cogs.duel import Duel
from cogs.gamble import Gamble
from cogs.funpack import KamiFunPack
from cogs.kami_adventure import KamiAdventure
from cogs.bank import (
    set_path as bank_set_path,
    bank_load, bank_save,
    get_balance, add_balance,
    get_last_daily, set_last_daily,
)

# --- TOKEN LOADING (minimal & robust) ---
import os
from pathlib import Path

# If you use dotenv, this will load .env that sits next to bot.py
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    ENV_PATH = Path(__file__).with_name(".env")
    # override=True ensures the .env wins if something else is set
    load_dotenv(dotenv_path=ENV_PATH, override=True)
except Exception:
    # dotenv is optional; if not installed, you can set env via PowerShell instead
    pass

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set. "
        "Create a .env next to bot.py (DISCORD_TOKEN=...) or set the environment variable."
    )
# ----------------------------------------
HOST = "127.0.0.1"
PORT = 2333
PASSWORD = "youshallnotpass"

COMMAND_PREFIX = "!"
MAX_QUEUE_SIZE = 100

BANK_PATH = "bank.json"
DAILY_AMOUNT = 250
DAILY_COOLDOWN_SEC = 24 * 60 * 60

KAMI_DATA_DIR = "data/kami"  # per-guild JSONs will be stored here

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.reactions = True

# ---------- DM-friendly, KAMI-themed categorized Help (final) ----------
from typing import List, Dict
from collections import defaultdict
from discord.ext import commands
import discord

class KamiHelp(commands.MinimalHelpCommand):
    """
    - Groups by category (Cog-aware)
    - Expands group subcommands into individual lines
    - Custom order for KAMI subcommands
    - Robust prefix detection across discord.py variants
    - DM fallback for long outputs
    """

    THEME_COLOR = 0x00B3FF
    EMBED_TITLE = "📖 Kami’s Codex — All Commands"

    CATEGORY_ICONS = {
        "Kami Adventure": "🗺️",
        "Gamble": "🎲",
        "Music": "🎵",
        "Cards": "🃏",
        "Duel": "🥊",
        "Fun Pack": "🎉",
        "XP / Levels": "📈",
        "Bank": "🏦",
        "Admin": "🛠️",
        "General": "🧭",
    }
    CATEGORY_ORDER = [
        "Kami Adventure", "Gamble", "Music", "Cards", "Duel",
        "Fun Pack", "XP / Levels", "Bank", "General", "Admin"
    ]

    # preferred subcommand order for groups
    PREFERRED_SUBORDER: Dict[str, List[str]] = {
        "kami": [
            "register", "profile", "explore", "battle",
            "heal", "inventory", "equip", "unequip",
            "shop", "buy", "sell",
        ],
    }

    def __init__(self, *, dm_fallback: bool = True):
        super().__init__()
        self.dm_fallback = dm_fallback

    # --- robust prefix detection ---
    def _get_prefix(self) -> str:
        ctx = self.context
        if ctx is None:
            return "!"
        pref = getattr(ctx, "clean_prefix", None) or getattr(ctx, "prefix", None)
        if pref:
            return pref if isinstance(pref, str) else (pref[0] if isinstance(pref, (list, tuple)) and pref else "!")
        cp = getattr(ctx.bot, "command_prefix", "!")
        try:
            if callable(cp):
                val = cp(ctx.bot, getattr(ctx, "message", None))  # type: ignore
                if isinstance(val, str): return val
                if isinstance(val, (list, tuple)) and val: return val[0]
            elif isinstance(cp, (list, tuple)) and cp:
                return cp[0]
            elif isinstance(cp, str):
                return cp
        except Exception:
            pass
        return "!"

    # --- categorize by Cog -> friendly section ---
    def _category_of(self, cmd: commands.Command) -> str:
        cog = cmd.cog_name or ""
        name = cog.lower()
        if "kami" in name and "adventure" in name: return "Kami Adventure"
        if name == "gamble" or "roulette" in cmd.qualified_name: return "Gamble"
        if name == "music": return "Music"
        if "card" in name: return "Cards"
        if "duel" in name: return "Duel"
        if "funpack" in name or "fun" in name: return "Fun Pack"
        if name in ("xp", "levels", "level"): return "XP / Levels"
        if "bank" in name or "economy" in name: return "Bank"
        if "admin" in name or "owner" in name: return "Admin"
        return "General"

    # --- formatting helpers ---
    def _fmt_command(self, prefix: str, cmd: commands.Command) -> str:
        summary = cmd.help or cmd.description or "Command"
        return f"**{prefix}{cmd.qualified_name}** — {summary}"

    def _sorted_subs(self, group: commands.Group) -> List[commands.Command]:
        subs = [sc for sc in group.commands if not sc.hidden]
        key = group.qualified_name  # e.g., "kami"
        preferred = self.PREFERRED_SUBORDER.get(key)
        if not preferred:
            return sorted(subs, key=lambda c: c.qualified_name)
        order = {name: i for i, name in enumerate(preferred)}
        return sorted(subs, key=lambda c: (order.get(c.name, 999), c.name))

    def _add_category_fields(self, embed: discord.Embed, title: str, lines: List[str]):
        """Add lines as one or more fields; continuation has blank header (no '(2)')."""
        icon = self.CATEGORY_ICONS.get(title, "✨")
        if not lines:
            return
        field_name = f"{icon} {title}"
        chunk, size = [], 0
        for line in lines:
            if size + len(line) + 1 > 1000 and chunk:
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)
                field_name = "\u200b"  # continuation
                chunk, size = [], 0
            chunk.append(line); size += len(line) + 1
        if chunk:
            embed.add_field(name=field_name, value="\n".join(chunk), inline=False)

    async def _send_pages(self, embeds: List[discord.Embed]):
        dest = self.get_destination()
        try:
            if len(embeds) > 1 and self.dm_fallback:
                for i, e in enumerate(embeds, 1):
                    e.set_footer(text=f"Page {i}/{len(embeds)} • Kami Bot")
                    await self.context.author.send(embed=e)
                await dest.send("📬 Sent you the full help in DMs.")
            else:
                for i, e in enumerate(embeds, 1):
                    if len(embeds) > 1:
                        e.set_footer(text=f"Page {i}/{len(embeds)} • Kami Bot")
                    await dest.send(embed=e)
        except Exception:
            for i, e in enumerate(embeds, 1):
                if len(embeds) > 1:
                    e.set_footer(text=f"Page {i}/{len(embeds)} • Kami Bot")
                await dest.send(embed=e)

    # --- overrides ---
    async def send_bot_help(self, mapping):
        prefix = self._get_prefix()
        bot = self.context.bot

        # Build categorized lines; expand groups using custom order if defined
        cats: Dict[str, List[str]] = defaultdict(list)
        for cmd in sorted(bot.commands, key=lambda c: c.qualified_name):
            if cmd.hidden:
                continue
            cat = self._category_of(cmd)
            if isinstance(cmd, commands.Group):
                subs = self._sorted_subs(cmd)
                if subs:
                    for sc in subs:
                        cats[cat].append(self._fmt_command(prefix, sc))
                else:
                    cats[cat].append(self._fmt_command(prefix, cmd))
            else:
                cats[cat].append(self._fmt_command(prefix, cmd))

        # Assemble paged embeds
        pages: List[discord.Embed] = []
        current = discord.Embed(
            title=self.EMBED_TITLE,
            description=f"Prefix: **{prefix}**  •  Use `{prefix}help <command>` for details.\n"
                        f"Tip: `{prefix}kami` opens the adventure help directly.",
            color=self.THEME_COLOR,
        )
        fields_used = 0
        for cat in self.CATEGORY_ORDER:
            lines = cats.get(cat, [])
            if not lines:
                continue
            if fields_used >= 12:
                pages.append(current)
                current = discord.Embed(title=self.EMBED_TITLE, color=self.THEME_COLOR)
                fields_used = 0
            self._add_category_fields(current, cat, lines)
            fields_used = len(current.fields)

        if fields_used == 0:
            current.description = "No commands available."
        pages.append(current)
        await self._send_pages(pages)

    async def send_group_help(self, group: commands.Group):
        prefix = self._get_prefix()
        embed = discord.Embed(
            title=f"📂 {group.qualified_name} — Subcommands",
            description=(group.help or group.description or "Command group"),
            color=self.THEME_COLOR,
        )
        for sc in self._sorted_subs(group):
            embed.add_field(
                name=f"{prefix}{sc.qualified_name} {sc.signature}".strip(),
                value=sc.help or sc.description or "No description.",
                inline=False,
            )
        await self.get_destination().send(embed=embed)


# ---------- autosave ----------
@tasks.loop(minutes=5)
async def autosave():
    try:
        bank_save()
    except Exception as e:
        print(f"[autosave] bank_save failed: {e!r}")
    xp_cog = bot.get_cog("XP")
    if xp_cog and hasattr(xp_cog, "save"):
        try:
            await xp_cog.save()  # type: ignore
        except Exception as e:
            print(f"[autosave] xp.save() failed: {e!r}")

@autosave.before_loop
async def _wait_ready():
    await bot.wait_until_ready()

# ---------- Music (unchanged core) ----------
class Music(commands.Cog, name="Music"):
    """🎵 Kami Music with fallback for reliability."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queues: Dict[int, List[wavelink.Playable]] = {}
        self.fallbacks: Dict[int, List[wavelink.Playable]] = {}
        self.last_channels: Dict[int, discord.TextChannel] = {}

    def _q(self, gid: int) -> List[wavelink.Playable]:
        return self.queues.setdefault(gid, [])

    async def _ensure_connected(self, ctx) -> Optional[wavelink.Player]:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("🔊 Join a voice channel first so **Kami DJ** knows where to spin!")
            return None
        if not isinstance(ctx.voice_client, wavelink.Player):
            await ctx.author.voice.channel.connect(cls=wavelink.Player)
        self.last_channels[ctx.guild.id] = ctx.channel
        return ctx.voice_client  # type: ignore

    @commands.command(help="Join your voice channel.")
    async def join(self, ctx):
        vc = await self._ensure_connected(ctx)
        if vc:
            await ctx.send("🎧 **Kami DJ** connected.")

    @commands.command(help="Leave voice channel.")
    async def leave(self, ctx):
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.disconnect()
            await ctx.send("👋 **Kami DJ** out!")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(help="Play by URL or search. Keeps extra results as fallback if first fails.")
    async def play(self, ctx, *, query: str):
        vc = await self._ensure_connected(ctx);  # ... rest identical to your version
        if not vc:
            return
        if query.startswith(("https://open.spotify.com/", "http://open.spotify.com/")):
            return await ctx.send("⚠️ Spotify links aren’t supported. Use YouTube or search.")
        is_url = query.startswith(("http://", "https://"))
        try:
            if is_url:
                results = await wavelink.Playable.search(query)
            else:
                yt_src = getattr(wavelink.TrackSource, "YouTube", None) or getattr(wavelink.TrackSource, "YOUTUBE", None)
                results = await wavelink.Playable.search(query, source=yt_src) if yt_src else await wavelink.Playable.search(query)
            tracks = list(results) if isinstance(results, (list, tuple)) else [results]
            if not tracks:
                return await ctx.send("🔍 No tracks found.")
            best = tracks.pop(0)
            self.fallbacks[ctx.guild.id] = tracks
            q = self._q(ctx.guild.id)
            if not getattr(vc, "playing", False) and not getattr(vc, "paused", False):
                await vc.play(best)
                await ctx.send(f"▶️ Now playing: **{getattr(best, 'title', 'Unknown Title')}**")
            else:
                if len(q) >= MAX_QUEUE_SIZE:
                    return await ctx.send(f"📦 Queue is full (max {MAX_QUEUE_SIZE}).")
                q.append(best)
                await ctx.send(f"➕ Queued: **{getattr(best, 'title', 'Unknown Title')}**")
        except Exception as e:
            await ctx.send(f"❌ Search error: {e}")

    @commands.command(aliases=["q"], help="Show upcoming queue.")
    async def queue(self, ctx):
        q = self._q(ctx.guild.id)
        if not q:
            return await ctx.send("📭 Queue is empty.")
        lines = [f"{i}. {getattr(t, 'title', 'Unknown Title')}" for i, t in enumerate(q[:10], start=1)]
        extra = f"\n…and {len(q)-10} more." if len(q) > 10 else ""
        await ctx.send("**🎼 Upcoming:**\n" + "\n".join(lines) + extra)

    @commands.command(aliases=["np"], help="Show the current track.")
    async def now(self, ctx):
        vc = ctx.voice_client
        if not isinstance(vc, wavelink.Player) or not vc.current:
            return await ctx.send("⏹️ Nothing is playing.")
        await ctx.send(f"🎶 Now playing: **{getattr(vc.current, 'title', 'Unknown Title')}**")

    @commands.command(help="Pause playback.")
    async def pause(self, ctx):
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.pause()
            await ctx.send("⏸️ Paused.")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(help="Resume playback.")
    async def resume(self, ctx):
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(help="Stop playback.")
    async def stop(self, ctx):
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.stop()
            await ctx.send("⏹️ Stopped.")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(name="skip", aliases=["next"], help="Skip the current track.")
    async def skip_song(self, ctx):
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(help="Show Lavalink node status.")
    async def node(self, ctx):
        pool = getattr(wavelink, "Pool", None)
        if pool and pool.nodes:
            n = list(pool.nodes.values())[0]
            return await ctx.send(f"🛰️ Node status: **{n.status.name}**")
        await ctx.send("❓ No nodes in pool.")

    @commands.command(help="Force reconnect to Lavalink.")
    async def reconnect(self, ctx):
        pool = getattr(wavelink, "Pool", None)
        if pool:
            for n in list(pool.nodes.values()):
                await n.disconnect()
        asyncio.create_task(self.bot._connect_lavalink_retry())
        await ctx.send("🔁 Reconnecting to Lavalink…")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, event):
        player: Optional[wavelink.Player] = getattr(event, "player", None)
        if player:
            gid = player.guild.id
            alts = self.fallbacks.get(gid) or []
            if alts:
                nxt = alts.pop(0)
                self.fallbacks[gid] = alts
                try:
                    await player.play(nxt)
                    ch = self.last_channels.get(gid)
                    if ch:
                        await ch.send(f"⚠️ Track failed; trying **{getattr(nxt, 'title', 'next result')}**…")
                    return
                except Exception:
                    pass
            q = self._q(gid)
            if q:
                await player.play(q.pop(0))

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, event):
        player: wavelink.Player = event.player  # type: ignore
        q = self._q(player.guild.id)
        if q:
            await player.play(q.pop(0))

# ---------- General (daily/balance) ----------
def _fmt_delta(seconds: int) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60); h, m = divmod(m, 60); d, h = divmod(h, 24)
    parts = []
    if d: parts.append(f"{d}d")
    if h or d: parts.append(f"{h}h")
    if m or h or d: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

class General(commands.Cog, name="General"):
    @commands.command(name="balance", aliases=["bal"])
    async def balance_cmd(self, ctx, member: Optional[discord.Member] = None):
        member = member or ctx.author
        coins = get_balance(ctx.guild.id, member.id)
        await ctx.send(f"💰 **{member.display_name}** has **{coins} KamiCoins**.")

    @commands.command(name="daily")
    async def daily_cmd(self, ctx):
        gid, uid = ctx.guild.id, ctx.author.id
        now = int(time.time())
        last = get_last_daily(gid, uid) or 0
        elapsed = now - last
        remaining = DAILY_COOLDOWN_SEC - elapsed
        if last and remaining > 0:
            rel = discord.utils.format_dt(datetime.datetime.fromtimestamp(now + remaining), style="R")
            return await ctx.send(f"⏳ Already claimed. Come back {rel} (**{_fmt_delta(remaining)}**).")
        new_bal = add_balance(gid, uid, DAILY_AMOUNT)
        set_last_daily(gid, uid, now)
        rel = discord.utils.format_dt(datetime.datetime.fromtimestamp(now + DAILY_COOLDOWN_SEC), style="R")
        await ctx.send(f"✅ Daily claimed! +{DAILY_AMOUNT} KamiCoins. New balance: **{new_bal}**. Next claim {rel}.")

# ---------- Bot subclass ----------
class Bot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # make data_dir available to the Adventure cog setup()
        self.kami_data_dir = KAMI_DATA_DIR

    async def setup_hook(self):
        bank_set_path(BANK_PATH)
        bank_load()
        await self.add_cog(Cards(self, bank_path=BANK_PATH))
        await self.add_cog(XP(self))
        await self.add_cog(Duel(self))
        await self.add_cog(KamiFunPack(self))
        await self.add_cog(Gamble(self, bank_path=BANK_PATH))
        await self.add_cog(Music(self))
        await self.add_cog(General())
        await self.add_cog(KamiAdventure(self, data_dir=self.kami_data_dir))
        if not autosave.is_running():
            autosave.start()
        asyncio.create_task(self._connect_lavalink_retry())

    async def _connect_lavalink_retry(self):
        tries = 0
        while True:
            try:
                if getattr(wavelink, "Pool", None) and wavelink.Pool.nodes:
                    print("[Wavelink] already connected")
                    return
                tries += 1
                print(f"[Wavelink] connecting to {HOST}:{PORT} (try {tries})")
                node = wavelink.Node(uri=f"http://{HOST}:{PORT}", password=PASSWORD)
                await wavelink.Pool.connect(nodes=[node], client=self)
                print("[Wavelink] connect call returned (waiting for READY event)")
                return
            except Exception as e:
                print(f"[Wavelink] connect failed: {e!r}; retrying in 2s")
                await asyncio.sleep(2)

# Plug in custom help (shows all subcommands; DM fallback)
bot = Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=KamiHelp(dm_fallback=True))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

@bot.listen()
async def on_wavelink_node_ready(node):
    print(f"[Wavelink] node READY: {getattr(node, 'identifier', 'main')}")

if __name__ == "__main__":
    if TOKEN == "PASTE_YOUR_DISCORD_BOT_TOKEN":
        raise SystemExit("Paste your bot token into bot.py.")
    bot.run(TOKEN)
