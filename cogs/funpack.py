# Kami Fun Pack — Modified 2025-08-10
# (No timeouts + 24h WYR reward limit + Light Kami/One Piece flavor + Slash & Prefix Commands)
#
# Color legend:
# - Trivia = Indigo (0x5865F2)
# - WYR = Emerald (0x2ECC71)
# - Poll = Gold (0xF1C40F)
# - RPS/TTT = Grey (0x99AAB5)
#
# Footers include version and 🚢 Kami ship for quick verification in-chat.

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

# --- KAMI TRIVIA imports ---
import re
from dataclasses import dataclass, field
from typing import Dict, Set

# --- Disc Imports ---
import discord
from discord import app_commands
from discord.ext import commands, tasks

# ---------- Optional KamiCoins integration ----------
try:
    from cogs.bank import add_balance  # type: ignore
    KAMI_BANK = True
except Exception:
    KAMI_BANK = False

# ---------- Version / constants ----------
FUNPACK_VERSION = "2025-08-10"
SHIP = "🚢"
TZ = ZoneInfo("America/Chicago")
FUNPACK_DATA = "funpack_data.json"

# Trivia
TRIVIA_REWARDS = [250, 150, 75]
TRIVIA_COLOR = 0x5865F2
TRIVIA_USER_COOLDOWN_S = 60  # ⏱ per-user cooldown to start a new trivia round

# WYR
WYR_REWARD_PER_VOTE = 20
WYR_COLOR = 0x2ECC71
WYR_REWARD_CUTOFF_SEC = 24 * 60 * 60  # 24h

# Poll / misc
POLL_COLOR = 0xF1C40F
MISC_COLOR = 0x99AAB5

KAMI_COIN_NAME = "KamiCoins"

# Default auto hours (kept from your original behavior)
TRIVIA_DEFAULT_HOURS = [10, 14, 18, 21]
WYR_DEFAULT_HOURS = [12, 20]


