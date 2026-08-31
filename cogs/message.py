"""Cog for managing message-related interactions."""
from typing import Union
import discord
from discord.ext import commands, tasks
from discord import app_commands
from config import (
    SUCCESS_EMOJI, ERROR_EMOJI, PREVIOUS_EMOJI, NEXT_EMOJI, EXCLUDED_EMOJIS, MAX_REACTION_EMOJIS
)


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
            files=files,
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
        await self.user.send(self.message.value, files=files)
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
            files=files,
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


# Modal for editing a message
class EditMessageModal(discord.ui.Modal):
    """Modal for editing an existing bot message."""
    def __init__(self, message: discord.Message):
        """Initialize the modal with the target message."""
        super().__init__(title="Edit Message")
        self.message = message
        self.edit_message.default = message.content

        # Calculate remaining attachment slots (Discord limit is 10 per message)
        existing_attachments = len(message.attachments)
        max_new_attachments = max(0, 10 - existing_attachments)

        # Update the file upload component's max_values dynamically
        self.add_files.component.max_values = max_new_attachments
        self.add_files.description = (
            f"Existing attachments will be preserved. "
            f"You can add up to {max_new_attachments} more attachment(s)."
        )

    edit_message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the updated message. Markdown formatting is supported. (no preview)",
        max_length=2000, # Discord's message character limit
        required=True,
    )
    add_files = discord.ui.Label(
        text="Upload Additional Attachments",
        description="Existing attachments will be preserved.",
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
        """Edit the message upon submission."""
        await interaction.response.defer(ephemeral=True)
        uploaded_files = self.add_files.component.values or []
        files = [await attachment.to_file() for attachment in uploaded_files]
        
        # Keep existing attachments and append new files
        attachments = list(self.message.attachments)
        attachments.extend(files)
        
        selected = self.allowed_mentions_toggles.component.values
        mention_user = "Members" in selected
        mention_role = "Roles" in selected
        mention_everyone = "@everyone and @here" in selected
        allowed_mentions = discord.AllowedMentions(
            users=mention_user,
            roles=mention_role,
            everyone=mention_everyone,
        )
        
        await self.message.edit(
            content=self.edit_message.value,
            attachments=attachments,
            allowed_mentions=allowed_mentions,
        )
        await interaction.followup.send(
            f"{SUCCESS_EMOJI} Message edited successfully.",
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle errors during message edit."""
        if isinstance(error, discord.NotFound):
            msg = f"{ERROR_EMOJI} This message is no longer available."
        elif isinstance(error, discord.Forbidden):
            msg = f"{ERROR_EMOJI} I do not have permission to edit this message."
        elif isinstance(error, discord.HTTPException):
            msg = f"{ERROR_EMOJI} Failed to edit the message. It may be too large or have too many attachments."
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

    # Previous page button
    @discord.ui.button(style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to the previous page of emojis."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    # Next page button
    @discord.ui.button(style=discord.ButtonStyle.secondary)
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


# Select menu for choosing an emoji reaction
class EmojiReactionSelect(discord.ui.Select):
    """Select menu for choosing a bot emoji to react or unreact with."""
    def __init__(self, target_message: discord.Message, emojis: list[discord.Emoji]):
        """Initialize the select menu with emojis and target message."""
        options = [
            discord.SelectOption(
                label=emoji.name,
                value=str(emoji.id),
                emoji=emoji
            )
            for emoji in emojis
        ]
        super().__init__(
            placeholder="Select an emoji",
            min_values=1,
            max_values=1,
            options=options
        )
        self.target_message = target_message
        self.emojis = emojis
        self.emoji_map = {str(e.id): e for e in emojis}

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the selection of an emoji reaction."""
        selected_id = self.values[0]
        selected_emoji = self.emoji_map.get(selected_id)
        if not selected_emoji:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The selected emoji is no longer available.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Helper to reset original view so selection is cleared and timeout is refreshed
        async def reset_select_menu(msg: discord.Message, emojis: list[discord.Emoji]):
            try:
                await interaction.edit_original_response(view=EmojiReactionView(interaction, msg, emojis))
            except Exception:
                pass

        # Redundancy check: ensure channel and message still exist
        try:
            channel = interaction.channel
            # guild_only() ensures channel is not None for guild interactions
            assert channel is not None
            fresh_message = await channel.fetch_message(self.target_message.id)
        except discord.NotFound:
            await interaction.followup.send(
                f"{ERROR_EMOJI} The target message no longer exists.",
                ephemeral=True
            )
            await reset_select_menu(self.target_message, self.emojis)
            return
        except discord.Forbidden:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I do not have permission to view this channel or message.",
                ephemeral=True
            )
            await reset_select_menu(self.target_message, self.emojis)
            return
        except discord.HTTPException as error:
            await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to fetch message: {error}",
                ephemeral=True
            )
            await reset_select_menu(self.target_message, self.emojis)
            return

        # Check if the bot has already reacted with the selected emoji
        # selected_emoji is always a custom discord.Emoji from bot's cache
        bot_user = interaction.client.user
        if bot_user is None:
            await interaction.followup.send(
                f"{ERROR_EMOJI} Bot user not ready.",
                ephemeral=True
            )
            return
        bot_reacted = False
        for reaction in fresh_message.reactions:
            is_match = False
            if isinstance(reaction.emoji, (discord.Emoji, discord.PartialEmoji)):
                if reaction.emoji.id == selected_emoji.id:
                    is_match = True

            if is_match:
                if reaction.me:
                    bot_reacted = True
                break

        try:
            if bot_reacted:
                await fresh_message.remove_reaction(selected_emoji, bot_user)
                await interaction.followup.send(
                    f"{SUCCESS_EMOJI} Removed {selected_emoji} reaction from the message.",
                    ephemeral=True
                )
            else:
                await fresh_message.add_reaction(selected_emoji)
                await interaction.followup.send(
                    f"{SUCCESS_EMOJI} Added {selected_emoji} reaction to the message.",
                    ephemeral=True
                )
        except discord.Forbidden:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I do not have permission to add or remove reactions in this channel.",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.followup.send(
                f"{ERROR_EMOJI} The message or emoji was not found.",
                ephemeral=True
            )
        except discord.HTTPException as error:
            await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to update reaction: {error}",
                ephemeral=True
            )
        finally:
            await reset_select_menu(fresh_message, self.emojis)


