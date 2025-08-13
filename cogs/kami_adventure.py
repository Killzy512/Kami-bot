# kami_adventure.py

import discord
from discord.ext import commands
import json
import random
import asyncio
from discord.ui import View, Button

# === Load Data === #
def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
        return {}

MOBS = load_json('./data/mobs.json')
ITEMS = load_json('./data/items.json')
SKILLS = load_json('./data/skills.json')

# === Constants === #
REVIVE_HP = 3
DEFAULT_PLAYER_HP = 100
EMOJI_HEART = "❤️"
EMOJI_SHIELD = "🛡️"
EMOJI_SWORD = "⚔️"
EMOJI_KAMI = "💠"
EMOJI_SKULL = "💀"

class CombatPlayer:
    def __init__(self, member: discord.Member, race: str = "human"):
        self.member = member
        self.name = member.display_name
        self.id = str(member.id)
        self.hp = DEFAULT_PLAYER_HP
        self.max_hp = DEFAULT_PLAYER_HP
        self.defending = False
        self.turn_taken = False
        self.equipment = {
            "weapon": None,
            "shield": None,
            "accessories": []
        }
        self.race = race
        self.effects = self.get_race_effects(race)
        self.last_action = ""

    def get_race_effects(self, race):
        # Expand this later to load from a race.json
        race_data = {
            "vampire": {"lifesteal": 0.10},
            "elf": {"dodge_chance": 0.15},
            "orc": {"attack_bonus": 5, "defense_penalty": 5},
            "human": {"xp_bonus": 0.10},
            "spirit": {"revive_hp": 6},
        }
        return race_data.get(race, {})

    def is_alive(self):
        return self.hp > 0

    def revive(self):
        self.hp = self.effects.get("revive_hp", REVIVE_HP)

    def take_damage(self, amount):
        if self.defending:
            amount //= 2
        dodge = self.effects.get("dodge_chance", 0)
        if random.random() < dodge:
            self.last_action = f"{self.name} **dodged** the attack!"
            return 0
        self.hp = max(self.hp - amount, 0)
        return amount

    def deal_damage(self, base_damage):
        bonus = self.effects.get("attack_bonus", 0)
        return base_damage + bonus

    def heal(self, amount):
        self.hp = min(self.hp + amount, self.max_hp)

    def get_display(self):
        status = EMOJI_SHIELD if self.defending else ""
        if not self.is_alive():
            return f"{EMOJI_SKULL} {self.name} (KO)"
        return f"{EMOJI_HEART} {self.hp}/{self.max_hp} - {self.name} {status}"


class CombatMob:
    def __init__(self, template: dict):
        self.name = template.get("name", "Unknown Mob")
        self.hp = template.get("hp", 100)
        self.max_hp = self.hp
        self.attack = template.get("attack", 10)
        self.reward = template.get("reward", {"gold": 50, "xp": 25})
        self.id = f"mob_{random.randint(1000,9999)}"

    def is_alive(self):
        return self.hp > 0

    def take_damage(self, amount):
        self.hp = max(self.hp - amount, 0)
        return amount

    def get_display(self):
        return f"👹 **{self.name}** - {self.hp}/{self.max_hp} HP"


class BattleParty:
    def __init__(self, mob_template: dict):
        self.mob = CombatMob(mob_template)
        self.players: dict[str, CombatPlayer] = {}
        self.started = True
        self.turn_order = []
        self.active = True
        self.turn_index = 0

    def add_player(self, member: discord.Member):
        uid = str(member.id)
        if uid not in self.players:
            self.players[uid] = CombatPlayer(member)
            self.turn_order.append(uid)

    def get_player(self, user: discord.User):
        return self.players.get(str(user.id))

    def alive_players(self):
        return [p for p in self.players.values() if p.is_alive()]

    def all_players_ready(self):
        return all(p.turn_taken or not p.is_alive() for p in self.players.values())

    def reset_turns(self):
        for p in self.players.values():
            p.turn_taken = False
            p.defending = False

    def is_finished(self):
        return not self.mob.is_alive() or len(self.alive_players()) == 0

    def revive_dead(self):
        for p in self.players.values():
            if p.hp <= 0:
                p.revive()

# === GLOBAL BATTLE STATE ===
CURRENT_BATTLE: BattleParty | None = None


def generate_battle_embed() -> discord.Embed:
    if not CURRENT_BATTLE:
        return discord.Embed(title="No Battle", description="No active battle.")

    embed = discord.Embed(
        title=f"{EMOJI_KAMI} Kami Battle - {CURRENT_BATTLE.mob.name}",
        description=CURRENT_BATTLE.mob.get_display(),
        color=discord.Color.dark_purple()
    )

    for player in CURRENT_BATTLE.players.values():
        embed.add_field(name=player.name, value=player.get_display(), inline=False)

    if CURRENT_BATTLE.is_finished():
        embed.set_footer(text="The battle has ended.")
    else:
        embed.set_footer(text="Choose your action wisely... Kami is watching.")
    
    return embed


