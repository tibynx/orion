import discord
from discord.ext import commands
from discord import app_commands

from config import SUCCESS_EMOJI, ERROR_EMOJI


# TODO: Do pylint, and fix code
# TODO: Add more comments
# TODO: Add missing activity types: listening, watching, playing


class Presence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_status = discord.Status.online  # Default status
        self.current_activity: discord.BaseActivity | None = None  # Track current activity


    # Group for changing bot activity
    activity_set_group = app_commands.Group(
        name="activityset",
        description="Set ",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True
    )

    # Clear activity
    @app_commands.command(
        name="activityclear",
        description="Clear the bot's activity and status.",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def activity_clear(self, interaction: discord.Interaction):
        self.current_activity = None
        await self.bot.change_presence(status=self.current_status, activity=None)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Presence and status have been cleared.",
            ephemeral=True
        )

    # Set status
    @app_commands.command(
        name="statusset",
        description="Set the bot's presence status."
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(
        status="The status to set the bot to."
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(name="Online", value="online"),
            app_commands.Choice(name="Idle", value="idle"),
            app_commands.Choice(name="Do Not Disturb", value="dnd"),
            app_commands.Choice(name="Invisible", value="invisible"),
        ]
    )
    async def status_set(self, interaction: discord.Interaction, status: app_commands.Choice[str]):
        status_mapping = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.do_not_disturb,
            "invisible": discord.Status.invisible,
        }

        self.current_status = status_mapping[status.value]
        await self.bot.change_presence(status=self.current_status, activity=self.current_activity)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Changed status to: **{status.name}**",
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
        url="The URL of the stream. (Must be a valid Twitch or YouTube URL.)"
    )
    async def activity_streaming(self, interaction: discord.Interaction, title: str, url: str, description: str = None):
        if not url or not url.startswith("https://"):
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} You must provide a valid URL for the stream! Example: `https://www.twitch.tv/your_channel`")
        self.current_activity = discord.Activity(type=discord.ActivityType.streaming, name=title, url=url, state=description)
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
    async def activity_custom(self, interaction: discord.Interaction, title: str):
        self.current_activity = discord.CustomActivity(name=title)
        await self.bot.change_presence(status=self.current_status, activity=self.current_activity)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Activity set to: {title}",
            ephemeral=True
        )





async def setup(bot):
    await bot.add_cog(Presence(bot))