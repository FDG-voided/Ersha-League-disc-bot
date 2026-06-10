import discord
from discord import app_commands
from discord.ext import commands
from uuid import uuid4
from datetime import datetime

import config
from data_manager import (
    load_players,
    load_clubs,
    save_clubs,
    load_pending_offers,
    save_pending_offers,
    get_club_by_owner,
    get_club_by_id,
    get_player_by_id,
    transfer_player,
)


class TransferView(discord.ui.View):
    def __init__(self, offer: dict, target_id: int):
        super().__init__(timeout=None)
        self.offer = offer
        self.target_id = target_id

    async def _get_offer_from_store(self):
        offers = await load_pending_offers()
        for o in offers:
            if o["player_id"] == self.offer["player_id"] and o["to_owner_id"] == str(self.target_id):
                return o
        return None

    async def _remove_offer_from_store(self):
        offers = await load_pending_offers()
        offers[:] = [o for o in offers if not (o["player_id"] == self.offer["player_id"] and o["to_owner_id"] == str(self.target_id))]
        await save_pending_offers(offers)

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ This offer is not for you.", ephemeral=True)
            return

        offer = await self._get_offer_from_store()
        if offer is None:
            await interaction.response.send_message("❌ This offer is no longer pending.", ephemeral=True)
            return

        seller_club = await get_club_by_owner(str(interaction.user.id))
        if seller_club is None:
            await interaction.response.send_message("❌ You are not a club owner.", ephemeral=True)
            return

        player = await get_player_by_id(offer["player_id"])
        if player is None:
            await interaction.response.send_message("❌ Player no longer exists.", ephemeral=True)
            return

        buyer_club = await get_club_by_id(offer["from_club_id"])
        if buyer_club is None:
            await interaction.response.send_message("❌ Buyer club no longer exists.", ephemeral=True)
            return

        fee = offer["amount"]

        if buyer_club["funds"] < fee:
            await interaction.response.send_message(f"❌ {buyer_club['name']} no longer has enough funds. They need **{fee:,}** but only have **{buyer_club['funds']:,}**.", ephemeral=True)
            return

        clubs = await load_clubs()
        for c in clubs:
            if c["id"] == buyer_club["id"]:
                c["funds"] -= fee
            if c["id"] == seller_club["id"]:
                c["funds"] += fee
        await save_clubs(clubs)

        await transfer_player(player["id"], buyer_club["id"])
        await self._remove_offer_from_store()

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        embed = discord.Embed(
            title="✅ Transfer Completed",
            description=(
                f"**{player['name']}** has been transferred!\n\n"
                f"**From:** {seller_club['name']}\n"
                f"**To:** {buyer_club['name']}\n"
                f"**Fee:** {fee:,}"
            ),
            color=0x00FF88,
        )
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ This offer is not for you.", ephemeral=True)
            return

        offer = await self._get_offer_from_store()
        if offer is None:
            await interaction.response.send_message("❌ This offer is no longer pending.", ephemeral=True)
            return

        await self._remove_offer_from_store()

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        embed = discord.Embed(
            title="❌ Offer Rejected",
            description=f"The offer for **{offer['player_name']}** from **{offer['from_club_name']}** has been rejected.",
            color=0xFF4444,
        )
        await interaction.followup.send(embed=embed)


class TransferCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_owner_club(self, interaction: discord.Interaction):
        return await get_club_by_owner(str(interaction.user.id))

    async def _other_players_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
        club = await get_club_by_owner(str(interaction.user.id))
        if not club:
            return []
        players = await load_players()
        others = [p for p in players if p.get("club_id") is not None and p["club_id"] != club["id"]]
        return [
            app_commands.Choice(name=p["name"], value=p["name"])
            for p in others if current.lower() in p["name"].lower()
        ][:25]

    async def _offer_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
        return await self._other_players_autocomplete(interaction, current)

    async def _accept_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
        club = await get_club_by_owner(str(interaction.user.id))
        if not club:
            return []
        offers = await load_pending_offers()
        mine = [o for o in offers if o["to_club_id"] == club["id"]]
        return [
            app_commands.Choice(name=o["player_name"], value=o["player_name"])
            for o in mine if current.lower() in o["player_name"].lower()
        ][:25]

    async def _reject_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
        return await self._accept_autocomplete(interaction, current)

    @app_commands.command(name="offer", description="Offer a transfer to another club owner")
    @app_commands.describe(player_name="Name of the player", target_owner="The other club owner", fee="Transfer fee")
    @app_commands.autocomplete(player_name=_offer_autocomplete)
    async def offer(
        self, interaction: discord.Interaction, player_name: str, target_owner: discord.Member, fee: int
    ):
        await interaction.response.defer()
        from_club = await self._get_owner_club(interaction)
        if from_club is None:
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

        if match.get("club_id") is None:
            embed = discord.Embed(
                title="❌ Free Agent",
                description=f"**{match['name']}** is a free agent. Use `/buy` to sign them.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        if match["club_id"] == from_club["id"]:
            embed = discord.Embed(
                title="❌ Your Own Player",
                description=f"**{match['name']}** is already in your club.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        to_club = await get_club_by_id(match["club_id"])
        if to_club is None:
            embed = discord.Embed(
                title="❌ Club Not Found",
                description="The player's club no longer exists.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        if str(target_owner.id) != to_club["owner_discord_id"]:
            embed = discord.Embed(
                title="❌ Wrong Owner",
                description=f"**{match['name']}** is in **{to_club['name']}**, which is owned by <@{to_club['owner_discord_id']}>, not {target_owner.mention}.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        if fee <= 0:
            embed = discord.Embed(
                title="❌ Invalid Fee",
                description="Fee must be a positive number.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        if from_club["funds"] < fee:
            embed = discord.Embed(
                title="❌ Insufficient Budget",
                description=f"Your club only has **{from_club['funds']:,}** funds.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        offer_data = {
            "id": str(uuid4()),
            "player_id": match["id"],
            "player_name": match["name"],
            "from_club_id": from_club["id"],
            "from_club_name": from_club["name"],
            "to_club_id": to_club["id"],
            "to_club_name": to_club["name"],
            "to_owner_id": str(target_owner.id),
            "amount": fee,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }

        offers = await load_pending_offers()
        offers.append(offer_data)
        await save_pending_offers(offers)

        embed = discord.Embed(
            title="📨 Offer Sent",
            description=f"Offer for **{match['name']}** sent to **{to_club['name']}** for **{fee:,}**.",
            color=0x00CED1,
        )
        await interaction.followup.send(embed=embed)

        channel_id = config.TRANSFER_CHANNEL_ID
        if channel_id:
            channel = self.bot.get_channel(int(channel_id))
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(int(channel_id))
                except Exception:
                    pass
            if channel:
                view = TransferView(offer_data, target_owner.id)
                channel_embed = discord.Embed(
                    title="🔁 Transfer Offer Received",
                    description=(
                        f"**{from_club['name']}** wants to buy **{match['name']}** for **{fee:,}**.\n\n"
                        f"**From:** {interaction.user.mention}\n"
                        f"**To:** {target_owner.mention}\n\n"
                        f"{target_owner.mention} — use the buttons below to respond."
                    ),
                    color=0x00CED1,
                )
                try:
                    await channel.send(embed=channel_embed, view=view)
                except discord.Forbidden:
                    await interaction.followup.send("⚠️ I don't have permission to send messages in the transfer channel.", ephemeral=True)
                except discord.HTTPException as e:
                    await interaction.followup.send(f"⚠️ Failed to post offer to channel: {e}", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Transfer channel not found. Check TRANSFER_CHANNEL_ID in .env.", ephemeral=True)

    @app_commands.command(name="accept_offer", description="Accept a pending transfer offer")
    @app_commands.describe(player_name="Name of the player in the offer")
    @app_commands.autocomplete(player_name=_accept_autocomplete)
    async def accept_offer(self, interaction: discord.Interaction, player_name: str):
        await interaction.response.defer()
        seller_club = await self._get_owner_club(interaction)
        if seller_club is None:
            embed = discord.Embed(
                title="❌ Not a Club Owner",
                description="You are not registered as a club owner.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        offers = await load_pending_offers()
        offer = None
        for o in offers:
            if player_name.lower() in o["player_name"].lower() and o["to_club_id"] == seller_club["id"]:
                offer = o
                break

        if offer is None:
            embed = discord.Embed(
                title="❌ No Offer Found",
                description=f"No pending offer for '{player_name}' addressed to your club.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        player = await get_player_by_id(offer["player_id"])
        if player is None:
            embed = discord.Embed(
                title="❌ Player Not Found",
                description="The player in this offer no longer exists.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        buyer_club = await get_club_by_id(offer["from_club_id"])
        if buyer_club is None:
            embed = discord.Embed(
                title="❌ Buyer Club Not Found",
                description="The buying club no longer exists.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        fee = offer["amount"]

        if buyer_club["funds"] < fee:
            embed = discord.Embed(
                title="❌ Buyer Insufficient Budget",
                description=f"**{buyer_club['name']}** needs **{fee:,}** but only has **{buyer_club['funds']:,}**.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        clubs = await load_clubs()
        for c in clubs:
            if c["id"] == buyer_club["id"]:
                c["funds"] -= fee
            if c["id"] == seller_club["id"]:
                c["funds"] += fee
        await save_clubs(clubs)

        await transfer_player(player["id"], buyer_club["id"])

        offers.remove(offer)
        await save_pending_offers(offers)

        embed = discord.Embed(
            title="✅ Transfer Completed",
            description=(
                f"**{player['name']}** has been transferred!\n\n"
                f"**From:** {seller_club['name']}\n"
                f"**To:** {buyer_club['name']}\n"
                f"**Fee:** {fee:,}"
            ),
            color=0x00FF88,
        )
        embed.set_footer(text="Ersha League • Powered by stats")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="reject_offer", description="Reject a pending transfer offer")
    @app_commands.describe(player_name="Name of the player in the offer")
    @app_commands.autocomplete(player_name=_reject_autocomplete)
    async def reject_offer(self, interaction: discord.Interaction, player_name: str):
        await interaction.response.defer()
        to_club = await self._get_owner_club(interaction)
        if to_club is None:
            embed = discord.Embed(
                title="❌ Not a Club Owner",
                description="You are not registered as a club owner.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        offers = await load_pending_offers()
        offer = None
        for o in offers:
            if player_name.lower() in o["player_name"].lower() and o["to_club_id"] == to_club["id"]:
                offer = o
                break

        if offer is None:
            embed = discord.Embed(
                title="❌ No Offer Found",
                description=f"No pending offer for '{player_name}' addressed to your club.",
                color=0xFF4444,
            )
            await interaction.followup.send(embed=embed)
            return

        offers.remove(offer)
        await save_pending_offers(offers)

        embed = discord.Embed(
            title="❌ Offer Rejected",
            description=f"The offer for **{offer['player_name']}** from **{offer['from_club_name']}** has been rejected.",
            color=0xFF4444,
        )
        await interaction.followup.send(embed=embed)

        if offer.get("from_club_id"):
            clubs = await load_clubs()
            for c in clubs:
                if c["id"] == offer["from_club_id"]:
                    embed2 = discord.Embed(
                        title="📨 Offer Rejected",
                        description=f"Your offer for **{offer['player_name']}** was rejected by **{to_club['name']}**.",
                        color=0xFFAA00,
                    )
                    await interaction.followup.send(embed=embed2)
                    break


async def setup(bot: commands.Bot):
    await bot.add_cog(TransferCommands(bot))
