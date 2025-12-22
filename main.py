import logging
import os
import discord
from discord import app_commands
from discord.ext import commands
from config import BOT_TOKEN, ERROR_EMOJI


# TODO: Do pylint, and fix code
# TODO: Add a proper README.md
# TODO: Make poetry config


# Set intents
intents = discord.Intents.default()
intents.message_content = True

# Set up logging
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(logs_dir, exist_ok=True)
timestamp = discord.utils.utcnow().strftime("%Y-%m-%d_%H-%M-%S") # UTC timestamp
log_filename = os.path.join(logs_dir, f"log_{timestamp}.log")

logger = logging.getLogger("discord.app")
logger.setLevel(logging.INFO)
log_handler = logging.FileHandler(filename=log_filename, encoding="utf-8", mode="w")
# Using Python's standard formatting style
log_format = "[{asctime}] [{levelname:<8}] {name}: {message}"
log_formatter = logging.Formatter(log_format, "%Y-%m-%d %H:%M:%S", style="{")
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        # No prefix since we use app commands
        super().__init__(command_prefix="", intents=intents)
        self.logger = logger


    # Load cogs
    async def load_cogs(self) -> None:
        for file in os.listdir(os.path.join(os.path.realpath(os.path.dirname(__file__)), "cogs")):
            if file.endswith(".py"): # Only load python files
                extension = file[:-3]
                try:
                    await self.load_extension(f"cogs.{extension}")
                    self.logger.info("Loaded extension '%s'", extension)
                except Exception as error:
                    self.logger.error(
                        "Failed to load extension '%s': %s", extension, type(error).__name__
                    )
                    self.logger.exception(error)


    async def setup_hook(self) -> None:
        self.logger.info(
            "Logged in as %s#%s (ID: %s)", self.user.name, self.user.discriminator, self.user.id
        )
        self.logger.info("discord.py version: %s", discord.__version__)
        self.logger.info("-------------------")
        await self.load_cogs()

        # Sync interactions
        try:
            synced = await self.tree.sync() # Sync all commands globally
            self.logger.info("Synced %d interactions globally", len(synced))
        except Exception as error:
            self.logger.error("Failed to sync interaction: %s", type(error).__name__)
            self.logger.exception(error)


    # Log guild join
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.logger.info(
            "Joined guild '%s' (ID: %s) with %d member(s), the guild owner is %s (ID: %s)",
            guild.name, guild.id, len(guild.members), guild.owner, guild.owner.id
        )

    # Log guild leave
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.logger.info(
            "Left guild '%s' (ID: %s) with %d member(s), the guild owner is %s (ID: %s)",
            guild.name, guild.id, len(guild.members), guild.owner, guild.owner.id
        )

    # Log app command execution
    async def on_app_command_completion(
            self, interaction: discord.Interaction, command: app_commands.Command
    ) -> None:
        if interaction.guild is not None:
            self.logger.info(
                "User %s (ID: %s) executed the '%s' interaction in guild '%s' (ID: %s)",
                interaction.user, interaction.user.id, command.qualified_name,
                interaction.guild.name, interaction.guild.id
            )
        else:
            self.logger.info(
                "User %s (ID: %s) executed the '%s' interaction in DMs",
                interaction.user, interaction.user.id, command.qualified_name
            )

    # Log command errors
    async def on_error(self, event_name: str, *args, **kwargs) -> None:
        self.logger.exception("An error occurred in %s", event_name)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors
        self.logger.error("An unhandled command error occurred: %s", error)

    async def on_app_command_error(
            self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        command_name = interaction.command.name if interaction.command else "Unknown command"

        # Check if interaction was already responded to
        if interaction.response.is_done():
            send_func = interaction.followup.send
        else:
            send_func = interaction.response.send_message


        # User doesn't have permission to execute the command
        if isinstance(error, (app_commands.MissingPermissions, app_commands.errors.CheckFailure)):
            await send_func(
                f"{ERROR_EMOJI} You don't have permission to execute this command.",
                ephemeral=True
            )

        # Bot doesn't have permission to execute the command
        elif isinstance(error, (app_commands.BotMissingPermissions, discord.Forbidden)):
            await send_func(
                f"{ERROR_EMOJI} I don't have permission to execute this command.",
                ephemeral=True
            )

        # Command doesn't exist
        # Happens when a command is updated, but the client hasn't refreshed
        elif isinstance(error, app_commands.CommandNotFound):
            await send_func(
                f"{ERROR_EMOJI} Command not found. Please refresh your client.",
                ephemeral=True
            )

        # Network issues or rate limiting
        elif isinstance(error, discord.HTTPException):
            self.logger.warning(
                "HTTP exception occurred in interaction '%s' for user %s (ID: %s) in "
                "guild '%s' (ID: %s): %s",
                command_name, interaction.user.name, interaction.user.id,
                interaction.guild.name, interaction.guild.id, error
            )
            await send_func(
                f"{ERROR_EMOJI} I cannot complete this command because of network issues. "
                "I might have been rate limited. Please try again later.",
                ephemeral=True
            )

        # Command raised an unexpected error
        elif isinstance(error, app_commands.CommandInvokeError):
            original = getattr(error, "original", error)
            self.logger.error(
                "CommandInvokeError occurred in interaction '%s' by user %s (ID: %s) in "
                "guild '%s' (ID: %s): %r",
                command_name, interaction.user.name, interaction.user.id,
                interaction.guild.name, interaction.guild.id, original,
                exc_info=(type(original), original, original.__traceback__),
            )
            await send_func(
                f"{ERROR_EMOJI} An error occurred while executing the command.",
                ephemeral=True
            )
            return

        # Other errors
        else:
            self.logger.error(
                "Unhandled app command error in interaction '%s' by user %s (ID: %s) in "
                "guild '%s' (ID: %s): %r",
                command_name, interaction.user.name, interaction.user.id,
                interaction.guild.name, interaction.guild.id, error,
                exc_info=(type(error), error, error.__traceback__),
            )
            await send_func(
                f"{ERROR_EMOJI} An unexpected error occurred while executing the command.",
                ephemeral=True
            )


# Run the bot
bot = DiscordBot()

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables")
bot.run(BOT_TOKEN)
