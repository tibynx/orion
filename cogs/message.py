"""Cog for managing message-related interactions."""
from typing import Union
import discord
from discord.ext import commands
from discord import app_commands
from config import SUCCESS_EMOJI, ERROR_EMOJI


# Helper to check if the user is the bot itself.
def is_self_dm(bot: commands.Bot, user: discord.User) -> bool:
    """Check if the target user is the bot itself."""
    return user == bot.user


# Modal for sending a message in a channel
class MessageModal(discord.ui.Modal):
    """Modal for sending a message to a specific channel."""
    def __init__(self, channel: discord.abc.Messageable):
        """Initialize the modal with the target channel."""
        super().__init__(title=f"Message #{channel.name}")
        self.channel = channel

    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send.",
        max_length=2000, # Discord's message character limit
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Send the message to the channel upon submission."""
        await interaction.response.defer(ephemeral=True)
        await self.channel.send(self.message.value)
        await interaction.followup.send(
            f"{SUCCESS_EMOJI} Message sent successfully in {self.channel.mention}.",
            ephemeral=True
        )
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle errors during message submission."""
        if isinstance(error, discord.NotFound):
            msg = f"{ERROR_EMOJI} The specified channel cannot be found."
        elif isinstance(error, discord.Forbidden):
            msg = f"{ERROR_EMOJI} I do not have permission to send messages to this channel."
        else:
            msg = f"{ERROR_EMOJI} An unexpected error occurred."
            raise error

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


# Modal for sending a direct message to a user
class DmModal(discord.ui.Modal):
    """Modal for sending a direct message to a user."""
    def __init__(self, user: discord.User):
        """Initialize the modal with the target user."""
        super().__init__(title=f"Message {user.name}")
        self.user = user

    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send.",
        max_length=2000, # Discord's message character limit
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Send the direct message upon submission."""
        # Defer the response to avoid interaction timeout while sending the DM
        await interaction.response.defer(ephemeral=True)
        await self.user.send(self.message.value)
        await interaction.followup.send(
            f"{SUCCESS_EMOJI} Direct message sent successfully to {self.user.mention}.",
            ephemeral=True
        )
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle errors during direct message submission."""
        if isinstance(error, discord.NotFound):
            msg = f"{ERROR_EMOJI} This user is no longer available."
        elif isinstance(error, discord.Forbidden):
            msg = (f"{ERROR_EMOJI} Cannot send message to {self.user.mention}. "
                   f"They might have DMs disabled.")
        else:
            msg = f"{ERROR_EMOJI} An unexpected error occurred."
            raise error

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


# Modal for replying to a message
class ReplyModal(discord.ui.Modal):
    """Modal for replying to a specific message."""
    def __init__(self, message: discord.Message):
        """Initialize the modal with the target message."""
        super().__init__(title=f"Reply to {message.author.name}")
        self.message = message

    reply_message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send.",
        max_length=2000, # Discord's message character limit
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Send the reply upon submission."""
        await interaction.response.defer(ephemeral=True)
        await self.message.reply(self.reply_message.value)
        await interaction.followup.send(
            f"{SUCCESS_EMOJI} Reply sent successfully to {self.message.author.mention}.",
            ephemeral=True
        )
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle errors during reply submission."""
        if isinstance(error, discord.NotFound):
            msg = f"{ERROR_EMOJI} This message is no longer available."
        elif isinstance(error, discord.Forbidden):
            msg = f"{ERROR_EMOJI} I do not have permission to reply to this message."
        else:
            msg = f"{ERROR_EMOJI} An unexpected error occurred."
            raise error

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


# Message commands
class Message(commands.Cog):
    """Cog for sending and replying to messages."""
    def __init__(self, bot):
        """Initialize the cog with the bot instance."""
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
        description="Send a message in a channel."
    )
    # Requires manage messages permission
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    @app_commands.describe(
        channel="The channel to send the message in."
    )
    async def send_message_modal(
        self, interaction: discord.Interaction,
        channel: Union[
            discord.TextChannel, discord.Thread,
            discord.StageChannel, discord.VoiceChannel
        ],
    ):
        """Display a modal to send a message to a specific channel."""
        # Send the message modal
        await interaction.response.send_modal(MessageModal(channel))


    # Send a direct message to a user
    @app_commands.command(
        name="dm",
        description="Send a direct message to a user."
    )
    # Requires manage guild permission
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(
        user="The user to send the direct message to."
    )
    async def send_dm_modal(
            self, interaction: discord.Interaction, user: discord.User
    ):
        """Display a modal to send a direct message to a user."""
        if is_self_dm(self.bot, user):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I cannot send a DM to myself.",
                ephemeral=True
            )
            return
        # Send the DM modal
        await interaction.response.send_modal(DmModal(user))


    # Callback for the reply context menu command
    @app_commands.guild_only()
    # Requires manage guild permission
    @app_commands.default_permissions(manage_guild=True)
    async def reply_command_callback(
            self, interaction: discord.Interaction, message: discord.Message
    ):
        """Display a modal to reply to a message via context menu."""
        # Send the reply modal
        await interaction.response.send_modal(ReplyModal(message))


    # Callback for the send DM user command
    @app_commands.guild_only()
    # Requires manage guild permission
    @app_commands.default_permissions(manage_guild=True)
    async def dm_command_callback(self, interaction: discord.Interaction, user: discord.User):
        """Display a modal to send a direct message to a user via context menu."""
        if is_self_dm(self.bot, user):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I cannot send a DM to myself.",
                ephemeral=True
            )
            return
        # Send the DM modal
        await interaction.response.send_modal(DmModal(user))



async def setup(bot):
    """Add the Message cog to the bot."""
    await bot.add_cog(Message(bot))
