# cogs/gamble.py
from __future__ import annotations
import random, math, time
from typing import Optional, Set, List, Tuple, Dict

import discord
from discord.ext import commands

from .bank import (
    set_path as bank_set_path,
    bank_load, bank_save,
    get_balance, add_balance,
)

KAMICOIN_NAME = "KamiCoins"
MIN_BET = 1

# House (Kami Bank)
BANKER_UID = -42
BANKER_START_BALANCE = 1_000_000  # <- 1 million start
BACCARAT_WEIGHTS = {"player": 44.6, "banker": 45.9, "tie": 9.5}

# Blackjack config
BJ_TIMEOUT = 90           # seconds of inactivity before we auto-stand
BJ_DEALER_STAND_SOFT17 = True  # dealer stands on all 17 (incl. soft)
BJ_BLACKJACK_PAYOUT = 1.5  # 3:2 net (total returned = bet * 2.5)

# -------- helpers --------
def _parse_bet(arg: str, balance: int) -> int:
    arg = arg.strip().lower()
    if arg in ("all", "max"):
        amt = balance
    elif arg in ("half", "½"):
        amt = balance // 2
    else:
        try:
            amt = int(arg.replace("_", "").replace(",", ""))
        except ValueError:
            amt = -1
    return max(amt, -1)

def _fmt(n: int) -> str:
    return f"{n:,} {KAMICOIN_NAME}"

def _user_bal(ctx: commands.Context, uid: Optional[int] = None) -> int:
    return get_balance(ctx.guild.id, uid or ctx.author.id)

def _house_bal(ctx: commands.Context) -> int:
    return get_balance(ctx.guild.id, BANKER_UID)

def _house_add(ctx: commands.Context, delta: int) -> int:
    return add_balance(ctx.guild.id, BANKER_UID, delta)

def _user_add(ctx: commands.Context, delta: int, uid: Optional[int] = None) -> int:
    return add_balance(ctx.guild.id, uid or ctx.author.id, delta)

# === Casino-style settlement ===
# Place bet: move bet from user -> house.
def _take_bet(ctx: commands.Context, bet: int) -> None:
    _user_add(ctx, -bet)
    _house_add(ctx, +bet)

# Pay total to user (includes returning the stake):
def _payout_total(ctx: commands.Context, total: int) -> int:
    _house_add(ctx, -total)
    return _user_add(ctx, +total)

def _save_silent():
    try: bank_save()
    except Exception: pass


# =================== Blackjack engine ===================
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A","2","3","4","5","6","7","8","9","T","J","Q","K"]
CARD_EMO = {"A":"🂡","K":"🂮","Q":"🂭","J":"🂫","T":"10"}

def _new_deck() -> List[str]:
    deck = [r+s for s in SUITS for r in RANKS] * 6  # 6-deck shoe
    random.shuffle(deck)
    return deck

def _hand_value(cards: List[str]) -> Tuple[int, bool]:
    """Returns (best_total, is_soft)."""
    total = 0
    aces = 0
    for c in cards:
        r = c[0]
        if r == "A":
            aces += 1
            total += 11
        elif r in "TJQK":
            total += 10
        else:
            total += int(r)
    soft = False
    while total > 21 and aces:
        total -= 10
        aces -= 1
    if aces > 0:
        soft = True if total <= 21 else False
    return total, soft

def _is_blackjack(cards: List[str]) -> bool:
    if len(cards) != 2:
        return False
    ranks = {c[0] for c in cards}
    return ("A" in ranks) and any(r in ranks for r in ("T","J","Q","K"))

def _fmt_cards(cards: List[str], hide_first: bool = False) -> str:
    out = []
    for i, c in enumerate(cards):
        r, s = c[0], c[1]
        face = CARD_EMO.get(r, r)
        if hide_first and i == 0:
            out.append("🂠")
        else:
            out.append(f"{face}{s}")
    return " ".join(out)

