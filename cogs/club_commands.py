import discord
from discord import app_commands
from discord.ext import commands

from data_manager import (
    load_players,
    load_clubs,
    save_clubs,
    get_club_by_owner,
    get_club_by_id,
    get_player_by_id,
    add_player_to_club,
    remove_player_from_club,
)


class ClubCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_owner_club(self, interaction: discord.Interaction):
        return await get_club_by_owner(str(interaction.user.id))

    async def _autocomplete_clubs(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
        clubs = await load_clubs()
        return [
            app_commands.Choice(name=c["name"], value=c["name"])
            for c in clubs if current.lower() in c["name"].lower()
        ][:25]

    async def _autocomplete_free_agents(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
        players = await load_players()
        free = [p for p in players if p.get("club_id") is None]
        return [
            app_commands.Choice(name=p["name"], value=p["name"])
            for p in free if current.lower() in p["name"].lower()
        ][:25]

    async def _autocomplete_my_players(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
        club = await self._get_owner_club(interaction)
        if not club:
            return []
        players = await load_players()
        mine = [p for p in players if p.get("club_id") == club["id"]]
        return [
            app_commands.Choice(name=p["name"], value=p["name"])
            for p in mine if current.lower() in p["name"].lower()
        ][:25]

    @app_commands.command(name="club", description="View a club's info")
    @app_commands.describe(club_name="Name of the club")
    @app_commands.autocomplete(club_name=_autocomplete_clubs)
    async def club(self, interaction: discord.Interaction, club_name: str):
        await interaction.response.defer()
        clubs = await load_clubs()
        match = None
        for c in clubs:
            if club_name.lower() in c["name"].lower():
                match = c
                break
        if match is None:
            embed = discord.Embed(
                title="❌ Club Not Found",
                description=f"No club found matching '{club_name}'.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        players = await load_players()
        squad_lines = []
        for pid in match.get("players", []):
            p = await get_player_by_id(pid)
            if p:
                rating = p.get("rating", 50)
                squad_lines.append(
                    f"**{p['name']}** — {p['position']} — *Rating:* {rating}/99"
                )

        embed = discord.Embed(
            title=f"🏛️ {match['name']}",
            color=0xFFD700,
        )
        embed.add_field(name="Budget", value=f"💰 {match.get('budget', 0):,}", inline=True)
        embed.add_field(name="Squad Size", value=str(len(squad_lines)), inline=True)
        owner_mention = f"<@{match['owner_discord_id']}>" if match["owner_discord_id"] and match["owner_discord_id"] not in (
            "OWNER_1_ID", "OWNER_2_ID"
        ) else "Owner not set"
        embed.add_field(name="Owner", value=owner_mention, inline=False)
        if squad_lines:
            embed.add_field(
                name="Squad",
                value="\n".join(squad_lines),
                inline=False,
            )
        embed.set_footer(text="Ersha League • Powered by stats")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="myclub", description="View your own club")
    async def myclub(self, interaction: discord.Interaction):
        await interaction.response.defer()
        club = await self._get_owner_club(interaction)
        if club is None:
            embed = discord.Embed(
                title="❌ No Club Found",
                description="You are not registered as a club owner.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        players = await load_players()
        squad_lines = []
        for pid in club.get("players", []):
            p = await get_player_by_id(pid)
            if p:
                rating = p.get("rating", 50)
                squad_lines.append(
                    f"**{p['name']}** — {p['position']} — *Rating:* {rating}/99"
                )

        embed = discord.Embed(
            title=f"🏛️ {club['name']} — Your Club",
            color=0xFFD700,
        )
        embed.add_field(name="Budget", value=f"💰 {club.get('budget', 0):,}", inline=True)
        embed.add_field(name="Squad Size", value=str(len(squad_lines)), inline=True)
        if squad_lines:
            embed.add_field(
                name="Squad",
                value="\n".join(squad_lines),
                inline=False,
            )
        embed.set_footer(text="Ersha League • Powered by stats")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="buy", description="Buy a free agent for your club")
    @app_commands.describe(player_name="Name of the player to buy")
    @app_commands.autocomplete(player_name=_autocomplete_free_agents)
    async def buy(self, interaction: discord.Interaction, player_name: str):
        await interaction.response.defer()
        club = await self._get_owner_club(interaction)
        if club is None:
            embed = discord.Embed(
                title="❌ Not a Club Owner",
                description="You are not registered as a club owner.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

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

        if match["club_id"] is not None:
            embed = discord.Embed(
                title="❌ Transfer Denied",
                description="You must negotiate a sale with the other club owner.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        rating = match.get("rating", 50)
        fee = rating * 1000
        if club["budget"] < fee:
            embed = discord.Embed(
                title="❌ Insufficient Budget",
                description=f"Transfer fee is **{fee:,}** but your club only has **{club['budget']:,}**.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        clubs = await load_clubs()
        for c in clubs:
            if c["id"] == club["id"]:
                c["budget"] -= fee
                break
        await save_clubs(clubs)

        await add_player_to_club(club["id"], match["id"])

        embed = discord.Embed(
            title="✅ Transfer Complete",
            description=f"**{match['name']}** signed for **{club['name']}** — Fee: **{fee:,}**",
            color=0x00FF88,
        )
        embed.set_footer(text="Ersha League • Powered by stats")
        await interaction.followup.send(embed=embed)

    async def _sell_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
        return await self._autocomplete_my_players(interaction, current)

    @app_commands.command(name="sell", description="Release a player from your club")
    @app_commands.describe(player_name="Name of the player to sell/release")
    @app_commands.autocomplete(player_name=_sell_autocomplete)
    async def sell(self, interaction: discord.Interaction, player_name: str):
        await interaction.response.defer()
        club = await self._get_owner_club(interaction)
        if club is None:
            embed = discord.Embed(
                title="❌ Not a Club Owner",
                description="You are not registered as a club owner.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        players = await load_players()
        match = None
        for p in players:
            if player_name.lower() in p["name"].lower() and p.get("club_id") == club["id"]:
                match = p
                break
        if match is None:
            embed = discord.Embed(
                title="❌ Player Not Found",
                description=f"No player named '{player_name}' found in your club.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        rating = match.get("rating", 50)
        refund = (rating * 1000) // 2

        clubs = await load_clubs()
        for c in clubs:
            if c["id"] == club["id"]:
                c["budget"] += refund
                break
        await save_clubs(clubs)

        await remove_player_from_club(match["id"])

        embed = discord.Embed(
            title="✅ Player Released",
            description=f"**{match['name']}** released from **{club['name']}**. **{refund:,}** refunded to budget.",
            color=0x00FF88,
        )
        embed.set_footer(text="Ersha League • Powered by stats")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ClubCommands(bot))
