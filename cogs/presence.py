import discord
from discord.ext import commands
from discord import app_commands
from config import SUCCESS_EMOJI, ERROR_EMOJI


# TODO: Do pylint, and fix code
# TODO: Define status_mapping as a class-level constant
# TODO: Verify URL is actually Twitch or YouTube URL


# Presence commands for changing bot activity and status
class Presence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_status = discord.Status.online  # Default status
        self.current_activity: discord.BaseActivity | None = None  # Track current activity

    # Group for changing bot activity
    activity_set_group = app_commands.Group(
        name="activityset",
        description="Set the bot's activity and status.",
        # Requires manage guild permission
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True
    )


    # Clear activity
    @app_commands.command(
        name="activityclear",
        description="Clear the bot's activity and status."
    )
    # Requires manage guild permission
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def activity_clear(self, interaction: discord.Interaction):
        # Set status to online, clear activity
        self.current_activity = None
        self.current_status = discord.Status.online
        await self.bot.change_presence(status=self.current_status, activity=None)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Activity and status have been cleared.",
            ephemeral=True
        )


    # Set status
    @activity_set_group.command(
        name="indicator",
        description="Set the bot's status indicator."
    )
    # Requires manage guild permission
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(
        status="The status to set for the bot."
    )
    @app_commands.choices( # List of status choices
        status=[
            app_commands.Choice(name="Online", value="online"),
            app_commands.Choice(name="Idle", value="idle"),
            app_commands.Choice(name="Do Not Disturb", value="dnd"),
            app_commands.Choice(name="Invisible", value="invisible"),
        ]
    )
    async def activity_indicator(
            self, interaction: discord.Interaction, status: app_commands.Choice[str]
    ):
        # Map string choices to discord.Status
        status_mapping = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.do_not_disturb,
            "invisible": discord.Status.invisible,
        }
        # Set the new status, keep current activity
        self.current_status = status_mapping[status.value]
        await self.bot.change_presence(status=self.current_status, activity=self.current_activity)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Status changed to: **{status.name}**",
            ephemeral=True
        )

    # Change bot activity to streaming
    @activity_set_group.command(
        name="streaming",
        description="Set the bot's activity to streaming."
    )
    @app_commands.describe(
        title="The title of the stream.",
        description="The description of the activity.",
        # Only Twitch and YouTube are supported by Discord
        url="The URL of the stream (must be a valid Twitch or YouTube URL)."
    )
    async def activity_streaming(
            self, interaction: discord.Interaction, title: str, url: str, description: str = None
    ):
        # Check for valid URL, only https is supported
        if not url.startswith("https://"):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} You must provide a valid URL for the stream. "
                "Example: `https://www.twitch.tv/your_channel`",
                ephemeral=True
            )
            return
        self.current_activity = discord.Activity(
            type=discord.ActivityType.streaming, name=title, url=url, state=description
        )
        await self.bot.change_presence(status=self.current_status, activity=self.current_activity)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Activity set to: **Streaming** {title} (<{url}>)",
            ephemeral=True
        )


    # Set custom bot activity
    @activity_set_group.command(
        name="custom",
        description="Set a custom activity for the bot."
    )
    @app_commands.describe(
        title="The activity text to display."
    )
    async def activity_custom(
            self, interaction: discord.Interaction, title: str
    ):
        self.current_activity = discord.CustomActivity(name=title)
        await self.bot.change_presence(status=self.current_status, activity=self.current_activity)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Activity set to: {title}",
            ephemeral=True
        )


    # Set activity to playing
    @activity_set_group.command(
        name="playing",
        description="Set the bot's activity to playing."
    )
    @app_commands.describe(
        title="The name of the game being played.",
        description="The description of the activity."
    )
    async def activity_playing(
            self, interaction: discord.Interaction, title: str, description: str = None
    ):
        self.current_activity = discord.Activity(
            type=discord.ActivityType.playing, name=title, state=description
        )
        await self.bot.change_presence(status=self.current_status, activity=self.current_activity)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Activity set to: **Playing** {title}",
            ephemeral=True
        )


    # Set activity to listening
    @activity_set_group.command(
        name="listening",
        description="Set the bot's activity to listening."
    )
    @app_commands.describe(
        title="The name of what the bot is listening to.",
        description="The description of the activity."
    )
    async def activity_listening(
            self, interaction: discord.Interaction, title: str, description: str = None
    ):
        self.current_activity = discord.Activity(
            type=discord.ActivityType.listening, name=title, state=description
        )
        await self.bot.change_presence(status=self.current_status, activity=self.current_activity)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Activity set to: **Listening to** {title}",
            ephemeral=True
        )


    # Set activity to watching
    @activity_set_group.command(
        name="watching",
        description="Set the bot's activity to watching."
    )
    @app_commands.describe(
        title="The name of what the bot is watching.",
        description="The description of the activity."
    )
    async def activity_watching(
            self, interaction: discord.Interaction, title: str, description: str = None
    ):
        self.current_activity = discord.Activity(
            type=discord.ActivityType.watching, name=title, state=description
        )
        await self.bot.change_presence(status=self.current_status, activity=self.current_activity)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Activity set to: **Watching** {title}",
            ephemeral=True
        )



async def setup(bot):
    await bot.add_cog(Presence(bot))