class BJGame:
    def __init__(self, guild_id: int, channel_id: int, user_id: int, bet: int):
        self.gid = guild_id
        self.cid = channel_id
        self.uid = user_id
        self.bet = bet
        self.deck = _new_deck()
        self.player: List[str] = []
        self.dealer: List[str] = []
        self.active = True
        self.last_action = time.time()
        self.doubled = False

    def deal_initial(self):
        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]

    def hit_player(self) -> str:
        self.last_action = time.time()
        c = self.deck.pop()
        self.player.append(c)
        return c

    def dealer_play(self):
        # Dealer reveals; hit until rules satisfied
        while True:
            total, soft = _hand_value(self.dealer)
            if total < 17:
                self.dealer.append(self.deck.pop())
                continue
            if total == 17 and not BJ_DEALER_STAND_SOFT17 and soft:
                self.dealer.append(self.deck.pop())
                continue
            break

    def expired(self) -> bool:
        return (time.time() - self.last_action) >= BJ_TIMEOUT


# =================== Cog ===================
class Gamble(commands.Cog, name="Gamble"):
    """Kami Casino games. House is the **Kami Bank** (🏯)."""

    def __init__(self, bot: commands.Bot, bank_path: Optional[str] = None):
        self.bot = bot
        if bank_path:
            bank_set_path(bank_path)
            bank_load()
        self._banker_seeded: Set[int] = set()
        # active blackjack sessions: (guild_id, channel_id) -> BJGame
        self._bj_games: Dict[Tuple[int,int], BJGame] = {}

    # --- internal ---
    def _ensure_banker(self, ctx: commands.Context) -> None:
        gid = ctx.guild.id
        if gid in self._banker_seeded:
            return
        if get_balance(gid, BANKER_UID) <= 0:
            add_balance(gid, BANKER_UID, BANKER_START_BALANCE)
        self._banker_seeded.add(gid)

    # ---------- COIN FLIP ----------
    @commands.command(
        name="flip",
        help=("Flip a golden coin and guess **heads** or **tails**.\n"
              "Win = 2× total payout (net +bet). Examples: `!flip 100 heads`, `!flip half tails`"),
        usage="<amount: number|all|half> [heads|tails]"
    )
    @commands.cooldown(1, 2.0, commands.BucketType.user)
    async def flip_cmd(self, ctx: commands.Context, amount: str, guess: str | None = None):
        self._ensure_banker(ctx)
        bal = _user_bal(ctx)
        bet = _parse_bet(amount, bal)
        if bet < MIN_BET: return await ctx.send(f"Bet must be ≥ {MIN_BET}. Balance: {_fmt(bal)}.")
        if bet > bal:     return await ctx.send(f"Not enough funds. Balance: {_fmt(bal)}.")

        user_pick = None
        if guess:
            g = guess.strip().lower()
            if g not in ("h","head","heads","t","tail","tails"):
                return await ctx.send("Pick **heads** or **tails** (or omit to just flip).")
            user_pick = "heads" if g.startswith("h") else "tails"

        _take_bet(ctx, bet)
        outcome = random.choice(("heads", "tails"))

        if user_pick and user_pick == outcome:
            new_bal = _payout_total(ctx, bet * 2)
            msg = f"🪙 **{outcome}**! You won **{_fmt(bet)}**. Balance: **{_fmt(new_bal)}**."
        else:
            new_bal = _user_bal(ctx)
            msg = (f"🪙 **{outcome.upper()}** — lost **{_fmt(bet)}**. "
                   f"Balance: **{_fmt(new_bal)}**.") if user_pick else \
                  (f"🪙 It’s **{outcome}**. No call, no payout. Balance: **{_fmt(new_bal)}**.")
        msg += f"\n🏯 Kami Bank: **{_fmt(_house_bal(ctx))}**."
        await ctx.send(msg)
        _save_silent()

    # ---------- DICE ----------
    @commands.command(
        name="dice",
        help="Guess **1–6** (5×) or **high**(4–6)/**low**(1–3) (1.8×).",
        usage="<amount: number|all|half> <1-6|high|low>"
    )
    @commands.cooldown(1, 2.0, commands.BucketType.user)
    async def dice_cmd(self, ctx: commands.Context, amount: str, guess: str):
        self._ensure_banker(ctx)
        bal = _user_bal(ctx)
        bet = _parse_bet(amount, bal)
        if bet < MIN_BET: return await ctx.send(f"Bet must be ≥ {MIN_BET}. Balance: {_fmt(bal)}.")
        if bet > bal:     return await ctx.send(f"Not enough funds. Balance: {_fmt(bal)}.")

        g = guess.strip().lower()
        if g in ("high","h"):  exact, mult = None, 1.8
        elif g in ("low","l"): exact, mult = None, 1.8
        else:
            try:
                n = int(g); assert 1 <= n <= 6
            except Exception:
                return await ctx.send("Guess **1-6**, or **high**/**low**.")
            exact, mult = n, 5.0

        _take_bet(ctx, bet)
        roll = random.randint(1, 6)
        win = (roll == exact) if exact else ((roll >= 4) if g.startswith("h") else (roll <= 3))

        if win:
            total = int(bet * mult)
            new_bal = _payout_total(ctx, total)
            await ctx.send(f"🎲 **{roll}** — WIN! +{_fmt(total - bet)} (payout {mult:g}×). "
                           f"Bal: **{_fmt(new_bal)}** | 🏯 **{_fmt(_house_bal(ctx))}**.")
        else:
            await ctx.send(f"🎲 **{roll}** — lost **{_fmt(bet)}**. Bal: **{_fmt(_user_bal(ctx))}** | "
                           f"🏯 **{_fmt(_house_bal(ctx))}**.")
        _save_silent()

    # ---------- SLOTS ----------
    @commands.command(
        name="slots",
        help="7️⃣7️⃣7️⃣ = 10×, any 3 of a kind = 5×, any 2 of a kind = 2×.",
        usage="<amount: number|all|half>"
    )
    @commands.cooldown(1, 2.0, commands.BucketType.user)
    async def slots_cmd(self, ctx: commands.Context, amount: str):
        self._ensure_banker(ctx)
        bal = _user_bal(ctx)
        bet = _parse_bet(amount, bal)
        if bet < MIN_BET: return await ctx.send(f"Bet must be ≥ {MIN_BET}. Balance: {_fmt(bal)}.")
        if bet > bal:     return await ctx.send(f"Not enough funds. Balance: {_fmt(bal)}.")

        _take_bet(ctx, bet)
        icons = ["🍒","🍋","🔔","⭐","7️⃣","🍀"]
        r = [random.choice(icons) for _ in range(3)]
        a, b, c = r
        mult = 0
        if a == b == c == "7️⃣": mult = 10
        elif a == b == c:        mult = 5
        elif a == b or a == c or b == c: mult = 2

        if mult:
            total = bet * mult
            new_bal = _payout_total(ctx, total)
            await ctx.send(f"🎰 {' '.join(r)} — **WIN {mult}×** (+{_fmt(total - bet)}). "
                           f"Bal: **{_fmt(new_bal)}** | 🏯 **{_fmt(_house_bal(ctx))}**.")
        else:
            await ctx.send(f"🎰 {' '.join(r)} — lost **{_fmt(bet)}**. Bal: **{_fmt(_user_bal(ctx))}** | "
                           f"🏯 **{_fmt(_house_bal(ctx))}**.")
        _save_silent()

    # ---------- BACCARAT ----------
    @commands.command(
        name="baccarat",
        aliases=["bac","bacc","punto","kami_baccarat"],
        help="Bet on **player** (1:1), **banker** (0.95:1, 5% commission), or **tie** (8:1).",
        usage="<amount: number|all|half> <player|banker|tie>"
    )
    @commands.cooldown(1, 3.0, commands.BucketType.user)
    async def baccarat_cmd(self, ctx: commands.Context, amount: str, side: str):
        self._ensure_banker(ctx)

        bal = _user_bal(ctx)
        bet = _parse_bet(amount, bal)
        if bet < MIN_BET: return await ctx.send(f"Bet must be ≥ {MIN_BET}. Balance: {_fmt(bal)}.")
        if bet > bal:     return await ctx.send(f"Not enough funds. Balance: {_fmt(bal)}.")

        s = side.strip().lower()
        if s not in ("player","p","banker","b","tie","t"):
            return await ctx.send("Pick **player**, **banker**, or **tie**.")
        s = {"p":"player","b":"banker","t":"tie"}.get(s, s)

        _take_bet(ctx, bet)

        pool = []
        for name, w in BACCARAT_WEIGHTS.items():
            pool.extend([name] * int(w * 10))
        outcome = random.choice(pool)

        if s == outcome:
            if outcome == "player":
                total = bet * 2
                new_bal = _payout_total(ctx, total)
                note = f"You won **{_fmt(bet)}**."
            elif outcome == "banker":
                win_net = math.floor(bet * 0.95)     # net
                total = bet + win_net
                new_bal = _payout_total(ctx, total)
                note = f"You won **{_fmt(win_net)}** after 5% commission."
            else:  # tie
                total = bet * 9
                new_bal = _payout_total(ctx, total)
                note = f"You won **{_fmt(bet * 8)}** (8:1)."
        else:
            new_bal = _user_bal(ctx)
            note = f"You lost **{_fmt(bet)}**."

        icons = {"player":"🧑‍🎴","banker":"🏦","tie":"⚖️"}
        msg = (f"🀄 **Baccarat** — Outcome: {icons[outcome]} **{outcome.title()}**.\n"
               f"{note} Your balance: **{_fmt(new_bal)}**.\n"
               f"🏯 **Kami Bank**: **{_fmt(_house_bal(ctx))}**.")
        await ctx.send(msg)
        _save_silent()

    # ---------- VIDEO POKER (Jacks-or-Better) ----------
    @commands.command(
        name="videopoker",
        aliases=["vp"],
        help=("Draw 5 cards. Pays on Jacks-or-Better and up.\n"
              "Paytable: Pair J/Q/K/A=1×, Two Pair=2×, Trips=3×, Straight=4×, "
              "Flush=6×, Full House=9×, Quads=25×, Straight Flush=50×, Royal=250×"),
        usage="<amount: number|all|half>"
    )
    @commands.cooldown(1, 3.0, commands.BucketType.user)
    async def videopoker_cmd(self, ctx: commands.Context, amount: str):
        self._ensure_banker(ctx)
        bal = _user_bal(ctx)
        bet = _parse_bet(amount, bal)
        if bet < MIN_BET: return await ctx.send(f"Bet must be ≥ {MIN_BET}. Balance: {_fmt(bal)}.")
        if bet > bal:     return await ctx.send(f"Not enough funds. Balance: {_fmt(bal)}.")

        _take_bet(ctx, bet)

        ranks = "23456789TJQKA"
        suits = "♠♥♦♣"
        deck = [r+s for r in ranks for s in suits]
        random.shuffle(deck)
        hand = deck[:5]

        mult, name = _evaluate_video_poker(hand, ranks)
        if mult >= 1:
            total = bet * (mult + 1)  # return stake + net
            new_bal = _payout_total(ctx, total)
            await ctx.send(f"🃏 **{' '.join(hand)}** — {name}! Payout {mult+1}× "
                           f"(+{_fmt(bet*mult)}). Bal: **{_fmt(new_bal)}** | "
                           f"🏯 **{_fmt(_house_bal(ctx))}**.")
        else:
            await ctx.send(f"🃏 **{' '.join(hand)}** — no hand. Lost **{_fmt(bet)}**. "
                           f"Bal: **{_fmt(_user_bal(ctx))}** | 🏯 **{_fmt(_house_bal(ctx))}**.")
        _save_silent()

    # ---------- ROULETTE ----------
    @commands.command(
        name="roulette",
        help=("Bet on a **number** (0–36) for 35:1, or **red/black/odd/even** for 1:1.\n"
              "Examples: `!roulette 100 red`, `!roulette 50 17`"),
        usage="<amount: number|all|half> <red|black|odd|even|0-36>"
    )
    @commands.cooldown(1, 2.0, commands.BucketType.user)
    async def roulette_cmd(self, ctx: commands.Context, amount: str, bet_on: str):
        self._ensure_banker(ctx)
        bal = _user_bal(ctx)
        bet = _parse_bet(amount, bal)
        if bet < MIN_BET: return await ctx.send(f"Bet must be ≥ {MIN_BET}. Balance: {_fmt(bal)}.")
        if bet > bal:     return await ctx.send(f"Not enough funds. Balance: {_fmt(bal)}.")

        choice = bet_on.strip().lower()
        num_choice: Optional[int] = None
        kind: Optional[str] = None

        if choice in ("red","black","odd","even"):
            kind = choice
        else:
            try:
                n = int(choice); assert 0 <= n <= 36
                num_choice = n
            except Exception:
                return await ctx.send("Bet **red/black/odd/even** or a **number 0–36**.")

        _take_bet(ctx, bet)

        number = random.randint(0, 36)
        red_nums = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        color = "red" if number in red_nums else ("green" if number == 0 else "black")
        parity = None if number == 0 else ("odd" if number % 2 else "even")

        win = False
        total = 0
        if num_choice is not None:
            if number == num_choice:
                win = True; total = bet * 36  # 35:1 net → total 36×
        else:
            if parity and kind in ("odd","even") and kind == parity:
                win = True; total = bet * 2
            if kind in ("red","black") and kind == color:
                win = True; total = bet * 2

        if win:
            new_bal = _payout_total(ctx, total)
            await ctx.send(f"🎡 **{number} {color}** — WIN! "
                           f"{'number' if num_choice is not None else kind} pays "
                           f"{(36 if num_choice is not None else 2)}×. "
                           f"Bal: **{_fmt(new_bal)}** | 🏯 **{_fmt(_house_bal(ctx))}**.")
        else:
            await ctx.send(f"🎡 **{number} {color}** — lost **{_fmt(bet)}**. "
                           f"Bal: **{_fmt(_user_bal(ctx))}** | 🏯 **{_fmt(_house_bal(ctx))}**.")
        _save_silent()

    # ---------------- BLACKJACK ----------------
    @commands.group(
        name="bj",
        invoke_without_command=True,
        help=("**Blackjack at the Thousand Sunny table**.\n"
              "`!bj <amount>` to sit & deal, then `!hit`, `!stand`, `!double`.\n"
              "Payouts: win 1:1, blackjack 3:2, push returns bet.")
    )
    async def bj_group(self, ctx: commands.Context, amount: Optional[str] = None):
        if amount is None:
            return await ctx.send("Usage: `!bj <amount>` to sit and deal your hand.")
        self._ensure_banker(ctx)

        key = (ctx.guild.id, ctx.channel.id)
        if key in self._bj_games and self._bj_games[key].active:
            return await ctx.send("A Blackjack round is already in progress at this table.")

        bal = _user_bal(ctx)
        bet = _parse_bet(amount, bal)
        if bet < MIN_BET: return await ctx.send(f"Bet must be ≥ {MIN_BET}. Balance: {_fmt(bal)}.")
        if bet > bal:     return await ctx.send(f"Not enough funds. Balance: {_fmt(bal)}.")

        _take_bet(ctx, bet)
        game = BJGame(ctx.guild.id, ctx.channel.id, ctx.author.id, bet)
        game.deal_initial()
        self._bj_games[key] = game

        p_total, _ = _hand_value(game.player)
        d_up = game.dealer[1]
        themed = "🌊 Nami shuffles the deck… Zoro cuts—"
        msg = (f"{themed}\n"
               f"**Your hand:** {_fmt_cards(game.player)}  (**{p_total}**)\n"
               f"**Dealer:** {_fmt_cards(game.dealer, hide_first=True)}  (showing {d_up[0]}{d_up[1]})\n")

        # Check naturals
        p_bj = _is_blackjack(game.player)
        d_bj = _is_blackjack(game.dealer)
        if p_bj or d_bj:
            game.dealer_play()
            await self._bj_finish(ctx, game, natural_check=True)
            return
        msg += "Type **`!hit`**, **`!stand`**, or **`!double`**. ⏳"
        await ctx.send(msg)
        _save_silent()

    @commands.command(name="hit")
    async def bj_hit(self, ctx: commands.Context):
        key = (ctx.guild.id, ctx.channel.id)
        game = self._bj_games.get(key)
        if not game or not game.active:
            return await ctx.send("No Blackjack hand active here. Start with `!bj <amount>`.")
        if game.uid != ctx.author.id:
            return await ctx.send("Only the seated player can act.")
        if game.expired():
            return await self._bj_auto_stand(ctx, game)

        c = game.hit_player()
        total, _ = _hand_value(game.player)
        if total > 21:
            game.active = False
            await ctx.send(f"🃏 You drew **{c}** → **{_fmt_cards(game.player)}** (**{total}**) — **BUST**.\n"
                           f"🏯 Kami Bank: **{_fmt(_house_bal(ctx))}**.")
            _save_silent()
            return
        await ctx.send(f"🃏 Hit: drew **{c}** → **{_fmt_cards(game.player)}** (**{total}**). "
                       f"Type **`!hit`** or **`!stand`**.")
        _save_silent()

    @commands.command(name="stand")
    async def bj_stand(self, ctx: commands.Context):
        key = (ctx.guild.id, ctx.channel.id)
        game = self._bj_games.get(key)
        if not game or not game.active:
            return await ctx.send("No Blackjack hand active here. Start with `!bj <amount>`.")
        if game.uid != ctx.author.id:
            return await ctx.send("Only the seated player can act.")
        await self._bj_finish(ctx, game)

    @commands.command(name="double")
    async def bj_double(self, ctx: commands.Context):
        key = (ctx.guild.id, ctx.channel.id)
        game = self._bj_games.get(key)
        if not game or not game.active:
            return await ctx.send("No Blackjack hand active here. Start with `!bj <amount>`.")
        if game.uid != ctx.author.id:
            return await ctx.send("Only the seated player can act.")
        if game.doubled:
            return await ctx.send("You already doubled once.")

        bal = _user_bal(ctx)
        if bal < game.bet:
            return await ctx.send("Not enough balance to double your bet.")

        # take additional bet
        _take_bet(ctx, game.bet)
        game.bet *= 2
        game.doubled = True

        c = game.hit_player()
        total, _ = _hand_value(game.player)
        if total > 21:
            game.active = False
            await ctx.send(f"🃏 Double-down drew **{c}** → **{_fmt_cards(game.player)}** (**{total}**) — **BUST**.\n"
                           f"🏯 Kami Bank: **{_fmt(_house_bal(ctx))}**.")
            _save_silent()
            return
        # Forced stand after double
        await self._bj_finish(ctx, game, from_double=True)

    @commands.command(name="bjstatus")
    async def bj_status(self, ctx: commands.Context):
        key = (ctx.guild.id, ctx.channel.id)
        game = self._bj_games.get(key)
        if not game or not game.active:
            return await ctx.send("No Blackjack hand active here.")
        if game.uid != ctx.author.id:
            return await ctx.send("Only the seated player can check the current hand.")
        p_total, _ = _hand_value(game.player)
        await ctx.send(f"**Your hand:** {_fmt_cards(game.player)} (**{p_total}**)\n"
                       f"**Dealer:** {_fmt_cards(game.dealer, hide_first=True)}")

    @commands.command(name="bjend")
    async def bj_end(self, ctx: commands.Context):
        key = (ctx.guild.id, ctx.channel.id)
        game = self._bj_games.get(key)
        if not game or not game.active:
            return await ctx.send("No Blackjack hand active here.")
        if game.uid != ctx.author.id:
            return await ctx.send("Only the seated player can end the hand.")
        game.active = False
        await ctx.send("Blackjack hand ended.")

    async def _bj_auto_stand(self, ctx: commands.Context, game: BJGame):
        await ctx.send("⏳ Time’s up—auto **stand**.")
        await self._bj_finish(ctx, game)

    async def _bj_finish(self, ctx: commands.Context, game: BJGame, natural_check: bool=False, from_double: bool=False):
        # Dealer play & settle
        game.dealer_play()
        game.active = False

        p_total, _ = _hand_value(game.player)
        d_total, _ = _hand_value(game.dealer)

        p_bj = _is_blackjack(game.player)
        d_bj = _is_blackjack(game.dealer)

        result = ""
        total_pay = 0

        if natural_check:
            # natural resolution
            if p_bj and d_bj:
                # push
                total_pay = game.bet  # return stake
                result = f"Both **Blackjack** — **Push**. Stake returned."
            elif p_bj:
                total_pay = game.bet + int(game.bet * BJ_BLACKJACK_PAYOUT)
                result = f"**Blackjack!** Pays 3:2."
            elif d_bj:
                result = f"Dealer has **Blackjack** — you lose."
            else:
                # shouldn't happen
                pass
        else:
            # normal resolution
            if p_total > 21:
                result = "You **busted** — you lose."
            elif d_total > 21:
                total_pay = game.bet * 2
                result = "Dealer **busted** — you win 1:1."
            elif p_total > d_total:
                total_pay = game.bet * 2
                result = "You win 1:1."
            elif p_total < d_total:
                result = "Dealer wins."
            else:
                total_pay = game.bet
                result = "**Push** — stake returned."

        if total_pay:
            new_bal = _payout_total(ctx, total_pay)
        else:
            new_bal = _user_bal(ctx)

        await ctx.send(
            f"🃏 **Your:** {_fmt_cards(game.player)} (**{p_total}**)\n"
            f"🏦 **Dealer:** {_fmt_cards(game.dealer)} (**{d_total}**)\n"
            f"{result}  |  Bet: **{_fmt(game.bet)}**\n"
            f"**Balance:** {_fmt(new_bal)}   •   🏯 **Kami Bank:** {_fmt(_house_bal(ctx))}"
        )
        _save_silent()

    # ---------- HOUSE ----------
    @commands.command(name="banker", aliases=["kamibank","house"])
    async def banker_cmd(self, ctx: commands.Context):
        self._ensure_banker(ctx)
        await ctx.send(f"🏯 **Kami Bank** balance: **{_fmt(_house_bal(ctx))}**.")


