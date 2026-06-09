import discord
from discord.ext import commands
import config
from data_manager import recalculate_player_ratings


class ErshaLeagueBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.load_extension("cogs.player_commands")
        await self.load_extension("cogs.club_commands")
        await self.load_extension("cogs.transfer_commands")

        guild_id = config.GUILD_ID
        if guild_id:
            try:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            except Exception as e:
                print(f"Warning: Could not sync guild commands: {e}")

        await self.tree.sync()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        print(f"🌐 Connected to {len(self.guilds)} guild(s)")
        await recalculate_player_ratings()
        print("📊 Player ratings recalculated on startup.")


if __name__ == "__main__":
    bot = ErshaLeagueBot()
    token = config.TOKEN
    if not token or token == "your_discord_bot_token_here":
        print("❌ ERROR: No bot token found. Check your .env file.")
    else:
        bot.run(token)
