from typing import Union
import discord
from discord.ext import commands
from discord import app_commands
from config import SUCCESS_EMOJI, ERROR_EMOJI


# TODO: Do pylint, and fix code


# Modal for sending a message in a channel
class MessageModal(discord.ui.Modal):
    def __init__(self, channel: discord.abc.Messageable):
        super().__init__(title=f"Message #{channel.name}", timeout=600) # 10-minute timeout
        self.channel = channel

    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send",
        max_length=2000, # Discord's message character limit
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await self.channel.send(self.message.value)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Message sent successfully in {self.channel.mention}!",
            ephemeral=True
        )
    async def on_timeout(self, interaction: discord.Interaction) -> None: # Intentional timeout to avoid errors
        await interaction.response.send_message(
            f"{ERROR_EMOJI} Modal timed out. Please try again.",
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message(
            f"{ERROR_EMOJI} An error occurred while sending the message: `{str(error).capitalize()}`",
            ephemeral=True
        )


# Modal for sending a direct message to a user
class DmModal(discord.ui.Modal):
    def __init__(self, user: discord.User):
        super().__init__(title=f"Message {user.name}", timeout=600) # 10-minute timeout
        self.user = user

    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send",
        max_length=2000, # Discord's message character limit
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await self.user.send(self.message.value)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Direct message sent successfully to {self.user.mention}!",
            ephemeral=True
        )
    async def on_timeout(self, interaction: discord.Interaction) -> None: # Intentional timeout to avoid errors
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


# Modal for replying to a message
class ReplyModal(discord.ui.Modal):
    def __init__(self, message: discord.Message):
        super().__init__(title=f"Reply to {message.author.name}", timeout=600) # 10-minute timeout
        self.message = message

    reply_message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send",
        max_length=2000, # Discord's message character limit
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await self.message.reply(self.reply_message.value)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Reply sent to {self.message.author.mention} successfully!",
            ephemeral=True
        )
    async def on_timeout(self, interaction: discord.Interaction) -> None: # Intentional timeout to avoid errors
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

        # Context menu command for replying to a message
        self.reply_command = app_commands.ContextMenu(
            name="Reply to Message",
            callback=self.reply_command_callback
        )
        self.bot.tree.add_command(self.reply_command)

        # User command for sending a direct message
        self.dm_command = app_commands.ContextMenu(
            name="Send Direct Message",
            callback=self.dm_command_callback
        )
        self.bot.tree.add_command(self.dm_command)



    # Send a message in a specified channel
    @app_commands.command(
        name="msg",
        description="Send a message."
    )
    @app_commands.default_permissions(manage_messages=True) # Requires manage messages permission
    @app_commands.guild_only()
    @app_commands.describe(
        channel="The channel to send the message in."
    )
    async def send_message_modal(
        self,
        interaction: discord.Interaction,
        channel: Union[discord.TextChannel, discord.Thread, discord.StageChannel, discord.VoiceChannel],
    ):
        await interaction.response.send_modal(MessageModal(channel)) # Send the message modal


    # Send a direct message to a user
    @app_commands.command(
        name="dm",
        description="Send a direct message to a user."
    )
    @app_commands.default_permissions(manage_guild=True) # Requires manage guild permission
    @app_commands.guild_only()
    @app_commands.describe(
        user="The user to send the direct message to."
    )
    async def send_dm_modal(
        self,
        interaction: discord.Interaction,
        user: discord.User,
    ):
        if user == self.bot.user:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I cannot send a direct message to myself!",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(DmModal(user)) # Send the DM modal


    # Callback for the reply context menu command
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True) # Requires manage guild permission
    async def reply_command_callback(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.send_modal(ReplyModal(message)) # Send the reply modal


    # Callback for the send DM user command
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True) # Requires manage guild permission
    async def dm_command_callback(self, interaction: discord.Interaction, user: discord.User):
        if user == self.bot.user:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I cannot send a direct message to myself!",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(DmModal(user)) # Send the DM modal



async def setup(bot):
    await bot.add_cog(Message(bot))