# ---- Video Poker evaluator ----
def _evaluate_video_poker(hand: List[str], ranks: str) -> Tuple[int, str]:
    """Returns (net_mult, name). net_mult is 0 if no pay. Jacks-or-Better."""
    order = {r:i for i,r in enumerate(ranks)}
    rs = [h[0] for h in hand]
    ss = [h[1] for h in hand]
    counts = {r: rs.count(r) for r in set(rs)}
    is_flush = len(set(ss)) == 1
    idxs = sorted(order[r] for r in rs)
    is_straight = all(idxs[i]+1 == idxs[i+1] for i in range(4)) or set(rs) == set("A2345")

    by_count = sorted(counts.values(), reverse=True)
    if is_straight and is_flush:
        if set(rs) == set("TJQKA"):
            return 250, "Royal Flush"
        return 50, "Straight Flush"
    if by_count == [4,1]:
        return 25, "Four of a Kind"
    if by_count == [3,2]:
        return 9, "Full House"
    if is_flush:
        return 6, "Flush"
    if is_straight:
        return 4, "Straight"
    if by_count == [3,1,1]:
        return 3, "Three of a Kind"
    if by_count == [2,2,1]:
        return 2, "Two Pair"
    if by_count == [2,1,1,1]:
        pair_rank = [r for r,c in counts.items() if c == 2][0]
        if pair_rank in "JQKA":
            return 1, "Jacks or Better"
    return 0, "No Hand"
