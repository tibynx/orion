from typing import Union
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from config import SUCCESS_EMOJI, ERROR_EMOJI


# TODO: Do pylint, and fix code


# Moderation commands
class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



    # Purge messages
    @app_commands.command(
        name="purge",
        description="Purge a number of messages from a channel."
    )
    # Requires manage messages permission
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    @app_commands.describe(
        number="The number of messages to purge.",
        channel="The channel to purge messages from. Defaults to the current channel."
    )
    async def purge_messages(
            self,
            interaction: discord.Interaction,
            number: app_commands.Range[int, 1, 1000],
            channel: Union[
                discord.TextChannel, discord.ForumChannel,
                discord.VoiceChannel, discord.StageChannel
            ] = None
    ):
        await interaction.response.defer(ephemeral=True)  # Defer response
        try:
            if channel is None:
                channel = interaction.channel # Default to current channel
            deleted = await channel.purge(limit=number) # Purge messages
            await interaction.followup.send(
                f"{SUCCESS_EMOJI} Successfully purged {len(deleted)} messages.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I don't have permission to purge messages.",
                ephemeral=True
            )
        except discord.HTTPException:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I cannot complete this command because of network issues. "
                "I might got rate limited. Please try again later.",
                ephemeral=True
            )


    # Delete only pinned messages
    @app_commands.command(
        name="purgepins",
        description="Purge all pinned messages from a channel."
    )
    # Requires manage messages permission
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def purge_pinned_messages(
            self,
            interaction: discord.Interaction,
            channel: Union[
                discord.TextChannel, discord.ForumChannel,
                discord.VoiceChannel, discord.StageChannel
            ] = None
    ):
        await interaction.response.defer(ephemeral=True) # Defer response
        try:
            if channel is None:
                channel = interaction.channel # Default to current channel
            pinned_messages = await channel.pins() # Get pinned messages
            delete_tasks = [message.delete() for message in pinned_messages]
            await asyncio.gather(*delete_tasks)  # Delete pinned messages concurrently
            await interaction.followup.send(
                f"{SUCCESS_EMOJI} Successfully purged {len(pinned_messages)} pinned messages.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I don't have permission to purge messages.",
                ephemeral=True
            )
        except discord.HTTPException:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I cannot complete this command because of network issues. "
                "I might got rate limited. Please try again later.",
                ephemeral=True
            )



async def setup(bot):
    await bot.add_cog(Moderation(bot))