# ====================== Persistence helpers ======================
def _load_store() -> Dict:
    try:
        with open(FUNPACK_DATA, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_store(store: Dict) -> None:
    with open(FUNPACK_DATA, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)

def _now_local() -> datetime:
    return datetime.now(TZ)

def _today_key() -> str:
    return _now_local().date().isoformat()

def _week_id(dt: Optional[datetime] = None) -> str:
    dt = dt or _now_local()
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"

def _is_sunday_midnight(dt: Optional[datetime] = None) -> bool:
    dt = dt or _now_local()
    return dt.weekday() == 6 and dt.hour == 0 and dt.minute == 0


# ====================== Trivia ======================
@dataclass
class TriviaQ:
    q: str
    choices: List[str]   # 4 choices
    correct_index: int   # 0..3

DEFAULT_TRIVIA: List[TriviaQ] = [
    TriviaQ("What does HTTP stand for?",
            ["HyperText Transfer Protocol", "High Transfer Text Protocol", "HyperText Transit Pipeline", "Host Transfer Type Protocol"], 0),
    TriviaQ("Which keyword creates a function in Python?",
            ["func", "def", "lambda", "fn"], 1),
    TriviaQ("Which planet is known as the Red Planet?",
            ["Venus", "Mars", "Jupiter", "Mercury"], 1),
    TriviaQ("Which Big‑O is best (fastest)?",
            ["O(n^2)", "O(n log n)", "O(1)", "O(n^3)"], 2),
    TriviaQ("Discord was first released in which year?",
            ["2013", "2015", "2017", "2019"], 1),
]

# ───────────────────────── Persistent Trivia View ─────────────────────────
# Single, stateless view that handles ALL trivia messages using stable custom_ids.
# Round-specific state (question, choices, winners, answered) is stored by message_id.
class PersistentTriviaView(discord.ui.View):
    def __init__(self, cog: "KamiFunPack"):
        super().__init__(timeout=None)  # persistent
        self.cog = cog

    # Four stable buttons (A/B/C/D)
    @discord.ui.button(label="A", style=discord.ButtonStyle.secondary, custom_id="trivia:A")
    async def btn_a(self, i: discord.Interaction, b: discord.ui.Button):
        await self.cog._trivia_button(i, 0)

    @discord.ui.button(label="B", style=discord.ButtonStyle.secondary, custom_id="trivia:B")
    async def btn_b(self, i: discord.Interaction, b: discord.ui.Button):
        await self.cog._trivia_button(i, 1)

    @discord.ui.button(label="C", style=discord.ButtonStyle.secondary, custom_id="trivia:C")
    async def btn_c(self, i: discord.Interaction, b: discord.ui.Button):
        await self.cog._trivia_button(i, 2)

    @discord.ui.button(label="D", style=discord.ButtonStyle.secondary, custom_id="trivia:D")
    async def btn_d(self, i: discord.Interaction, b: discord.ui.Button):
        await self.cog._trivia_button(i, 3)


# ====== KAMI TRIVIA (drop-in) ======

@dataclass
class _KamiTriviaSession:
    channel_id: int
    question: str
    answers: Set[str]          # normalized acceptable answers
    winners_needed: int = 3
    winners: Set[int] = field(default_factory=set)
    active: bool = True

def _kami_norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[`~!@#$%^&*()\-_=+$begin:math:display$$end:math:display${}\\|;:'\",.<>/?]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _kami_plural(n: int) -> str:
    return "left" if n != 1 else "left"

def _kami_flair(left: int) -> str:
    if left > 1:
        return "🌸"
    if left == 1:
        return "🔮"
    return "🏁"

# storage: channel_id -> session
self_trivia_sessions: Dict[int, _KamiTriviaSession] = None  # set in __init__

# ====== KAMI TRIVIA (drop-in with timeout + end announcement) ======

@dataclass
class _KamiTriviaSession:
    channel_id: int
    question: str
    answers: Set[str]                 # normalized acceptable answers
    winners_needed: int = 3
    winners: Set[int] = field(default_factory=set)
    active: bool = True
    timer_task: Optional[asyncio.Task] = None

def _kt_norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[`~!@#$%^&*()\-_=+$begin:math:display$$end:math:display${}\\|;:'\",.<>/?]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _kt_flair(left: int) -> str:
    if left > 1:
        return "🌸"
    if left == 1:
        return "🔮"
    return "🏁"

async def _kt_finish(self, channel: discord.TextChannel, sess: _KamiTriviaSession, reason: str):
    """End a round (time/winners). Announce partial winners if any."""
    if not sess.active:
        return
    sess.active = False
    # stop timer if still running
    if sess.timer_task and not sess.timer_task.done():
        sess.timer_task.cancel()
    left = max(0, sess.winners_needed - len(sess.winners))
    winners_order = ", ".join(f"<@{uid}>" for uid in sess.winners) or "—"
    if left > 0:
        await channel.send(
            f"⏳ **Kami Verdict:** Time’s up — only **{len(sess.winners)}** seeker(s) solved it.\n"
            f"Winners so far: {winners_order}\n"
            f"Unclaimed spots: **{left}**\n"
            f"Type `!trivia start ...` for the next challenge!"
        )
    else:
        await channel.send(
            f"🏆 **Kami Verdict:** Round complete! Winners: {winners_order}\n"
            f"Type `!trivia start ...` for another."
        )

@commands.group(name="trivia", invoke_without_command=True)
async def trivia(self, ctx: commands.Context):
    """Kami Trivia:
    `!trivia start [winners] [seconds] | <question> | <ans1; ans2; ...>`
    e.g. `!trivia start 3 45 | Capital of Japan? | Tokyo`
    """
    await ctx.send(
        "🧠 **Kami Trivia**\n"
        "Start: `!trivia start [winners] [seconds] | <question> | <answer1; answer2; ...>`\n"
        "Stop:  `!trivia stop`\n"
        "Status:`!trivia status`"
    )

@trivia.command(name="start")
@commands.has_permissions(manage_messages=True)
async def trivia_start(self, ctx: commands.Context, *, spec: str):
    """
    Format:
      !trivia start [winners] [seconds] | <question> | <ans1; ans2; ...>
    winners default=3, seconds default=45
    """
    # init storage if not yet
    if self.self_trivia_sessions is None:
        self.self_trivia_sessions = {}

    parts = [p.strip() for p in spec.split("|")]
    if len(parts) != 3:
        return await ctx.reply(
            "❌ Use: `!trivia start [winners] [seconds] | <question> | <ans1; ans2; ...>`"
        )

    # Parse left side (may contain winners + seconds OR just one/both omitted)
    left_side = parts[0].split()
    winners_needed = 3
    seconds = 45
    if len(left_side) >= 1 and left_side[0].isdigit():
        winners_needed = int(left_side[0])
    if len(left_side) >= 2 and left_side[1].isdigit():
        seconds = int(left_side[1])

    question = parts[1]
    answers = {_kt_norm(a) for a in parts[2].split(";") if a.strip()}
    if not question or not answers:
        return await ctx.reply("❌ Need a question and at least one answer.")

    if (sess := self.self_trivia_sessions.get(ctx.channel.id)) and sess.active:
        return await ctx.reply("⚠️ A trivia round is already running here. Use `!trivia stop`.")

    sess = _KamiTriviaSession(
        channel_id=ctx.channel.id,
        question=question,
        answers=answers,
        winners_needed=max(1, winners_needed),
    )
    self.self_trivia_sessions[ctx.channel.id] = sess

    await ctx.send(
        f"🌸 **Kami Trivia Begins!**\n"
        f"**Question:** {question}\n"
        f"First **{sess.winners_needed}** correct answers win.\n"
        f"⏱️ Time limit: **{seconds}s** — type your answer now!"
    )

    # start timer
    async def timer():
        try:
            await asyncio.sleep(max(5, seconds))
            ch = ctx.channel
            if isinstance(ch, discord.TextChannel):
                await _kt_finish(self, ch, sess, reason="time")
        except asyncio.CancelledError:
            pass  # normal when round ends early

    sess.timer_task = asyncio.create_task(timer())

@trivia.command(name="status")
async def trivia_status(self, ctx: commands.Context):
    if self.self_trivia_sessions is None:
        self.self_trivia_sessions = {}
    sess = self.self_trivia_sessions.get(ctx.channel.id)
    if not sess or not sess.active:
        return await ctx.reply("No active trivia in this channel.")
    left = max(0, sess.winners_needed - len(sess.winners))
    winners_list = ", ".join(f"<@{uid}>" for uid in sess.winners) or "—"
    await ctx.send(
        f"🔎 **Status** — `{left}` left to win\n"
        f"Question: {sess.question}\n"
        f"Winners so far: {winners_list}"
    )

@trivia.command(name="stop")
@commands.has_permissions(manage_messages=True)
async def trivia_stop(self, ctx: commands.Context):
    if self.self_trivia_sessions is None:
        self.self_trivia_sessions = {}
    sess = self.self_trivia_sessions.get(ctx.channel.id)
    if not sess or not sess.active:
        return await ctx.reply("No active trivia here.")
    await _kt_finish(self, ctx.channel, sess, reason="stopped")

@commands.Cog.listener("on_message")
async def _kami_trivia_on_message(self, message: discord.Message):
    if message.author.bot or not message.guild:
        return
    if self.self_trivia_sessions is None:
        return
    sess = self.self_trivia_sessions.get(message.channel.id)
    if not sess or not sess.active:
        return

    guess = _kt_norm(message.content)
    if not guess:
        return
    if message.author.id in sess.winners:
        return

    if guess in sess.answers:
        sess.winners.add(message.author.id)
        left = max(0, sess.winners_needed - len(sess.winners))
        await message.channel.send(
            f"{_kt_flair(left)} **{message.author.display_name}** answered correctly! "
            f"**{left}** left…"
        )
        if left == 0:
            # all winners found — finish early
            ch = message.channel
            if isinstance(ch, discord.TextChannel):
                await _kt_finish(self, ch, sess, reason="completed")
# ====== end KAMI TRIVIA ======

# ====================== WYR ======================
@dataclass
class WYRQ:
    a: str
    b: str

DEFAULT_WYR: List[WYRQ] = [
    WYRQ("Have the ability to fly", "Be invisible"),
    WYRQ("Only use a flip phone", "Only use dial‑up internet"),
    WYRQ("Free pizza forever", "Free tacos forever"),
]

class WYRView(discord.ui.View):
    """One WYR round; no timeout; first vote per user rewards only within 24h of post."""
    def __init__(self, cog: "KamiFunPack", a: str, b: str, guild: discord.Guild):
        super().__init__(timeout=None)  # never expire
        self.cog = cog
        self.opt_a = a
        self.opt_b = b
        self.guild = guild
        self.votes_a: Set[int] = set()
        self.votes_b: Set[int] = set()
        self.rewarded: Set[int] = set()
        self.start_ts = discord.utils.utcnow().timestamp()

    def tally(self) -> Tuple[int, int]:
        return len(self.votes_a), len(self.votes_b)

    async def update_labels(self):
        a_cnt, b_cnt = self.tally()
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                if c.custom_id == "wyr_a":
                    c.label = f"🅰️ {self.opt_a} ({a_cnt})"
                elif c.custom_id == "wyr_b":
                    c.label = f"🅱️ {self.opt_b} ({b_cnt})"

    async def _reward_once(self, uid: int, interaction: discord.Interaction):
        now_ts = discord.utils.utcnow().timestamp()
        if (now_ts - self.start_ts) > WYR_REWARD_CUTOFF_SEC:
            return await interaction.response.send_message(
                "⚓ Law says you’re too late for the Kami reward, but your vote still counts.",
                ephemeral=True
            )
        if uid in self.rewarded:
            return await interaction.response.send_message(
                "☠️ Luffy grins — you’ve already picked your side!",
                ephemeral=True
            )
        if KAMI_BANK:
            try:
                add_balance(self.guild.id, uid, WYR_REWARD_PER_VOTE)
                self.rewarded.add(uid)
            except Exception:
                pass

    @discord.ui.button(label="🅰️", style=discord.ButtonStyle.primary, custom_id="wyr_a")
    async def wyr_a(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user is None: return
        if i.user.id in self.votes_a:
            self.votes_a.remove(i.user.id)
        else:
            self.votes_a.add(i.user.id)
            self.votes_b.discard(i.user.id)
            await self._reward_once(i.user.id, i)
        await self.update_labels()
        await i.response.edit_message(view=self)

    @discord.ui.button(label="🅱️", style=discord.ButtonStyle.success, custom_id="wyr_b")
    async def wyr_b(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user is None: return
        if i.user.id in self.votes_b:
            self.votes_b.remove(i.user.id)
        else:
            self.votes_b.add(i.user.id)
            self.votes_a.discard(i.user.id)
            await self._reward_once(i.user.id, i)
        await self.update_labels()
        await i.response.edit_message(view=self)


# ====================== Poll ======================
class PollView(discord.ui.View):
    def __init__(self, options: List[str]):
        super().__init__(timeout=None)  # keep clickable
        self.options = options
        self.votes: Dict[int, int] = {}
        styles = [discord.ButtonStyle.primary, discord.ButtonStyle.success,
                  discord.ButtonStyle.secondary, discord.ButtonStyle.danger,
                  discord.ButtonStyle.primary]
        for i, opt in enumerate(options[:5]):
            self.add_item(PollButton(i, opt.strip(), styles[i], self))

    def counts(self) -> List[int]:
        cnt = [0] * len(self.options)
        for _, idx in self.votes.items():
            if 0 <= idx < len(cnt):
                cnt[idx] += 1
        return cnt

    async def refresh_labels(self):
        cnt = self.counts()
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                idx = int(item.custom_id.split(":")[1])
                base = self.options[idx][:60]
                item.label = f"{base} ({cnt[idx]})"

class PollButton(discord.ui.Button):
    def __init__(self, idx: int, label_txt: str, style: discord.ButtonStyle, view: PollView):
        super().__init__(label=label_txt, style=style, custom_id=f"poll:{idx}")
        self.idx = idx
        self.pview = view

    async def callback(self, i: discord.Interaction):
        if i.user is None: return
        self.pview.votes[i.user.id] = self.idx
        await self.pview.refresh_labels()
        await i.response.edit_message(view=self.pview)


# ====================== RPS ======================
RPS_CHOICES = ["🪨 Rock", "📄 Paper", "✂️ Scissors"]
RPS_WINS = {0: 2, 1: 0, 2: 1}

class RPSView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=None)
        self.author_id = author_id

    @discord.ui.button(label="🪨 Rock", style=discord.ButtonStyle.secondary)
    async def r(self, i: discord.Interaction, b: discord.ui.Button): await self._play(i, 0)

    @discord.ui.button(label="📄 Paper", style=discord.ButtonStyle.secondary)
    async def p(self, i: discord.Interaction, b: discord.ui.Button): await self._play(i, 1)

    @discord.ui.button(label="✂️ Scissors", style=discord.ButtonStyle.secondary)
    async def s(self, i: discord.Interaction, b: discord.ui.Button): await self._play(i, 2)

    async def _play(self, i: discord.Interaction, pick: int):
        if not i.user or i.user.id != self.author_id:
            return await i.response.send_message("Only the challenger can play this game.", ephemeral=True)
        bot_pick = random.randint(0, 2)
        result = "Draw!" if pick == bot_pick else ("You win! 🎉" if RPS_WINS[pick] == bot_pick else "You lose! 😈")
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await i.response.edit_message(content=f"**RPS** — You: {RPS_CHOICES[pick]} | Kami: {RPS_CHOICES[bot_pick]}\n**{result}**", view=self)


# ====================== Tic‑Tac‑Toe ======================
WIN_LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,4,6),(2,5,8),(0,4,8)]

class TTTView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=None)
        self.players=[p1,p2]; self.marks=["❌","⭕"]; self.turn=0; self.board=[" "]*9
        for i in range(9): self.add_item(TTTButton(i, i//3, i%3, self))

    def status_text(self)->str: return f"{self.marks[self.turn]} {self.players[self.turn].mention}'s turn"

    def check_winner(self)->Optional[int]:
        for a,b,c in WIN_LINES:
            if self.board[a]!=" " and self.board[a]==self.board[b]==self.board[c]:
                return 0 if self.board[a]==self.marks[0] else 1
        if all(cell!=" " for cell in self.board): return -1
        return None

class TTTButton(discord.ui.Button):
    def __init__(self, idx:int,row:int,col:int,view:TTTView):
        super().__init__(style=discord.ButtonStyle.secondary,label=" ",row=row)
        self.idx=idx; self.tview=view
    async def callback(self, i: discord.Interaction):
        if not i.user: return
        if i.user.id != self.tview.players[self.tview.turn].id:
            return await i.response.send_message("Not your turn.", ephemeral=True)
        if self.tview.board[self.idx]!=" ":
            return await i.response.send_message("That spot is already taken.", ephemeral=True)
        mark=self.tview.marks[self.tview.turn]; self.tview.board[self.idx]=mark
        self.label=mark; self.disabled=True
        w=self.tview.check_winner()
        if w is None:
            self.tview.turn^=1
            await i.response.edit_message(content=self.tview.status_text(), view=self.tview)
        else:
            for c in self.tview.children:
                if isinstance(c, discord.ui.Button): c.disabled=True
            content="Cat’s game! It’s a draw. 🐱" if w==-1 else f"{self.tview.marks[w]} **{self.tview.players[w].display_name}** wins! 🎉"
            await i.response.edit_message(content=content, view=self.tview)


# ====================== Main Cog ======================
class KamiFunPack(commands.Cog, name="Kami Fun Pack"):
    """Interactive Kami bundle: Trivia, Would‑You‑Rather, Polls, RPS, Tic‑Tac‑Toe. Light Kami/One Piece flavor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._synced = False  # global slash sync guard
        self.store = _load_store()
        self.self_trivia_sessions = {}

        # bootstrap defaults
        self.store.setdefault("trivia_bank", [asdict(q) for q in DEFAULT_TRIVIA])
        self.store.setdefault("wyr_bank", [asdict(q) for q in DEFAULT_WYR])

        # guild-scoped settings
        self.store.setdefault("trivia_target", {})      # gid -> channel_id
        self.store.setdefault("trivia_hours", {})       # gid -> [h1,h2,h3,h4]
        self.store.setdefault("trivia_today", {})       # gid -> {"date":"YYYY-MM-DD","hours_posted":[int,...]}
        self.store.setdefault("trivia_scores", {})      # gid -> {"week_id": "...", "users": {uid: points}}
        self.store.setdefault("trivia_role", {})        # gid -> role_id
        self.store.setdefault("trivia_weekly_done", {}) # gid -> "YYYY-MM-DD" last weekly crown
        self.store.setdefault("active_trivia", {})      # message_id(str) -> round data

        self.store.setdefault("wyr_target", {})         # gid -> channel_id
        self.store.setdefault("wyr_hours", {})          # gid -> [h1,h2]
        self.store.setdefault("wyr_today", {})          # gid -> {"date":"YYYY-MM-DD","hours_posted":[int,...]}

        _save_store(self.store)

        # in-memory helpers
        self._round_locks: Dict[int, asyncio.Lock] = {}
        self._trivia_user_cooldown: Dict[int, float] = {}  # uid -> last start ts

        # loops
        self._trivia_loop.start()
        self._weekly_loop.start()
        self._wyr_loop.start()

    # ---------- global slash sync once + register persistent view ----------
    @commands.Cog.listener()
    async def on_ready(self):
        if not self._synced:
            try:
                # Register a single persistent view handling all trivia messages
                self.bot.add_view(PersistentTriviaView(self))
            except Exception as e:
                print(f"[KamiFunPack] add_view failed: {e!r}")
            try:
                await self.bot.tree.sync()  # global sync
            except Exception as e:
                print(f"[KamiFunPack] Global tree sync failed: {e!r}")
            self._synced = True

    # ---------- convenience getters/setters ----------
    def _bank_trivia(self) -> List[TriviaQ]:
        return [TriviaQ(**d) for d in self.store.get("trivia_bank", [])]

    def _set_bank_trivia(self, items: List[TriviaQ]) -> None:
        self.store["trivia_bank"] = [asdict(q) for q in items]; _save_store(self.store)

    def _bank_wyr(self) -> List[WYRQ]:
        return [WYRQ(**d) for d in self.store.get("wyr_bank", [])]

    def _set_bank_wyr(self, items: List[WYRQ]) -> None:
        self.store["wyr_bank"] = [asdict(q) for q in items]; _save_store(self.store)

    def _guild_hours_trivia(self, gid: int) -> List[int]:
        hrs = self.store["trivia_hours"].get(str(gid))
        if isinstance(hrs, list) and len(hrs) == 4:
            return [int(h) for h in hrs]
        return TRIVIA_DEFAULT_HOURS

    def _set_guild_hours_trivia(self, gid: int, hours: List[int]) -> None:
        self.store["trivia_hours"][str(gid)] = hours; _save_store(self.store)

    def _guild_hours_wyr(self, gid: int) -> List[int]:
        hrs = self.store["wyr_hours"].get(str(gid))
        if isinstance(hrs, list) and len(hrs) == 2:
            return [int(h) for h in hrs]
        return WYR_DEFAULT_HOURS

    def _set_guild_hours_wyr(self, gid: int, hours: List[int]) -> None:
        self.store["wyr_hours"][str(gid)] = hours; _save_store(self.store)

    def _target_trivia(self, gid: int) -> Optional[int]:
        v = self.store["trivia_target"].get(str(gid))
        return int(v) if v else None

    def _set_target_trivia(self, gid: int, cid: int) -> None:
        self.store["trivia_target"][str(gid)] = int(cid); _save_store(self.store)

    def _target_wyr(self, gid: int) -> Optional[int]:
        v = self.store["wyr_target"].get(str(gid))
        return int(v) if v else None

    def _set_target_wyr(self, gid: int, cid: int) -> None:
        self.store["wyr_target"][str(gid)] = int(cid); _save_store(self.store)

    def _today_tracker(self, gid: int, key: str) -> Dict:
        t = self.store[key].get(str(gid))
        today = _today_key()
        if not t or t.get("date") != today:
            t = {"date": today, "hours_posted": []}
            self.store[key][str(gid)] = t
            _save_store(self.store)
        return t

    def _scores(self, gid: int) -> Dict:
        s = self.store["trivia_scores"].get(str(gid))
        this_week = _week_id()
        if not s or s.get("week_id") != this_week:
            s = {"week_id": this_week, "users": {}}
            self.store["trivia_scores"][str(gid)] = s
            _save_store(self.store)
        return s

    def _add_weekly_score(self, gid: int, uid: int, points: int) -> None:
        s = self._scores(gid)
        users = s["users"]
        users[str(uid)] = int(users.get(str(uid), 0)) + int(points)
        _save_store(self.store)

    # ================== Trivia loops ==================
    @tasks.loop(seconds=30)
    async def _trivia_loop(self):
        await self.bot.wait_until_ready()
        now = _now_local()
        for guild in list(self.bot.guilds):
            target_id = self._target_trivia(guild.id)
            if not target_id:
                continue
            tracker = self._today_tracker(guild.id, "trivia_today")
            hours_needed = self._guild_hours_trivia(guild.id)
            if now.minute != 0 or now.hour not in hours_needed or now.hour in tracker["hours_posted"]:
                continue
            channel = guild.get_channel(target_id) or await self.bot.fetch_channel(target_id)
            if not isinstance(channel, discord.TextChannel):
                continue
            ok = await self._post_trivia_round(channel, auto=True)
            if ok:
                tracker["hours_posted"].append(now.hour)
                _save_store(self.store)

    @_trivia_loop.before_loop
    async def _before_trivia_loop(self):
        await self.bot.wait_until_ready()

    # Weekly crown + reset
    @tasks.loop(seconds=30)
    async def _weekly_loop(self):
        await self.bot.wait_until_ready()
        now = _now_local()
        if not _is_sunday_midnight(now):
            return
        today = now.date().isoformat()
        for guild in list(self.bot.guilds):
            last = self.store["trivia_weekly_done"].get(str(guild.id))
            if last == today:
                continue

            s = self.store["trivia_scores"].get(str(guild.id)) or {}
            users: Dict[str, int] = {k: int(v) for k, v in (s.get("users") or {}).items()}
            # Reset scores for new week
            self.store["trivia_scores"][str(guild.id)] = {"week_id": _week_id(now), "users": {}}
            self.store["trivia_weekly_done"][str(guild.id)] = today
            _save_store(self.store)

            target_id = self._target_trivia(guild.id)
            ch = guild.get_channel(target_id) if target_id else None
            if target_id and not isinstance(ch, discord.TextChannel):
                try:
                    ch = await self.bot.fetch_channel(target_id)  # type: ignore
                except Exception:
                    ch = None

            if not users:
                continue  # nobody played this week

            ranked = sorted(users.items(), key=lambda kv: (-kv[1], int(kv[0])))
            top10 = ranked[:10]
            lines = []
            for i, (uid_str, pts) in enumerate(top10, start=1):
                m = guild.get_member(int(uid_str))
                name = m.display_name if m else f"User {uid_str}"
                medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"#{i}"))
                lines.append(f"**{medal} {name}** — **{pts}** pts")

            embed = (discord.Embed(
                title="🏆 Weekly Trivia Leaderboard",
                description="\n".join(lines),
                color=POLL_COLOR
            ).set_footer(text=f"Kami Fun Pack v{FUNPACK_VERSION} {SHIP}"))

            if ch:
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass

            # Apply champion role to top scorer(s) if configured
            winners_ids = [int(uid) for uid, pts in ranked if pts == ranked[0][1]]
            role_id = self.store["trivia_role"].get(str(guild.id))
            if role_id:
                await self._apply_champion_role(guild, int(role_id), winners_ids)

    @_weekly_loop.before_loop
    async def _before_weekly_loop(self):
        await self.bot.wait_until_ready()

    async def _apply_champion_role(self, guild: discord.Guild, role_id: int, winner_ids: List[int]):
        role = guild.get_role(role_id)
        if not role:
            return
        for m in list(role.members):
            if m.id not in winner_ids:
                try:
                    await m.remove_roles(role, reason="Rotating weekly Trivia Champion")
                except Exception:
                    pass
        for uid in winner_ids:
            member = guild.get_member(uid)
            if member and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Weekly Trivia Champion")
                except Exception:
                    pass

    # --------- Trivia embed builders / helpers ---------
    @staticmethod
    def _trivia_question_embed(qtext: str, choices: List[str]) -> discord.Embed:
        letters = ["A", "B", "C", "D"]
        desc = "\n".join(f"**{letters[i]}** — {choices[i]}" for i in range(4))
        rewards_txt = "/".join(str(x) for x in TRIVIA_REWARDS)
        return (discord.Embed(
            title="🧠 Kami Trivia Challenge",
            description=f"**{qtext}**\n\n{desc}\n\nFirst **3** correct earn **{rewards_txt} {KAMI_COIN_NAME}** (in order).",
            color=TRIVIA_COLOR,
        ).set_footer(text=f"Kami Fun Pack v{FUNPACK_VERSION} {SHIP} | Click a button to answer. One try each."))

    @staticmethod
    def _trivia_result_embed(qtext: str, choices: List[str], correct_index: int, guild: discord.Guild, winners: List[int]) -> discord.Embed:
        if winners:
            medals = ["🥇", "🥈", "🥉"]
            parts = []
            for idx, uid in enumerate(winners):
                member = guild.get_member(uid)
                medal = medals[idx] if idx < 3 else "🏅"
                reward = TRIVIA_REWARDS[idx] if idx < len(TRIVIA_REWARDS) else 0
                name = member.display_name if member else f"User {uid}"
                coin_txt = f" (+{reward} {KAMI_COIN_NAME})" if reward else ""
                parts.append(f"{medal} **{name}**{coin_txt}")
            desc = "\n".join(parts)
        else:
            desc = "No correct answers this round. Next time!"
        correct_txt = choices[correct_index]
        return (discord.Embed(
            title="✅ Round Over — Kami Trivia Challenge",
            description=f"**Answer:** {correct_txt}\n{desc}",
            color=TRIVIA_COLOR
        ).set_footer(text=f"Kami Fun Pack v{FUNPACK_VERSION} {SHIP}"))

    def _round_lock(self, mid: int) -> asyncio.Lock:
        lock = self._round_locks.get(mid)
        if not lock:
            lock = asyncio.Lock()
            self._round_locks[mid] = lock
        return lock

    # --------- Posting / finishing rounds (persistent) ---------
    async def _post_trivia_round(self, channel: discord.TextChannel, auto: bool=False) -> bool:
        bank = self._bank_trivia()
        if not bank:
            try:
                await channel.send("⚠️ No trivia questions configured. Use `!trivia_add` or `/trivia_add` to add some.")
            except Exception:
                pass
            return False
        q = random.choice(bank)
        embed = self._trivia_question_embed(q.q, q.choices)

        # Send with the persistent view
        try:
            msg = await channel.send(embed=embed, view=PersistentTriviaView(self))
        except Exception:
            return False

        # Register active round keyed by message_id
        self.store["active_trivia"][str(msg.id)] = {
            "guild_id": channel.guild.id,
            "channel_id": channel.id,
            "q": q.q,
            "choices": q.choices,
            "correct": int(q.correct_index),
            "winners": [],
            "answered": [],
            "created_ts": int(discord.utils.utcnow().timestamp()),
            "auto": bool(auto),
        }
        _save_store(self.store)
        return True

    async def _finish_trivia_round(self, message: discord.Message, round_data: Dict):
        # Build result embed
        embed = self._trivia_result_embed(
            round_data["q"], round_data["choices"], round_data["correct"], message.guild, round_data.get("winners", [])
        )
        # Disabled view for the final state
        v = PersistentTriviaView(self)
        for c in v.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        try:
            await message.edit(embed=embed, view=v)
        except Exception:
            pass
        # Drop from active
        self.store["active_trivia"].pop(str(message.id), None)
        _save_store(self.store)

    # --------- Button handler (persistent) ---------
    async def _trivia_button(self, interaction: discord.Interaction, idx: int):
        if not interaction.guild or not interaction.message or not interaction.user:
            return await interaction.response.send_message("Guild only.", ephemeral=True)

        msg = interaction.message
        mid = str(msg.id)
        data = self.store.get("active_trivia", {}).get(mid)
        if not data:
            return await interaction.response.send_message("⌛ This round has ended.", ephemeral=True)

        # guard with per-message lock
        async with self._round_lock(msg.id):
            # refetch—another task might have changed it
            data = self.store.get("active_trivia", {}).get(mid)
            if not data:
                return await interaction.response.send_message("⌛ This round has ended.", ephemeral=True)

            uid = interaction.user.id
            answered: Set[int] = set(data.get("answered", []))
            if uid in answered:
                return await interaction.response.send_message("⚡ Enel laughs — you’ve already struck at this one!", ephemeral=True)
            answered.add(uid)
            data["answered"] = list(answered)

            if idx == int(data["correct"]):
                # winner flow
                winners: List[int] = list(data.get("winners", []))
                if uid not in winners:
                    winners.append(uid)
                    data["winners"] = winners
                    rank = len(winners) - 1
                    points = TRIVIA_REWARDS[rank] if rank < len(TRIVIA_REWARDS) else 0
                    try:
                        self._add_weekly_score(interaction.guild.id, uid, points)
                    except Exception:
                        pass
                    if KAMI_BANK and points > 0:
                        try:
                            add_balance(interaction.guild.id, uid, points)
                        except Exception:
                            pass

                # Finish at 3 winners
                _save_store(self.store)
                if len(data["winners"]) >= 3:
                    await self._finish_trivia_round(msg, data)
                else:
                    await interaction.response.send_message("🏴‍☠️ Correct! You’ve earned your spot on the Kami crew.", ephemeral=True)
            else:
                _save_store(self.store)
                await interaction.response.send_message("💀 Nope! The seas aren’t kind today.", ephemeral=True)

    # ================== WYR loop & posting ==================
    @tasks.loop(seconds=30)
    async def _wyr_loop(self):
        await self.bot.wait_until_ready()
        now = _now_local()
        for guild in list(self.bot.guilds):
            target_id = self._target_wyr(guild.id)
            if not target_id:
                continue
            tracker = self._today_tracker(guild.id, "wyr_today")
            hours_needed = self._guild_hours_wyr(guild.id)
            if now.minute != 0 or now.hour not in hours_needed or now.hour in tracker["hours_posted"]:
                continue
            ch = guild.get_channel(target_id) or await self.bot.fetch_channel(target_id)
            if not isinstance(ch, discord.TextChannel):
                continue
            ok = await self._post_wyr_round(ch)
            if ok:
                tracker["hours_posted"].append(now.hour)
                _save_store(self.store)

    @_wyr_loop.before_loop
    async def _before_wyr_loop(self):
        await self.bot.wait_until_ready()

    async def _post_wyr_round(self, channel: discord.TextChannel) -> bool:
        bank = self._bank_wyr()
        if not bank:
            try:
                await channel.send("⚠️ No WYR prompts configured. Use `!wyr_add` or `/wyr_add` to add some.")
            except Exception:
                pass
            return False
        q = random.choice(bank)
        e = (discord.Embed(
            title="🤔 Would You Rather…",
            description=f"🅰️ **{q.a}**\n🅱️ **{q.b}**\n\nFirst vote grants +{WYR_REWARD_PER_VOTE} {KAMI_COIN_NAME} (within 24h).",
            color=WYR_COLOR
        ).set_footer(text=f"Kami Fun Pack v{FUNPACK_VERSION} {SHIP} | Click to vote. You can switch anytime."))
        view = WYRView(self, q.a, q.b, channel.guild)
        try:
            await channel.send(embed=e, view=view)
            return True
        except Exception:
            return False

    # ================== Shared command helpers ==================
    async def _cmd_trivia(self, ctx_or_inter: commands.Context | discord.Interaction):
        # Per-user cooldown
        now_ts = discord.utils.utcnow().timestamp()
        uid = ctx_or_inter.author.id if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.user.id  # type: ignore
        last = self._trivia_user_cooldown.get(uid, 0.0)
        remaining = int(TRIVIA_USER_COOLDOWN_S - (now_ts - last))
        if remaining > 0:
            txt = f"⏱ Please wait **{remaining}s** before starting another trivia round."
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.send(txt)
            return await ctx_or_inter.response.send_message(txt, ephemeral=True)

        # Start one trivia round in the channel
        channel = ctx_or_inter.channel if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.channel  # type: ignore
        guild = ctx_or_inter.guild if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.guild  # type: ignore
        if not isinstance(channel, discord.TextChannel) or not guild:
            txt = "Use this in a server text channel."
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.send(txt)
            return await ctx_or_inter.response.send_message(txt, ephemeral=True)

        ok = await self._post_trivia_round(channel)
        if ok:
            self._trivia_user_cooldown[uid] = now_ts  # stamp cooldown
            if KAMI_BANK:
                msg = f"Top 3 win **{TRIVIA_REWARDS} {KAMI_COIN_NAME}** (per round)."
                if isinstance(ctx_or_inter, commands.Context):
                    await ctx_or_inter.send(msg, delete_after=8)
                else:
                    await ctx_or_inter.response.send_message(msg, ephemeral=True)

    async def _cmd_trivia_top(self, ctx_or_inter: commands.Context | discord.Interaction):
        guild = ctx_or_inter.guild if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.guild  # type: ignore
        if not guild:
            txt = "Use this in a server."
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.send(txt)
            return await ctx_or_inter.response.send_message(txt, ephemeral=True)
        s = self._scores(guild.id)
        users: Dict[str, int] = {k: int(v) for k, v in s["users"].items()}
        if not users:
            msg = "No scores yet this week. Be the first to get on the board with `!trivia` or `/trivia`!"
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.send(msg)
            return await ctx_or_inter.response.send_message(msg, ephemeral=True)
        ranked = sorted(users.items(), key=lambda kv: (-kv[1], int(kv[0])))
        top10 = ranked[:10]
        lines = []
        for i, (uid_str, pts) in enumerate(top10, start=1):
            m = guild.get_member(int(uid_str))
            name = m.display_name if m else f"User {uid_str}"
            medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"#{i}"))
            lines.append(f"**{medal} {name}** — **{pts}** pts")
        embed = (discord.Embed(
            title=f"🏅 Weekly Trivia Leaderboard — {_week_id()}",
            description="\n".join(lines),
            color=POLL_COLOR
        ).set_footer(text=f"Kami Fun Pack v{FUNPACK_VERSION} {SHIP}"))
        if isinstance(ctx_or_inter, commands.Context):
            await ctx_or_inter.send(embed=embed)
        else:
            await ctx_or_inter.response.send_message(embed=embed)

    async def _cmd_wyr(self, ctx_or_inter: commands.Context | discord.Interaction, a: str, b: str):
        # Post a WYR round immediately
        channel = ctx_or_inter.channel if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.channel  # type: ignore
        if not isinstance(channel, discord.TextChannel):
            txt = "Use this in a server text channel."
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.send(txt)
            return await ctx_or_inter.response.send_message(txt, ephemeral=True)
        e = (discord.Embed(
            title="🤔 Would You Rather…",
            description=f"🅰️ **{a}**\n🅱️ **{b}**\n\nFirst vote grants +{WYR_REWARD_PER_VOTE} {KAMI_COIN_NAME} (within 24h).",
            color=WYR_COLOR
        ).set_footer(text=f"Kami Fun Pack v{FUNPACK_VERSION} {SHIP} | Click to vote. You can switch anytime."))
        view = WYRView(self, a, b, channel.guild)
        await channel.send(embed=e, view=view)

    async def _cmd_poll(self, ctx_or_inter: commands.Context | discord.Interaction, question: str, options: List[str]):
        opts = [o.strip() for o in options if o.strip()]
        if not (2 <= len(opts) <= 5):
            txt = "Give me **2–5** options."
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.send(txt)
            return await ctx_or_inter.response.send_message(txt, ephemeral=True)
        e = (discord.Embed(
            title=f"📊 Quick Poll — {question}",
            description="\n".join(f"• {opt}" for opt in opts),
            color=POLL_COLOR
        ).set_footer(text=f"Kami Fun Pack v{FUNPACK_VERSION} {SHIP} | Click a button to vote."))
        view = PollView(opts)
        channel = ctx_or_inter.channel if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.channel  # type: ignore
        if isinstance(channel, discord.TextChannel):
            await channel.send(embed=e, view=view)
        else:
            txt = "Use this in a server text channel."
            if isinstance(ctx_or_inter, commands.Context):
                await ctx_or_inter.send(txt)
            else:
                await ctx_or_inter.response.send_message(txt, ephemeral=True)

    async def _cmd_rps(self, ctx_or_inter: commands.Context):
        e = (discord.Embed(
            title="✊ Kami RPS",
            description="Challenge Kami and pick your weapon.",
            color=MISC_COLOR
        ).set_footer(text=f"Kami Fun Pack v{FUNPACK_VERSION} {SHIP}"))
        view = RPSView(ctx_or_inter.author.id if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.user.id)  # type: ignore
        channel = ctx_or_inter.channel if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.channel  # type: ignore
        if isinstance(channel, discord.TextChannel):
            await channel.send(embed=e, view=view)
        else:
            txt = "Use this in a server text channel."
            if isinstance(ctx_or_inter, commands.Context):
                await ctx_or_inter.send(txt)
            else:
                await ctx_or_inter.response.send_message(txt, ephemeral=True)

    async def _cmd_ttt(self, ctx_or_inter: commands.Context | discord.Interaction, p1: discord.Member, p2: discord.Member):
        if p1.bot or p2.bot or p1 == p2:
            txt = "Pick two different human players."
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.send(txt)
            return await ctx_or_inter.response.send_message(txt, ephemeral=True)
        view = TTTView(p1, p2)
        channel = ctx_or_inter.channel if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.channel  # type: ignore
        if isinstance(channel, discord.TextChannel):
            await channel.send("Tic‑Tac‑Toe — good luck!", view=view)
        else:
            txt = "Use this in a server text channel."
            if isinstance(ctx_or_inter, commands.Context):
                await ctx_or_inter.send(txt)
            else:
                await ctx_or_inter.response.send_message(txt, ephemeral=True)

    # ================== Prefix Commands ==================
    @commands.command(name="trivia", help="Start one Trivia round now in this channel.")
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def trivia_cmd(self, ctx: commands.Context):
        await self._cmd_trivia(ctx)

    @commands.command(name="trivia_top", help="Show this week’s Trivia leaderboard.")
    async def trivia_top_cmd(self, ctx: commands.Context):
        await self._cmd_trivia_top(ctx)

    @commands.command(name="wyr", help="Start a WYR round now. Format: !wyr Option A | Option B")
    async def wyr_cmd(self, ctx: commands.Context, *, text: str):
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if len(parts) != 2:
            return await ctx.send("Format: `!wyr Option A | Option B`")
        await self._cmd_wyr(ctx, parts[0], parts[1])

    @commands.command(name="poll", help='Create a quick poll: !poll "Question?" opt1 | opt2 | [opt3..opt5]')
    async def poll_cmd(self, ctx: commands.Context, question: str, *, options: str):
        opts = [o.strip() for o in options.split("|")]
        await self._cmd_poll(ctx, question, opts)

    @commands.command(name="rps", help="Play Rock‑Paper‑Scissors with Kami.")
    async def rps_cmd(self, ctx: commands.Context):
        await self._cmd_rps(ctx)

    @commands.command(name="ttt", help="Start Tic‑Tac‑Toe between two members: !ttt @p1 @p2")
    async def ttt_cmd(self, ctx: commands.Context, p1: discord.Member, p2: discord.Member):
        await self._cmd_ttt(ctx, p1, p2)

    @commands.command(name="funpack_version", help="Show the current Fun Pack version.")
    async def funpack_version(self, ctx: commands.Context):
        await ctx.send(f"Kami Fun Pack — **v{FUNPACK_VERSION}** (No timeouts • WYR 24h reward limit • Slash + Prefix • Persistent Trivia • Per-user cooldown)")

    # ================== Slash Commands (Global) ==================
    @app_commands.command(name="trivia", description="Start one Trivia round now in this channel.")
    async def slash_trivia(self, interaction: discord.Interaction):
        await self._cmd_trivia(interaction)

    @app_commands.command(name="trivia_top", description="Show this week’s Trivia leaderboard.")
    async def slash_trivia_top(self, interaction: discord.Interaction):
        await self._cmd_trivia_top(interaction)

    @app_commands.command(name="wyr", description="Start a WYR round: /wyr option_a | option_b")
    @app_commands.describe(text="Format: Option A | Option B")
    async def slash_wyr(self, interaction: discord.Interaction, text: str):
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if len(parts) != 2:
            return await interaction.response.send_message("Format: `Option A | Option B`", ephemeral=True)
        await self._cmd_wyr(interaction, parts[0], parts[1])

    @app_commands.command(name="poll", description="Create a quick poll with 2–5 options.")
    @app_commands.describe(question="The poll question", options="Options separated by | (2–5)")
    async def slash_poll(self, interaction: discord.Interaction, question: str, options: str):
        opts = [o.strip() for o in options.split("|")]
        await self._cmd_poll(interaction, question, opts)

    @app_commands.command(name="rps", description="Play Rock‑Paper‑Scissors with Kami.")
    async def slash_rps(self, interaction: discord.Interaction):
        await self._cmd_rps(interaction)

    @app_commands.command(name="ttt", description="Start Tic‑Tac‑Toe between two members.")
    @app_commands.describe(p1="Player 1", p2="Player 2")
    async def slash_ttt(self, interaction: discord.Interaction, p1: discord.Member, p2: discord.Member):
        await self._cmd_ttt(interaction, p1, p2)

    @app_commands.command(name="funpack_version", description="Show the current Fun Pack version.")
    async def slash_funpack_version(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"Kami Fun Pack — **v{FUNPACK_VERSION}** (No timeouts • WYR 24h reward limit • Slash + Prefix • Persistent Trivia • Per-user cooldown)",
            ephemeral=True
        )


# ---------- setup entry ----------
async def setup(bot: commands.Bot):
    await bot.add_cog(KamiFunPack(bot))