class BattleView(View):
    def __init__(self, ctx, timeout=120):
        super().__init__(timeout=timeout)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if not CURRENT_BATTLE:
            await interaction.response.send_message("There is no active battle.", ephemeral=True)
            return False

        user = interaction.user
        player = CURRENT_BATTLE.get_player(user)

        if not player:
            await interaction.response.send_message("You are not in this battle.", ephemeral=True)
            return False

        if not player.is_alive():
            await interaction.response.send_message("You're currently KO'd. Wait for Kami's blessing.", ephemeral=True)
            return False

        if player.turn_taken:
            await interaction.response.send_message("You've already taken your turn!", ephemeral=True)
            return False

        return True

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.red)
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        player = CURRENT_BATTLE.get_player(user)

        dmg = player.deal_damage(random.randint(10, 20))
        dmg_dealt = CURRENT_BATTLE.mob.take_damage(dmg)
        player.last_action = f"{player.name} struck the enemy for **{dmg_dealt}** damage!"

        player.turn_taken = True
        await self.update_embed(interaction)

    @discord.ui.button(label="🛡️ Defend", style=discord.ButtonStyle.blurple)
    async def defend_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        player = CURRENT_BATTLE.get_player(user)
        player.defending = True
        player.turn_taken = True
        player.last_action = f"{player.name} is defending and taking reduced damage."

        await self.update_embed(interaction)

    @discord.ui.button(label="💊 Use Item", style=discord.ButtonStyle.green)
    async def item_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Item use not yet implemented.", ephemeral=True)

    @discord.ui.button(label="✨ Use Skill", style=discord.ButtonStyle.gray)
    async def skill_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Skill use not yet implemented.", ephemeral=True)

    async def update_embed(self, interaction: discord.Interaction):
        embed = generate_battle_embed()
        await interaction.response.edit_message(embed=embed, view=self)

        if CURRENT_BATTLE.all_players_ready():
            await asyncio.sleep(2)  # Delay for readability
            await run_mob_turn(self.ctx, self)

async def run_mob_turn(ctx, view: BattleView):
    global CURRENT_BATTLE
    if not CURRENT_BATTLE:
        return

    if CURRENT_BATTLE.is_finished():
        await end_battle(ctx, view)
        return

    actions = []
    mob = CURRENT_BATTLE.mob
    alive_players = CURRENT_BATTLE.alive_players()

    if not alive_players:
        await ctx.send("All players have fallen... Kami turns away.")
        await end_battle(ctx, view)
        return

    # Mob attacks one or more players
    targets = [p for p in alive_players if not p.defending]
    defenders = [p for p in alive_players if p.defending]

    if defenders:
        # Prioritize defenders
        if len(defenders) == 1:
            targets = [defenders[0]]
        else:
            targets = defenders

    # Deal mob damage
    mob_dmg = random.randint(12, 25)
    dmg_each = mob_dmg // len(targets)

    for target in targets:
        dmg_taken = target.take_damage(dmg_each)
        action_line = f"{mob.name} hits {target.name} for **{dmg_taken}** damage!"
        if dmg_taken == 0:
            action_line = f"{target.name} dodged {mob.name}'s attack!"
        elif not target.is_alive():
            action_line += f" {EMOJI_SKULL} They were KO'd!"
            target.revive()
            action_line += f" {EMOJI_KAMI} Revived by Kami with {target.hp} HP!"
        actions.append(action_line)

    # Reset players for next round
    CURRENT_BATTLE.reset_turns()

    # Send result
    embed = generate_battle_embed()
    embed.add_field(name="Mob's Turn", value="\n".join(actions), inline=False)

    if CURRENT_BATTLE.is_finished():
        await end_battle(ctx, view)
    else:
        await ctx.send(embed=embed, view=view)


async def end_battle(ctx, view: BattleView):
    global CURRENT_BATTLE
    if not CURRENT_BATTLE:
        return

    winner = "Players" if CURRENT_BATTLE.mob.hp <= 0 else "The Mob"
    end_embed = discord.Embed(
        title=f"{EMOJI_KAMI} Battle Over",
        description=f"**{winner} win the battle.**",
        color=discord.Color.gold() if winner == "Players" else discord.Color.red()
    )

    if CURRENT_BATTLE.mob.hp <= 0:
        reward = CURRENT_BATTLE.mob.reward
        end_embed.add_field(name="Rewards", value=f"{reward['xp']} XP\n{reward['gold']} Gold")

    view.clear_items()
    await ctx.send(embed=end_embed)

    CURRENT_BATTLE = None

class KamiAdventure(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

class KamiAdventure(commands.Cog):
    def __init__(self, bot, data_dir=None):
        self.bot = bot
        self.data_dir = data_dir or "data/kami"  # fallback path

    @commands.hybrid_command(name="battle", description="Begin a battle blessed by Kami.")
    async def battle(self, ctx):
        global CURRENT_BATTLE

        if CURRENT_BATTLE and not CURRENT_BATTLE.is_finished():
            if str(ctx.author.id) not in CURRENT_BATTLE.players:
                CURRENT_BATTLE.add_player(ctx.author)
                await ctx.send(f"{ctx.author.mention} has joined the battle!")
            else:
                await ctx.send("You're already in the battle!")
            embed = generate_battle_embed()
            await ctx.send(embed=embed)
            return

        # New battle
        mob_template = random.choice(list(MOBS.values()))
        CURRENT_BATTLE = BattleParty(mob_template)
        CURRENT_BATTLE.add_player(ctx.author)

        embed = generate_battle_embed()
        view = BattleView(ctx)

        await ctx.send(f"{ctx.author.mention} begins a battle!", embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(KamiAdventure(bot))

