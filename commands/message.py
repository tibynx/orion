from typing import Union

import discord
from discord.ext import commands
from discord import app_commands

from config import SUCCESS_EMOJI, ERROR_EMOJI


# TODO: Do pylint, and fix code
# TODO: Add more comments


class MessageModal(discord.ui.Modal):
    def __init__(self, channel: discord.abc.Messageable):
        super().__init__(title=f"Message #{channel.name}", timeout=600)
        self.channel = channel

    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send",
        max_length=2000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await self.channel.send(self.message.value)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Message sent successfully in {self.channel.mention}!",
            ephemeral=True
        )

    async def on_timeout(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"{ERROR_EMOJI} Modal timed out. Please try again.",
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message(
            f"{ERROR_EMOJI} An error occurred while sending the message: `{str(error).capitalize()}`",
            ephemeral=True
        )


class Message(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(
        name="msg",
        description="Send a message."
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(
        channel="The channel to send the message in."
    )
    async def send_message_modal(
        self,
        interaction: discord.Interaction,
        channel: Union[discord.TextChannel, discord.Thread, discord.StageChannel, discord.VoiceChannel],
    ):
        await interaction.response.send_modal(MessageModal(channel))



async def setup(bot):
    await bot.add_cog(Message(bot))