# View container for emoji reaction selection
class EmojiReactionView(discord.ui.LayoutView):
    """View containing the emoji reaction select menu inside a container."""
    def __init__(
        self,
        interaction: discord.Interaction,
        target_message: discord.Message,
        emojis: list[discord.Emoji],
        timeout: float = 180.0
    ):
        """Initialize the view with target message and available emojis."""
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.target_message = target_message
        self.emojis = emojis
        self.select_menu = EmojiReactionSelect(target_message, emojis)
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                "## Add or remove reaction\n"
                "Select an emoji that the bot will react or unreact with to the message."
            ),
            discord.ui.ActionRow(
                self.select_menu
            )
        )
        self.add_item(container)

    async def on_timeout(self) -> None:
        """Handle view timeout by disabling the selection menu."""
        self.select_menu.disabled = True
        try:
            await self.interaction.edit_original_response(view=self)
        except discord.HTTPException:
            pass


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

        # Context menu command for editing a bot message
        self.edit_command = app_commands.ContextMenu(
            name="Edit Message",
            callback=self.edit_command_callback
        )
        self.bot.tree.add_command(self.edit_command)

        # Context menu command for adding or removing reactions
        self.react_command = app_commands.ContextMenu(
            name="Add/Remove Reactions",
            callback=self.react_command_callback
        )
        self.bot.tree.add_command(self.react_command)

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


    # Callback for the edit context menu command
    @app_commands.guild_only()
    # Requires manage messages permission
    @app_commands.default_permissions(manage_messages=True)
    async def edit_command_callback(self, interaction: discord.Interaction, message: discord.Message):
        """Display a modal to edit one of the bot's messages via context menu."""
        if message.author != self.bot.user:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Only my own messages can be edited.",
                ephemeral=True
            )
            return
        # Send the edit modal
        await interaction.response.send_modal(EditMessageModal(message))


    # Callback for the add/remove reactions context menu command
    @app_commands.guild_only()
    # Requires manage messages and add reactions default permissions
    @app_commands.default_permissions(manage_messages=True, add_reactions=True)
    async def react_command_callback(
            self, interaction: discord.Interaction, message: discord.Message
    ):
        """Display a selection menu to add or remove reactions as the bot."""
        if not self.cached_emojis:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} No bot emojis found.",
                ephemeral=True
            )
            return

        emojis_to_display = self.cached_emojis[:MAX_REACTION_EMOJIS]
        view = EmojiReactionView(interaction, message, emojis_to_display)
        await interaction.response.send_message(
            view=view,
            ephemeral=True
        )


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
