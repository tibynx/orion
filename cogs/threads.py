"""Cog for managing threads."""
import discord
from discord.ext import commands
from discord import app_commands
from config import SUCCESS_EMOJI, ERROR_EMOJI


# Create a modal for creating a new thread
class CreateThreadModal(discord.ui.Modal, title="Create New Thread"):
    """Modal for defining thread name and first message."""
    def __init__(self, message: discord.Message):
        """Initialize the modal with the base message."""
        super().__init__()
        self.message = message

    name = discord.ui.TextInput(
        label="Thread Name",
        placeholder="New Thread",
        required=True,
        max_length=200, # Character limit for thread names
    )
    first_message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the first message of the thread. Markdown formatting is supported. (no preview)",
        required=True,
        max_length=2000, # Discord's message character limit
    )
    add_files = discord.ui.Label(
        text="Upload Attachments",
        component=discord.ui.FileUpload(
            max_values=10,
            required=False
        )
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Create the thread and send the first message upon submission."""
        await interaction.response.defer(ephemeral=True)
        uploaded_files = self.add_files.component.values or []
        files = [await attachment.to_file() for attachment in uploaded_files]
        # Create the thread from the message
        thread = await self.message.create_thread(
            name=self.name.value,
            auto_archive_duration=4320  # 3 days
        )
        # Send the first message in the thread
        await thread.send(
            content=self.first_message.value,
            files=files or None,
        )
        await interaction.followup.send(
            f"{SUCCESS_EMOJI} Thread created successfully.",
            ephemeral=True
        )
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle errors during thread creation."""
        if isinstance(error, discord.Forbidden):
            msg = f"{ERROR_EMOJI} I don't have permission to create threads or send messages here."
        elif isinstance(error, discord.NotFound):
            msg = f"{ERROR_EMOJI} The original message or channel is no longer available."
        else:
            msg = f"{ERROR_EMOJI} An unexpected error occurred."
            raise error

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)



# Thread management commands
class Threads(commands.Cog):
    """Cog for thread management commands."""
    def __init__(self, bot):
        """Initialize the cog with the bot instance."""
        self.bot = bot

        # Context menu command for creating a new thread
        self.thread_command = app_commands.ContextMenu(
            name="Create Thread",
            callback=self.thread_create_callback
        )
        self.bot.tree.add_command(self.thread_command)

    # Helper to resolve a thread from the current context or a provided ID
    async def _get_thread(
            self, interaction: discord.Interaction, thread_id: str | None = None
    ) -> discord.Thread | None:
        """Resolve a thread from context or provided ID."""
        # Get a thread from the current channel or by its ID.
        # If used inside a thread, return it directly
        if isinstance(interaction.channel, discord.Thread):
            return interaction.channel
        # If not inside a thread and no ID provided
        if not thread_id:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Please provide a thread ID when "
                "using this command outside of a thread.",
                ephemeral=True
            )
            return None
        # Try to fetch by ID and ensure it's a thread
        try:
            channel = await self.bot.fetch_channel(int(thread_id))
        except ValueError:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The provided thread ID is invalid.",
                ephemeral=True
            )
            return None
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified thread cannot be found!",
                ephemeral=True
            )
            return None
        if not isinstance(channel, discord.Thread):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified ID is not a thread.",
                ephemeral=True
            )
            return None
        return channel



    # Callback for the 'new thread' command in a context menu
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_threads=True)
    async def thread_create_callback(
            self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """Display a modal to create a thread from a message."""
        # Check if the channel type supports threads
        if not isinstance(message.channel, (discord.TextChannel, discord.ForumChannel)):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Threads can only be created in text channels or forums.",
                ephemeral=True
            )
            return
        # Check if the message already has a thread
        if message.thread:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} This message already has a thread.",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(CreateThreadModal(message))


    # Close thread
    @app_commands.command(
        name="threadclose",
        description="Close a thread. If used in a thread, closes the current thread."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_threads=True)
    @app_commands.describe(
        thread_id="The ID of the thread to close (optional if used inside a thread)"
    )
    async def thread_close(self, interaction: discord.Interaction, thread_id: str = None) -> None:
        """Close a thread."""
        thread = await self._get_thread(interaction, thread_id)
        if thread is None:
            return
        try:
            await thread.edit(archived=True)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Thread has been closed.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to close this thread.",
                ephemeral=True
            )


    # Rename thread
    @app_commands.command(
        name="threadrename",
        description="Rename a thread. If used in a thread, renames the current thread."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_threads=True)
    @app_commands.describe(
        thread_id="The ID of the thread to rename (optional if used inside a thread)",
        name="The new name of the thread"
    )
    async def thread_rename(
            self, interaction: discord.Interaction, name: str, thread_id: str = None
    ) -> None:
        """Rename a thread."""
        thread = await self._get_thread(interaction, thread_id)
        if thread is None:
            return
        try:
            await thread.edit(name=name)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Thread has been renamed to: **{name}**",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to rename this thread.",
                ephemeral=True
            )


    # Set slowmode for thread
    @app_commands.command(
        name="threadslowmode",
        description="Set the slowmode for a thread. "
                    "If used in a thread, sets the slowmode for the current thread."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_threads=True)
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
        thread_id="The ID of the thread to set slowmode for (optional if used inside a thread)",
        duration="The duration to set the slowmode to"
    )
    async def thread_slowmode(
            self, interaction: discord.Interaction,
            duration: discord.app_commands.Choice[int], thread_id: str = None
    ) -> None:
        """Set slowmode for a thread."""
        thread = await self._get_thread(interaction, thread_id)
        if thread is None:
            return
        try:
            await thread.edit(slowmode_delay=duration.value)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Thread slowmode set to: **{duration.name}**",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to set slowmode for this thread.",
                ephemeral=True
            )


    # Lock thread
    @app_commands.command(
        name="threadlock",
        description="Lock a thread. If used in a thread, locks the current thread."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_threads=True)
    @app_commands.describe(
        thread_id="The ID of the thread to lock (optional if used inside a thread)"
    )
    async def thread_lock(self, interaction: discord.Interaction, thread_id: str = None) -> None:
        """Lock a thread."""
        thread = await self._get_thread(interaction, thread_id)
        if thread is None:
            return
        try:
            await thread.edit(locked=True)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Thread has been locked.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to lock this thread.",
                ephemeral=True
            )


    # Unlock thread
    @app_commands.command(
        name="threadunlock",
        description="Unlock a thread. If used in a thread, unlocks the current thread."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_threads=True)
    @app_commands.describe(
        thread_id="The ID of the thread to unlock (optional if used inside a thread)"
    )
    async def thread_unlock(self, interaction: discord.Interaction, thread_id: str = None) -> None:
        """Unlock a thread."""
        thread = await self._get_thread(interaction, thread_id)
        if thread is None:
            return
        try:
            await thread.edit(locked=False)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Thread has been unlocked.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to unlock this thread.",
                ephemeral=True
            )



async def setup(bot):
    """Add the Threads cog to the bot."""
    await bot.add_cog(Threads(bot))
