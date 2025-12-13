import logging
import traceback
import os

import discord
from discord import app_commands
from discord.ext import commands

from config import TOKEN, ERROR_EMOJI


# TODO: Remove colors from console logger
# TODO: Make file logger rotate logs
# TODO: Make file logger save logs to 'logs/' directory
# TODO: Do pylint, and fix code
# TODO: Remove unused/unnecessary code
# TODO: Optimize code, check for better solutions
# TODO: Add a proper README.md, .gitignore, and requirements.txt
# TODO: Rename 'commands/' to 'cogs/'
# TODO: Remove commited secrets file and logs (oops..)
# TODO: Make a setup.py for easy installation
# TODO: Migrate using 'config.py' for constants like EMBED_COLOR and EMOJIS to use .env variables
# TODO: Move loading secrets from 'config.py' to 'main.py'
# TODO: Make a Dockerfile for easy deployment
# TODO: Create a GitHub Workflow to check code with pylint on each push
# TODO: Create a GitHub Workflow to automatically build and push Docker images on each release
# TODO: Make poetry config
# TODO: Make IDEA run configurations for PyCharm

# TODO: Make command to send messages as the bot (optionally in specific channels)
# TODO: Make command to react to messages as the bot (optionally in specific channels)
# TODO: Make command to purge messages


# Set intents
intents = discord.Intents.default()
intents.message_content = True

# Set up both of the loggers
class LoggingFormatter(logging.Formatter):
    # Colors
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    gray = "\x1b[38m"

    # Styles
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    COLORS = {
        logging.DEBUG: gray + bold,
        logging.INFO: blue + bold,
        logging.WARNING: yellow + bold,
        logging.ERROR: red,
        logging.CRITICAL: red + bold,
    }

    def format(self, record):
        log_color = self.COLORS[record.levelno]
        log_format = "(black)[{asctime}](reset) (levelcolor)[{levelname:<8}](reset) (green){name}:(reset) {message}"
        log_format = log_format.replace("(black)", self.black + self.bold)
        log_format = log_format.replace("(reset)", self.reset)
        log_format = log_format.replace("(levelcolor)", log_color)
        log_format = log_format.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(log_format, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)


logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(LoggingFormatter())

# File handler
file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
file_handler_log_format = "[{asctime}] [{levelname:<8}] {name}: {message}"
file_handler_formatter = logging.Formatter(file_handler_log_format, "%Y-%m-%d %H:%M:%S", style="{")
file_handler.setFormatter(file_handler_formatter)

# Add the handlers
logger.addHandler(console_handler)
logger.addHandler(file_handler)


