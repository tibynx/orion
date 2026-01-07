"""Cog for moderation commands."""
from typing import Union
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from config import SUCCESS_EMOJI, ERROR_EMOJI


# Moderation commands
class Moderation(commands.Cog):
    """Cog for moderation-related commands."""
    def __init__(self, bot):
        """Initialize the cog with the bot instance."""
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
                discord.TextChannel, discord.VoiceChannel,
                discord.StageChannel
            ] = None
    ):
        """Purge a specified number of messages from a channel."""
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
                discord.TextChannel, discord.VoiceChannel,
                discord.StageChannel
            ] = None
    ):
        """Purge all pinned messages from a channel."""
        await interaction.response.defer(ephemeral=True) # Defer response
        try:
            if channel is None:
                channel = interaction.channel # Default to current channel
            pinned_messages = await channel.pins() # Get pinned messages
            delete_tasks = [message.delete() for message in pinned_messages]
            # Delete pinned messages concurrently
            results = await asyncio.gather(*delete_tasks, return_exceptions=True)
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            failed_count = len(results) - success_count
            message_text = f"{SUCCESS_EMOJI} Successfully purged {success_count} pinned messages."
            if failed_count:
                message_text += f" {failed_count} messages could not be deleted."
            await interaction.followup.send(
                message_text,
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I don't have permission to purge messages.",
                ephemeral=True
            )


    # Set slowmode for a channel
    @app_commands.command(
        name="slowmode",
        description="Set the slowmode for a channel. Defaults to the current channel."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.choices(duration=[
        discord.app_commands.Choice(name="off", value=0),
        discord.app_commands.Choice(name="3 seconds", value=3),
        discord.app_commands.Choice(name="5 seconds", value=5),
        discord.app_commands.Choice(name="10 seconds", value=10),
        discord.app_commands.Choice(name="15 seconds", value=15),
        discord.app_commands.Choice(name="30 seconds", value=30),
        discord.app_commands.Choice(name="1 minute", value=60),
        discord.app_commands.Choice(name="2 minutes", value=120),
        discord.app_commands.Choice(name="5 minutes", value=300),
        discord.app_commands.Choice(name="10 minutes", value=600),
        discord.app_commands.Choice(name="30 minutes", value=1800),
        discord.app_commands.Choice(name="1 hour", value=3600)
    ])
    @app_commands.describe(
        duration="The duration to set the slowmode to",
        channel="The channel to set slowmode for (optional)"
    )
    async def channel_slowmode(
            self, interaction: discord.Interaction,
            duration: discord.app_commands.Choice[int],
            channel: Union[
                discord.TextChannel, discord.VoiceChannel,
                discord.StageChannel
            ] = None
    ) -> None:
        """Set slowmode for a channel."""
        if channel is None:
            channel = interaction.channel
        try:
            await channel.edit(slowmode_delay=duration.value)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Channel slowmode set to: **{duration.name}**",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to set slowmode for this channel.",
                ephemeral=True
            )


async def setup(bot):
    """Add the Moderation cog to the bot."""
    await bot.add_cog(Moderation(bot))
