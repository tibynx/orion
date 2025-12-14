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


class DmModal(discord.ui.Modal):
    def __init__(self, user: discord.User):
        super().__init__(title=f"Message {user.name}", timeout=600)
        self.user = user

    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send",
        max_length=2000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await self.user.send(self.message.value)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Direct message sent successfully to {self.user.mention}!",
            ephemeral=True
        )

    async def on_timeout(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"{ERROR_EMOJI} Modal timed out. Please try again.",
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if isinstance(error, discord.Forbidden):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Cannot send direct message to {self.user.mention}. They might have DMs disabled.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} An error occurred while sending the direct message: `{str(error).capitalize()}`",
                ephemeral=True
            )


class ReplyModal(discord.ui.Modal):
    def __init__(self, message: discord.Message):
        super().__init__(title=f"Reply to {message.author.name}", timeout=600)
        self.message = message

    reply_message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send",
        max_length=2000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await self.message.reply(self.reply_message.value)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Reply sent to {self.message.author.mention} successfully!",
            ephemeral=True
        )

    async def on_timeout(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"{ERROR_EMOJI} Modal timed out. Please try again.",
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message(
            f"{ERROR_EMOJI} An error occurred while sending the reply: `{str(error).capitalize()}`",
            ephemeral=True
        )

class Message(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reply_command = app_commands.ContextMenu(
            name="Reply",
            callback=self.reply_command_callback
        )
        self.bot.tree.add_command(self.reply_command)


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


    # Send a direct message to a user
    @app_commands.command(
        name="dm",
        description="Send a direct message to a user."
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(
        user="The user to send the direct message to."
    )
    async def send_dm_modal(
        self,
        interaction: discord.Interaction,
        user: discord.User,
    ):
        await interaction.response.send_modal(DmModal(user))


    # Callback for the reply context menu command
    async def reply_command_callback(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.send_modal(ReplyModal(message))



async def setup(bot):
    await bot.add_cog(Message(bot))