"""Cog for managing message-related interactions."""
from typing import Union
import discord
from discord.ext import commands, tasks
from discord import app_commands
from config import SUCCESS_EMOJI, ERROR_EMOJI, PREVIOUS_EMOJI, NEXT_EMOJI, EXCLUDED_EMOJIS


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
        placeholder="Enter the message to send. Markdown formatting is supported. (no preview)",
        max_length=2000, # Discord's message character limit
        required=True,
    )
    add_files = discord.ui.Label(
        text="Upload Attachments",
        component=discord.ui.FileUpload(
            max_values=10,
            required=False
        )
    )
    allowed_mentions_toggles = discord.ui.Label(
        text="Allowed Mentions",
        description="Whether to ping mentions in the message.",
        component=discord.ui.CheckboxGroup(
            options=[
                discord.CheckboxGroupOption(label="Members", default=True),
                discord.CheckboxGroupOption(label="Roles", default=True),
                discord.CheckboxGroupOption(label="@everyone and @here", default=False)
            ],
            required=False
        )
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Send the message to the channel upon submission."""
        await interaction.response.defer(ephemeral=True)
        uploaded_files = self.add_files.component.values or []
        files = [await attachment.to_file() for attachment in uploaded_files]
        selected = self.allowed_mentions_toggles.component.values
        mention_user = "Members" in selected
        mention_role = "Roles" in selected
        mention_everyone = "@everyone and @here" in selected
        allowed_mentions = discord.AllowedMentions(
            users=mention_user,
            roles=mention_role,
            everyone=mention_everyone,
        )
        await self.channel.send(
            self.message.value,
            files=files or None,
            allowed_mentions=allowed_mentions,
        )
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
        placeholder="Enter the message to send. Markdown formatting is supported. (no preview)",
        max_length=2000, # Discord's message character limit
        required=True,
    )
    add_files = discord.ui.Label(
        text="Upload Attachments",
        component=discord.ui.FileUpload(
            max_values=10,
            required=False
        )
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Send the direct message upon submission."""
        # Defer the response to avoid interaction timeout while sending the DM
        await interaction.response.defer(ephemeral=True)
        uploaded_files = self.add_files.component.values or []
        files = [await attachment.to_file() for attachment in uploaded_files]
        await self.user.send(self.message.value, files=files or None)
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
        placeholder="Enter the message to send. Markdown formatting is supported. (no preview)",
        max_length=2000, # Discord's message character limit
        required=True,
    )
    add_files = discord.ui.Label(
        text="Upload Attachments",
        component=discord.ui.FileUpload(
            max_values=10,
            required=False
        )
    )

    mention_author_toggle = discord.ui.Label(
        text="Mention Author",
        description="Whether to ping the original author.",
        component=discord.ui.Checkbox(default=True)
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Send the reply upon submission."""
        await interaction.response.defer(ephemeral=True)
        uploaded_files = self.add_files.component.values or []
        files = [await attachment.to_file() for attachment in uploaded_files]
        should_mention = self.mention_author_toggle.component.value
        await self.message.reply(
            self.reply_message.value,
            files=files or None,
            mention_author=should_mention
        )
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


# Pagination view for bot emojis
class EmojiPaginationView(discord.ui.View):
    """View for paginating bot emojis list embeds."""
    def __init__(self, emojis: list[discord.Emoji]):
        """Initialize the pagination view with emojis."""
        super().__init__(timeout=180)
        self.emojis = emojis
        self.message = None
        self.current_page = 0
        self.per_page = 10
        self.total_pages = max(1, (len(emojis) - 1) // self.per_page + 1)
        # Set pagination emojis from config
        self.prev_page.emoji = PREVIOUS_EMOJI
        self.next_page.emoji = NEXT_EMOJI
        self.update_buttons()

    def update_buttons(self) -> None:
        """Enable or disable pagination buttons based on current page."""
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= self.total_pages - 1

    def build_embed(self) -> discord.Embed:
        """Build the embed for the current page."""
        embed = discord.Embed(
            title="Bot Emojis",
            color=None
        )
        if not self.emojis:
            embed.description = "No emojis available."
        else:
            start = self.current_page * self.per_page
            end = start + self.per_page
            page_emojis = self.emojis[start:end]

            lines = []
            for emoji in page_emojis:
                lines.append(f"{emoji} `{emoji}`")
            embed.description = "\n".join(lines)

        embed.set_footer(
            text=f"Page {self.current_page + 1}/{self.total_pages}  •  Total: {len(self.emojis)}"
        )
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to the previous page of emojis."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to the next page of emojis."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    async def on_timeout(self) -> None:
        """Disable buttons when the view times out."""
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
        self.stop()


# Message commands
class Message(commands.Cog):
    """Cog for sending and replying to messages."""
    def __init__(self, bot):
        """Initialize the cog with the bot instance."""
        self.bot = bot
        self.cached_emojis = []
        self.refresh_emoji_cache.start()

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

    async def cog_unload(self) -> None:
        """Stop the background tasks on cog unload."""
        self.refresh_emoji_cache.cancel()

    # Periodically refresh the application emojis cache every 30 minutes
    @tasks.loop(minutes=30)
    async def refresh_emoji_cache(self) -> None:
        """Fetch and cache application emojis, filtering out excluded ones."""
        try:
            emojis = await self.bot.fetch_application_emojis()
            excluded = set(EXCLUDED_EMOJIS)
            filtered = []
            for e in emojis:
                if (e.name in excluded or
                        str(e.id) in excluded or
                        str(e) in excluded):
                    continue
                filtered.append(e)

            self.cached_emojis = filtered
            self.bot.logger.info("Successfully refreshed application emojis cache.")
        except Exception as error:
            self.bot.logger.error("Failed to refresh application emojis cache: %s", error)

    @refresh_emoji_cache.before_loop
    async def before_refresh_emoji_cache(self) -> None:
        """Wait until the bot is ready before starting the cache loop."""
        await self.bot.wait_until_ready()



    # Send a message in a specified channel
    @app_commands.command(
        name="msg",
        description="Send a message in a channel."
    )
    # Requires manage messages permission
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    @app_commands.describe(
        channel="The channel to send the message in (optional)"
    )
    async def send_message_modal(
        self, interaction: discord.Interaction,
        channel: Union[
            discord.TextChannel, discord.Thread,
            discord.StageChannel, discord.VoiceChannel
        ] = None,
    ):
        """Display a modal to send a message to a specific channel."""
        if channel is None:
            channel = interaction.channel
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


    # List all custom emojis that the bot owns
    @app_commands.command(
        name="botemojis",
        description="List all custom emojis that the bot owns."
    )
    # Requires manage messages permission
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def list_bot_emojis(self, interaction: discord.Interaction) -> None:
        """List all custom emojis that the bot owns."""
        if not self.cached_emojis:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} No bot emojis found.",
                ephemeral=True
            )
            return

        view = EmojiPaginationView(self.cached_emojis)
        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True
        )
        view.message = await interaction.original_response()



async def setup(bot):
    """Add the Message cog to the bot."""
    await bot.add_cog(Message(bot))
