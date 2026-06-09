import discord
from discord import app_commands
from discord.ext import commands
import uuid

from data_manager import (
    load_players,
    save_players,
    get_embed_color,
)


class PlayerCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _autocomplete_players(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
        players = await load_players()
        return [
            app_commands.Choice(name=p["name"], value=p["name"])
            for p in players if current.lower() in p["name"].lower()
        ][:25]

    @app_commands.command(name="review", description="View a player's FIFA-style card")
    @app_commands.describe(player_name="Name of the player to review")
    @app_commands.autocomplete(player_name=_autocomplete_players)
    async def review(self, interaction: discord.Interaction, player_name: str):
        await interaction.response.defer()
        players = await load_players()
        match = None
        for p in players:
            if player_name.lower() in p["name"].lower():
                match = p
                break
        if match is None:
            embed = discord.Embed(
                title="❌ Player Not Found",
                description=f"No player found matching '{player_name}'.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        rating = match.get("rating", 50)
        color = get_embed_color(rating)
        club_name = "Free Agent"
        if match["club_id"]:
            from data_manager import get_club_by_id
            club = await get_club_by_id(match["club_id"])
            if club:
                club_name = club["name"]

        tier_emoji = ""
        if rating >= 85:
            tier_emoji = "💎"
        elif rating >= 75:
            tier_emoji = "🌟"
        elif rating >= 65:
            tier_emoji = "⭐"
        else:
            tier_emoji = "⚪"

        embed = discord.Embed(
            title=f"{match['name']} • {match['position']}",
            color=color,
        )
        embed.add_field(name="Club", value=club_name, inline=True)
        embed.add_field(name="Nationality", value=match.get("nationality", "Unknown"), inline=True)
        embed.add_field(name="Goals", value=str(match.get("goals", 0)), inline=True)
        embed.add_field(name="Assists", value=str(match.get("assists", 0)), inline=True)
        embed.add_field(
            name=f"Rating {tier_emoji}",
            value=f"**{rating}/99**",
            inline=False,
        )
        embed.set_footer(text="Ersha League • Powered by stats")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="leaderboard", description="Show top 10 players by a stat")
    @app_commands.describe(type="Stat to sort by: goals, assists, or rating")
    @app_commands.choices(type=[
        app_commands.Choice(name="goals", value="goals"),
        app_commands.Choice(name="assists", value="assists"),
        app_commands.Choice(name="rating", value="rating"),
    ])
    async def leaderboard(
        self, interaction: discord.Interaction, type: str = "rating"
    ):
        await interaction.response.defer()
        players = await load_players()
        sorted_players = sorted(
            players, key=lambda p: p.get(type, 0), reverse=True
        )[:10]

        color = 0xFFD700
        embed = discord.Embed(
            title=f"🏆 Leaderboard — Top 10 by {type.title()}",
            color=color,
        )

        for i, p in enumerate(sorted_players, 1):
            club_name = "Free Agent"
            if p["club_id"]:
                from data_manager import get_club_by_id
                club = await get_club_by_id(p["club_id"])
                if club:
                    club_name = club["name"]
            stat_value = p.get(type, 0)
            embed.add_field(
                name=f"{i}. {p['name']}",
                value=f"**{type.title()}:** {stat_value} | Club: {club_name}",
                inline=False,
            )

        embed.set_footer(text="Ersha League • Powered by stats")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="free_agents", description="List all free agent players")
    async def free_agents(self, interaction: discord.Interaction):
        await interaction.response.defer()
        players = await load_players()
        free = [p for p in players if p.get("club_id") is None]

        if not free:
            embed = discord.Embed(
                title="📋 Free Agents",
                description="No free agents available.",
                color=0xC0C0C0,
            )
            await interaction.followup.send(embed=embed)
            return

        embed = discord.Embed(
            title="📋 Free Agents",
            color=0xC0C0C0,
        )
        lines = []
        for p in free:
            rating = p.get("rating", 50)
            lines.append(
                f"**{p['name']}** | {p['position']} | Rating: {rating}/99"
            )
        embed.description = "\n".join(lines)
        embed.set_footer(text="Ersha League • Powered by stats")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="add_player", description="[Admin] Add a new player")
    @app_commands.describe(name="Player name", position="Position (e.g. ST, CM)", nationality="Nationality")
    async def add_player(
        self, interaction: discord.Interaction, name: str, position: str, nationality: str
    ):
        guild = interaction.guild
        is_owner = guild and guild.owner_id == interaction.user.id
        is_admin = False
        if guild:
            for role in interaction.user.roles:
                if role.name == "League Admin":
                    is_admin = True
                    break
        if not (is_owner or is_admin):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You must be the guild owner or have the 'League Admin' role.",
                color=0xFF4444,
            )
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer()
        players = await load_players()
        new_id = str(uuid.uuid4())[:8]
        new_player = {
            "id": new_id,
            "name": name,
            "discord_id": None,
            "club_id": None,
            "goals": 0,
            "assists": 0,
            "rating": 50,
            "position": position.upper(),
            "nationality": nationality,
        }
        players.append(new_player)
        await save_players(players)

        embed = discord.Embed(
            title="✅ Player Added",
            description=f"**{name}** ({position.upper()}, {nationality}) added as a free agent.",
            color=0x00FF88,
        )
        embed.set_footer(text="Ersha League • Powered by stats")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCommands(bot))
