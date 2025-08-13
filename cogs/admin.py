# cogs/admin.py
from __future__ import annotations

import traceback
from typing import Optional

from discord.ext import commands

KAMI_OWNER_ID: Optional[int] = None  # put your Discord user id here for owner checks (or keep None to use is_owner())

def is_kami_owner():
    async def predicate(ctx: commands.Context):
        if KAMI_OWNER_ID is not None:
            return ctx.author.id == KAMI_OWNER_ID
        return await ctx.bot.is_owner(ctx.author)
    return commands.check(predicate)

class Admin(commands.Cog, name="Admin"):
    """⚙️ Admin: utilities for Kami bot developers (reload, sync)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(brief="Reload a cog, e.g. `!reload music`", help="Reload a loaded extension. Example: `!reload music` or `!reload cogs.music`")
    @is_kami_owner()
    async def reload(self, ctx: commands.Context, module: str):
        mod = module if module.startswith("cogs.") else f"cogs.{module}"
        try:
            await self.bot.reload_extension(mod)
            await ctx.send(f"🔁 Reloaded `{mod}`. (If this was help text, try `!help` again)")
        except commands.ExtensionNotLoaded:
            try:
                await self.bot.load_extension(mod)
                await ctx.send(f"➕ Loaded `{mod}`.")
            except Exception:
                await ctx.send(f"❌ Failed to load `{mod}`:\n```py\n{traceback.format_exc()}\n```")
        except Exception:
            await ctx.send(f"❌ Failed to reload `{mod}`:\n```py\n{traceback.format_exc()}\n```")

    @commands.command(brief="Sync slash commands", help="Sync application commands to this guild.")
    @is_kami_owner()
    async def sync(self, ctx: commands.Context):
        await self.bot.tree.sync(guild=ctx.guild)
        await ctx.send("✅ Synced application commands for this guild.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
