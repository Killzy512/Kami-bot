# cogs/music.py
from __future__ import annotations

from typing import Dict, List, Optional

import discord
from discord.ext import commands
import wavelink

MAX_QUEUE_SIZE = 100  # per-guild queue cap


class Music(commands.Cog, name="Music"):
    """
    🎵 Kami Music: queue & play tracks in voice using Lavalink/Wavelink.

    Voice:
      • join      – Kami DJ joins your voice channel.
      • leave     – Kami DJ leaves voice.

    Playback:
      • play      – Play by URL or search. Queues if something’s already playing.
      • now       – Show the current track.
      • pause     – Pause playback.
      • resume    – Resume playback.
      • stop      – Stop playback.
      • skip      – Skip the current track.

    Queue:
      • queue (q) – Show the next 10 items.
      • clear     – Clear the queue.

    Node:
      • node      – Lavalink node status.
      • reconnect – Force reconnect the Lavalink pool (dev/admin).

    Tips:
      • Use `!play lofi hip hop` or paste a YouTube URL.
      • Spotify links aren’t supported by this cog; use search/YouTube instead.
      • Queue cap per guild: 100 items.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queues: Dict[int, List[wavelink.Playable]] = {}

    # ---------- helpers ----------
    def _q(self, gid: int) -> List[wavelink.Playable]:
        return self.queues.setdefault(gid, [])

    async def _ensure_connected(self, ctx: commands.Context) -> Optional[wavelink.Player]:
        """Connect to the author's voice channel if needed and return the player."""
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            return vc

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("🔊 Join a voice channel first so **Kami DJ** knows where to spin!")
            return None

        try:
            vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)  # type: ignore
            await ctx.send("🎧 **Kami DJ** connected. Time to vibe!")
            return vc  # type: ignore
        except Exception as e:
            await ctx.send(f"❌ Couldn’t join voice: `{e!r}`")
            return None

    def _tracks_from_results(self, results) -> List[wavelink.Playable]:
        """Flatten Wavelink search results into a list of tracks."""
        tracks: List[wavelink.Playable] = []
        if not results:
            return tracks

        # results can be a single track, a list of tracks, or a playlist-like object with .tracks
        if isinstance(results, (list, tuple)):
            for r in results:
                if hasattr(r, "tracks"):
                    tracks.extend(r.tracks)
                else:
                    tracks.append(r)
        else:
            if hasattr(results, "tracks"):
                tracks.extend(results.tracks)
            else:
                tracks.append(results)
        return tracks

    # ---------- commands ----------
    @commands.command(
        help="Join your voice channel. If not already connected, Kami DJ hops in."
    )
    async def join(self, ctx: commands.Context):
        """Join your voice channel."""
        await self._ensure_connected(ctx)

    @commands.command(
        help="Leave voice and clear any player state. Bye from Kami DJ! 👋"
    )
    async def leave(self, ctx: commands.Context):
        """Leave voice."""
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.disconnect()
            await ctx.send("🪄 Left voice. **Kami DJ** out!")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(
        help=(
            "Play a track by URL or search (YouTube). If something is already playing, "
            "Kami queues the top match. Tip: try `!play lofi hip hop`."
        )
    )
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a track (search or URL). Queues only one top match when already playing."""
        vc = await self._ensure_connected(ctx)
        if not vc:
            return

        if query.startswith(("https://open.spotify.com/", "http://open.spotify.com/")):
            return await ctx.send("⚠️ Spotify links aren’t supported here. Try a YouTube link or a search term.")

        is_url = query.startswith(("http://", "https://"))
        try:
            if is_url:
                results = await wavelink.Playable.search(query)
            else:
                yt_src = getattr(wavelink.TrackSource, "YouTube", None) or getattr(wavelink.TrackSource, "YOUTUBE", None)
                if yt_src:
                    results = await wavelink.Playable.search(query, source=yt_src)
                else:
                    results = await wavelink.Playable.search(query)

            tracks = self._tracks_from_results(results)
            if not tracks:
                return await ctx.send("🔍 No tracks found. Try different keywords, Nakama!")

            # If nothing is currently playing, try to start the first playable one.
            if not getattr(vc, "playing", False) and not getattr(vc, "paused", False):
                last_err: Exception | None = None
                for t in tracks:
                    try:
                        await vc.play(t)
                        title = getattr(t, "title", "Unknown Title")
                        uri = getattr(t, "uri", None)
                        pretty = f"**{title}**" + (f" <{uri}>" if uri else "")
                        await ctx.send(f"▶️ Now playing: {pretty} | Powered by **Kami Radio** 📡")
                        break
                    except Exception as e:
                        last_err = e
                        continue
                else:
                    return await ctx.send(f"❌ Couldn’t start any result: `{last_err!r}`")
            else:
                # Already playing -> queue only the top match
                top = tracks[0]
                q = self._q(ctx.guild.id)
                if len(q) >= MAX_QUEUE_SIZE:
                    return await ctx.send(f"📦 Queue is full (max {MAX_QUEUE_SIZE}).")
                q.append(top)
                title = getattr(top, "title", "Unknown Title")
                await ctx.send(f"➕ Queued: **{title}** • Your Kami playlist grows!")

        except Exception as e:
            await ctx.send(f"❌ Search error: `{e!r}`")

    @commands.command(aliases=["q"],
        help="Show the upcoming queue (first 10). Use `!clear` to wipe the queue."
    )
    async def queue(self, ctx: commands.Context):
        """Show the upcoming queue (first 10)."""
        q = self._q(ctx.guild.id)
        if not q:
            return await ctx.send("📭 Queue is empty. Use `!play <query>` to summon tunes.")
        lines = []
        for i, t in enumerate(q[:10], start=1):
            title = getattr(t, "title", "Unknown Title")
            lines.append(f"{i}. {title}")
        extra = f"\n…and **{len(q)-10}** more in the Kami queue." if len(q) > 10 else ""
        await ctx.send("**🎼 Upcoming:**\n" + "\n".join(lines) + extra)

    @commands.command(aliases=["np", "curr", "playing"],
        help="Show the current track (Now Playing) as spun by Kami DJ."
    )
    async def now(self, ctx: commands.Context):
        """Show the current track."""
        vc = ctx.voice_client
        if not isinstance(vc, wavelink.Player) or not getattr(vc, "current", None):
            return await ctx.send("⏹️ Nothing is playing.")
        t = vc.current
        title = getattr(t, "title", "Unknown Title")
        uri = getattr(t, "uri", None)
        pretty = f"**{title}**" + (f" <{uri}>" if uri else "")
        await ctx.send(f"🎶 Now playing: {pretty}")

    @commands.command(help="Pause playback. Use `!resume` to continue.")
    async def pause(self, ctx: commands.Context):
        """Pause playback."""
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.pause()
            await ctx.send("⏸️ Paused. Kami DJ is catching a breath.")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(help="Resume playback if paused.")
    async def resume(self, ctx: commands.Context):
        """Resume playback."""
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.resume()
            await ctx.send("▶️ Resumed. Kami vibes restored.")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(help="Stop playback and keep the queue intact.")
    async def stop(self, ctx: commands.Context):
        """Stop playback."""
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.stop()
            await ctx.send("⏹️ Stopped.")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(name="skip", aliases=["next"],
        help="Skip the current track. Kami jumps to what’s next."
    )
    async def skip_song(self, ctx: commands.Context):
        """Skip the current track."""
        vc = ctx.voice_client
        if isinstance(vc, wavelink.Player):
            await vc.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("⚠️ Not connected.")

    @commands.command(help="Clear the upcoming queue (doesn’t stop the current track).")
    async def clear(self, ctx: commands.Context):
        """Clear the upcoming queue."""
        q = self._q(ctx.guild.id)
        n = len(q)
        q.clear()
        await ctx.send(f"🧹 Cleared **{n}** queued track(s). The Kami deck is fresh.")

    @commands.command(
        help="Show Lavalink node status (useful for diagnostics)."
    )
    async def node(self, ctx: commands.Context):
        """Show Lavalink node status."""
        pool = getattr(wavelink, "Pool", None)
        if pool and pool.nodes:
            n = list(pool.nodes.values())[0]
            return await ctx.send(f"🛰️ Node status: **{n.status.name}**")
        await ctx.send("❓ No nodes in pool. Is Lavalink up?")

    @commands.command(
        help="Force reconnect to Lavalink (dev/admin). The bot’s setup handles the actual reconnect."
    )
    async def reconnect(self, ctx: commands.Context):
        """Force reconnect to Lavalink node."""
        pool = getattr(wavelink, "Pool", None)
        if pool:
            try:
                for n in list(pool.nodes.values()):
                    await n.disconnect()
            except Exception:
                pass
        if hasattr(self.bot, "_connect_lavalink_retry"):
            self.bot.loop.create_task(self.bot._connect_lavalink_retry())  # type: ignore
        await ctx.send("🔁 Reconnecting to Lavalink… Kami techs on it!")

    # ---------- events ----------
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, event):
        """Auto-play next item when a track ends."""
        try:
            player: wavelink.Player = event.player  # type: ignore
        except Exception:
            player = getattr(event, "player", None)
        if not player:
            return
        q = self._q(player.guild.id)
        if q:
            next_track = q.pop(0)
            try:
                await player.play(next_track)
            except Exception:
                # If a queued track fails, try the next one silently
                while q:
                    nt = q.pop(0)
                    try:
                        await player.play(nt)
                        break
                    except Exception:
                        continue

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