class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="", intents=intents)
        self.logger = logger


    # Load cogs
    async def load_cogs(self) -> None:
        for file in os.listdir(f"{os.path.realpath(os.path.dirname(__file__))}/commands"):
            if file.endswith(".py"):
                extension = file[:-3]
                # try:
                await self.load_extension(f"commands.{extension}")
                self.logger.info(f"Loaded extension '{extension}'")
                # except Exception as e:
                #     exception = f"{type(e).__name__}: {e}"
                #     self.logger.error(f"Failed to load extension '{extension}'\n{exception}")


    async def setup_hook(self) -> None:
        self.logger.info(f"Logged in as {self.user.name}#{self.user.discriminator} (ID: {self.user.id})")
        self.logger.info(f"discord.py version: {discord.__version__}")
        self.logger.info("-------------------")
        await self.load_cogs()

        # Sync interactions
        try:
            synced = await bot.tree.sync()
            self.logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            exception = f"{type(e).__name__}: {e}"
            self.logger.error(f"Failed to sync commands\n{exception}")


    # Log guild join
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.logger.info(f"Joined guild '{guild.name}' (ID: {guild.id}) with {len(guild.members)} member(s), the guild owner is {guild.owner} (ID: {guild.owner.id})")

    # Log guild leave
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.logger.info(f"Left guild '{guild.name}' (ID: {guild.id}) with {len(guild.members)} member(s), the guild owner is {guild.owner} (ID: {guild.owner.id})")

    # Log app command execution
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command) -> None:
        """Log successful app command (slash command) executions"""
        full_command_name = command.qualified_name
        split = full_command_name.split(" ")
        executed_command = str(split[0])

        if interaction.guild is not None:
            self.logger.info(
                f"User {interaction.user} (ID: {interaction.user.id}) executed '/{executed_command}' command in "
                f"guild '{interaction.guild.name}' (ID: {interaction.guild.id})"
            )
        else:
            self.logger.info(
                f"User {interaction.user} (ID: {interaction.user.id}) executed '/{executed_command}' command in DMs"
            )

    # Log command errors
    async def on_error(self, event_name: str, *args, **kwargs) -> None:
        """Handle general errors"""
        self.logger.error(f"An error occurred in {event_name}")
        traceback.print_exc()

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Handle app command (slash command) errors"""
        command_name = interaction.command.name if interaction.command else "Unknown command"

        # Check if interaction was already responded to
        if interaction.response.is_done():
            send_func = interaction.followup.send
        else:
            send_func = interaction.response.send_message


        # Command is on cooldown
        if isinstance(error, app_commands.CommandOnCooldown):
            minutes, seconds = divmod(error.retry_after, 60)
            hours, minutes = divmod(minutes, 60)
            hours = hours % 24
            cooldown = []
            if round(hours) > 0:
                cooldown.append(f"{round(hours)} hours")
            if round(minutes) > 0:
                cooldown.append(f"{round(minutes)} minutes")
            if round(seconds) > 0:
                cooldown.append(f"{round(seconds)} seconds")
            await send_func(
                f"{ERROR_EMOJI} You can use this command again in {' '.join(cooldown)}!",
                ephemeral=True
            )

        # User doesn't have permission to execute the command
        elif isinstance(error, app_commands.MissingPermissions):
            await send_func(
                f"{ERROR_EMOJI} You are missing permission(s) to execute this command: `{', '.join(error.missing_permissions)}`",
                ephemeral=True
            )

        # Bot doesn't have permission to execute the command
        elif isinstance(error, app_commands.BotMissingPermissions):
            await send_func(
                f"{ERROR_EMOJI} I am missing permission(s) to execute this command: `{', '.join(error.missing_permissions)}`",
                ephemeral=True
            )

        # Command doesn't exist'
        elif isinstance(error, app_commands.CommandNotFound):
            await send_func(
                f"{ERROR_EMOJI} Command not found!",
                ephemeral=True
            )

        # User doesn't have the required role to execute the command
        elif isinstance(error, app_commands.MissingRole):
            await send_func(
                f"{ERROR_EMOJI} You are missing the required role to execute this command!",
                ephemeral=True
            )

        # Command cannot be used in DMs
        elif isinstance(error, app_commands.NoPrivateMessage):
            await send_func(
                f"{ERROR_EMOJI} This command cannot be used in private messages!",
                ephemeral=True
            )

        # Command raised an unexpected error
        elif isinstance(error, app_commands.CommandInvokeError):
            await send_func(
                f"{ERROR_EMOJI} An error occurred while executing the command: `{str(error).capitalize()}`",
                ephemeral=True
            )

        # Bot doesn't have permission
        elif isinstance(error, discord.Forbidden):
            await send_func(
                f"{ERROR_EMOJI} I do not have the required permissions to execute this command!",
                ephemeral=True
            )

        # User is not authorized to use this command
        elif isinstance(error, app_commands.errors.CheckFailure):
            await send_func(
                f"{ERROR_EMOJI} You do not have permission to execute this command!",
                ephemeral=True
            )

        # Other errors
        else:
            self.logger.error(f"Unhandled exception in command '{command_name}': {str(error)}")
            await send_func(
                f"{ERROR_EMOJI} An unexpected error occurred while executing the command: `{str(error).capitalize()}`",
                ephemeral=True
            )


# Run the bot
bot = DiscordBot()
bot.run(TOKEN)