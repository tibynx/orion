"""Cog for voice channel playback and control."""
import asyncio
import os
import tempfile
from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands
import filetype
from config import SUCCESS_EMOJI, ERROR_EMOJI


# Confirmation dialog for playing when another file is playing/paused
class PlayConfirmationDialog(discord.ui.LayoutView):
    """View for confirming playback when another file is already playing."""
    def __init__(
            self, cog: 'Voice', interaction: discord.Interaction,
            file_bytes: bytes, filename: str
    ):
        """Initialize the dialog with necessary data for playback."""
        super().__init__(timeout=60.0)
        self.cog = cog
        self.interaction = interaction
        self.file_bytes = file_bytes
        self.filename = filename

        # Get the current player name for the message
        state = cog.get_voice_state(interaction.guild_id)
        current_player_name = state.current_player.display_name if state.current_player else "Someone"

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## File Already Playing\n"
                f"**{current_player_name}** is currently playing a file. "
                "Do you want to stop their playback and play your file instead?"
            )
        )
        # Buttons
        cancel_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary, label="Cancel"
        )
        confirm_button = discord.ui.Button(
            style=discord.ButtonStyle.danger, label="Stop and Play"
        )

        cancel_button.callback = self.cancel_callback
        confirm_button.callback = self.confirm_callback

        container.add_item(discord.ui.ActionRow(cancel_button, confirm_button))
        self.add_item(container)

    async def cancel_callback(self, interaction: discord.Interaction):
        """Cancel override."""
        await interaction.response.defer()
        await interaction.delete_original_response()

    async def confirm_callback(self, interaction: discord.Interaction):
        """Confirm override and start new playback."""
        await interaction.response.defer()
        await interaction.delete_original_response()
        # Call the cog's internal play method
        await self.cog.start_playback(
            self.interaction,
            self.file_bytes,
            self.filename,
            override=True
        )

    async def on_timeout(self):
        """Handle timeout by deleting the dialog message."""
        try:
            await self.interaction.delete_original_response()
        except discord.HTTPException:
            pass


class VoiceState:
    """Represents the voice state of a guild."""
    def __init__(self):
        """Initialize voice state."""
        self.voice_client: Optional[discord.VoiceClient] = None
        self.current_player: Optional[discord.Member] = None
        self.current_volume = 0.5
        self.audio_source: Optional[discord.AudioSource] = None
        self.temp_file_path: Optional[str] = None
        self.switching = False  # Flag to prevent disconnect when switching files


class Voice(commands.Cog):
    """Cog for voice channel audio playback and control."""
    # Supported audio formats
    SUPPORTED_FORMATS = "MP3, WAV, OGG, FLAC, AAC, M4A, OPUS, WebM"
    # Valid MIME types for audio files
    VALID_AUDIO_MIME_TYPES = {
        'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave', 'audio/x-wav',
        'audio/ogg', 'audio/flac', 'audio/x-flac', 'audio/aac', 'audio/m4a',
        'audio/x-m4a', 'audio/mp4', 'audio/webm', 'audio/opus',
        'video/mp4',  # M4A files use MP4 container
    }
    def __init__(self, bot):
        """Initialize the cog with the bot instance and load Opus."""
        self.bot = bot
        self.voice_states = {}  # guild_id -> VoiceState
        self._load_opus()

    def _load_opus(self):
        """Load the Opus library for voice support."""
        if discord.opus.is_loaded():
            return

        # Common library names for various platforms
        opus_libs = [
            'libopus.so.0',
            'libopus.so',
            'opus',
            'libopus-0.x64.dll',
            'libopus-0.x86.dll',
            'libopus-0.dll',
            'opus.dll'
        ]
        for lib in opus_libs:
            try:
                discord.opus.load_opus(lib)
                self.bot.logger.info(f"Successfully loaded Opus: {lib}")
                return
            except Exception:
                continue

        self.bot.logger.warning("Failed to load Opus library. Voice playback might not work.")

    def get_voice_state(self, guild_id: int) -> VoiceState:
        """Get or create a voice state for a guild."""
        if guild_id not in self.voice_states:
            self.voice_states[guild_id] = VoiceState()
        return self.voice_states[guild_id]

    def cleanup_voice_state(self, guild_id: int):
        """Clean up voice state for a guild."""
        if state := self.voice_states.pop(guild_id, None):
            # Clean up temp file if exists
            if state.temp_file_path and os.path.exists(state.temp_file_path):
                try:
                    os.remove(state.temp_file_path)
                except (OSError, PermissionError) as error:
                    self.bot.logger.warning(
                        f"Failed to remove temp file {state.temp_file_path}: {error}"
                    )

    async def disconnect_voice(self, voice_client: discord.VoiceClient):
        """Disconnect from a voice channel and cleanup."""
        if voice_client:
            guild_id = voice_client.guild.id
            if voice_client.is_connected():
                await voice_client.disconnect()
            # Ensure the state is cleaned up
            self.cleanup_voice_state(guild_id)

    def check_user_in_voice_channel(
        self, interaction: discord.Interaction, state: VoiceState
    ) -> tuple[bool, str]:
        """Check if the user is in the same voice channel as the bot."""
        if not state.voice_client or not state.voice_client.is_connected():
            return False, f"{ERROR_EMOJI} I'm not connected to a voice channel."
        if not interaction.user.voice or interaction.user.voice.channel != state.voice_client.channel:
            return False, (f"{ERROR_EMOJI} You must be in the same "
                           "voice channel as me to use this command.")
        return True, ""

    def after_playback(self, guild_id: int, error: Optional[Exception]):
        """Callback after playback finishes or encounters an error."""
        if error:
            self.bot.logger.error(f"Playback error in Guild ID {guild_id}: {error}")

        state = self.voice_states.get(guild_id)
        if not state:
            return

        if state.switching:
            state.switching = False
            return

        if state.voice_client and state.voice_client.is_connected():
            asyncio.run_coroutine_threadsafe(
                self.disconnect_voice(state.voice_client),
                self.bot.loop
            )

    @staticmethod
    def is_valid_audio_file(file_bytes: bytes, filename: str) -> bool:
        """Check if the file is a valid audio file using magic bytes and extension.
        
        Note: M4A audio files are often detected as a video/mp4 MIME type because
        they use the MP4 container format. We use file extension as additional
        validation to distinguish M4A audio from MP4 video files.
        """
        kind = filetype.guess(file_bytes)
        if kind is None:
            return False
        # Get file extension using os.path.splitext for reliability
        file_ext = os.path.splitext(filename.lower())[1].lstrip('.')
        # For video/mp4 MIME type, only accept if the extension is m4a (audio)
        if kind.mime == 'video/mp4':
            return file_ext == 'm4a'
        # For other MIME types, check against valid audio types
        return kind.mime in Voice.VALID_AUDIO_MIME_TYPES

    @app_commands.command(
        name="play",
        description="Play an audio file in your current voice or stage channel."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True, connect=True)
    @app_commands.describe(
        audio_file="Audio file to play (MP3, WAV, OGG, FLAC, AAC, M4A, OPUS, WebM - max 25MB)"
    )
    async def play(
        self, interaction: discord.Interaction, audio_file: discord.Attachment
    ) -> None:
        """Play an audio file in the user's voice channel."""
        await interaction.response.defer(ephemeral=True)

        # Check if the user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send(
                f"{ERROR_EMOJI} You must be in a voice or stage channel to use this command.",
                ephemeral=True
            )

        user_channel = interaction.user.voice.channel
        permissions = user_channel.permissions_for(interaction.guild.me)
        if not permissions.connect or not permissions.speak:
            return await interaction.followup.send(
                f"{ERROR_EMOJI} I don't have permission to connect or speak in that channel.",
                ephemeral=True
            )

        # Download and validate
        try:
            file_bytes = await audio_file.read()
        except Exception as error:
            self.bot.logger.error(
                f"Failed to read audio file in Guild ID {interaction.guild_id}: {error}"
            )
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to download the audio file.",
                ephemeral=True
            )

        if not self.is_valid_audio_file(file_bytes, audio_file.filename):
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Invalid file type. Supported file types: {self.SUPPORTED_FORMATS}",
                ephemeral=True
            )

        state = self.get_voice_state(interaction.guild_id)
        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            # Show confirmation dialog
            view = PlayConfirmationDialog(self, interaction, file_bytes, audio_file.filename)
            return await interaction.followup.send(view=view, ephemeral=True)

        await self.start_playback(interaction, file_bytes, audio_file.filename)
        return None

    async def start_playback(
        self, interaction: discord.Interaction, file_bytes: bytes,
        filename: str, override: bool = False
    ) -> None:
        """Internal method to handle audio playback logic."""
        state = self.get_voice_state(interaction.guild_id)
        user_channel = interaction.user.voice.channel

        if override and state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            state.switching = True
            state.voice_client.stop()
            # Wait briefly for the audio player to stop
            for _ in range(10):
                if not (state.voice_client.is_playing() or state.voice_client.is_paused()):
                    break
                await asyncio.sleep(0.1)

        # Save to a temp file
        temp_path = None
        try:
            # Clean up old temp file if not playing
            if state.temp_file_path and os.path.exists(state.temp_file_path):
                if not (state.voice_client and state.voice_client.is_playing()):
                    try:
                        os.remove(state.temp_file_path)
                    except (OSError, PermissionError):
                        pass

            file_ext = os.path.splitext(filename)[1]
            fd, temp_path = tempfile.mkstemp(suffix=file_ext if file_ext else '')
            os.write(fd, file_bytes)
            os.close(fd)
            state.temp_file_path = temp_path

        except Exception as error:
            self.bot.logger.error(f"Temp file error in Guild ID {interaction.guild_id}: {error}")
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to process the audio file.",
                ephemeral=True
            )

        # Connect to voice
        try:
            if state.voice_client and state.voice_client.is_connected():
                if state.voice_client.channel != user_channel:
                    await asyncio.wait_for(state.voice_client.move_to(user_channel), timeout=10.0)
            else:
                state.voice_client = await asyncio.wait_for(user_channel.connect(), timeout=10.0)

            if isinstance(user_channel, discord.StageChannel):
                try:
                    await interaction.guild.me.edit(suppress=False)
                except discord.Forbidden:
                    pass
        except Exception as error:
            self.bot.logger.error(
                f"Voice connection error in Guild ID {interaction.guild_id}: {error}"
            )
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

            msg = f"{ERROR_EMOJI} Failed to connect to voice channel."
            if isinstance(error, asyncio.TimeoutError):
                msg = f"{ERROR_EMOJI} Voice connection timed out. Maybe the channel is full?"

            return await interaction.followup.send(msg, ephemeral=True)

        # Play audio
        try:
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(temp_path),
                volume=state.current_volume
            )
            state.audio_source = source
            state.voice_client.play(
                source, after=lambda e: self.after_playback(interaction.guild_id, e)
            )
            state.current_player = interaction.user

            await interaction.followup.send(
                f"{SUCCESS_EMOJI} Playing **{filename}** in {user_channel.mention}.",
                ephemeral=True
            )
        except Exception as error:
            self.bot.logger.error(
                f"Playback start error in Guild ID {interaction.guild_id}: {error}"
            )
            await self.disconnect_voice(state.voice_client)
            await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to start playback.",
                ephemeral=True
            )

    @app_commands.command(
        name="pause",
        description="Pause the currently playing audio."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True, connect=True)
    async def pause(self, interaction: discord.Interaction) -> None:
        """Pause the current audio playback."""
        state = self.get_voice_state(interaction.guild_id)

        is_valid, error_msg = self.check_user_in_voice_channel(interaction, state)
        if not is_valid:
            return await interaction.response.send_message(error_msg, ephemeral=True)

        if not state.voice_client.is_playing():
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} No audio is currently playing.",
                ephemeral=True
            )

        state.voice_client.pause()
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Paused playback.",
            ephemeral=True
        )
        return None

    @app_commands.command(
        name="resume",
        description="Resume the paused audio."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True, connect=True)
    async def resume(self, interaction: discord.Interaction) -> None:
        """Resume paused audio playback."""
        state = self.get_voice_state(interaction.guild_id)

        is_valid, error_msg = self.check_user_in_voice_channel(interaction, state)
        if not is_valid:
            return await interaction.response.send_message(error_msg, ephemeral=True)

        if not state.voice_client.is_paused():
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} Audio is not paused.",
                ephemeral=True
            )

        state.voice_client.resume()
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Resumed playback.",
            ephemeral=True
        )
        return None

    @app_commands.command(
        name="stop",
        description="Stop the currently playing audio and disconnect."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True, connect=True)
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop audio playback and disconnect from the voice channel."""
        state = self.get_voice_state(interaction.guild_id)

        is_valid, error_msg = self.check_user_in_voice_channel(interaction, state)
        if not is_valid:
            return await interaction.response.send_message(error_msg, ephemeral=True)

        await self.disconnect_voice(state.voice_client)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Stopped playback and disconnected.",
            ephemeral=True
        )
        return None

    @app_commands.command(
        name="volume",
        description="Adjust the playback volume (0-200%)."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True, connect=True)
    @app_commands.describe(volume="Volume level (0-200)")
    async def volume(
        self, interaction: discord.Interaction, volume: app_commands.Range[int, 0, 200]
    ) -> None:
        """Adjust the volume of the current playback."""
        state = self.get_voice_state(interaction.guild_id)

        is_valid, error_msg = self.check_user_in_voice_channel(interaction, state)
        if not is_valid:
            return await interaction.response.send_message(error_msg, ephemeral=True)

        # Convert percentage to decimal
        volume_decimal = volume / 100.0
        state.current_volume = volume_decimal

        if state.audio_source:
            state.audio_source.volume = volume_decimal

        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Volume set to {volume}%.",
            ephemeral=True
        )
        return None

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """Handle bot disconnection from the voice channel."""
        if member == member.guild.me and before.channel and not after.channel:
            self.cleanup_voice_state(member.guild.id)

    async def cog_unload(self):
        """Clean up resources when cog is unloaded."""
        for guild_id in list(self.voice_states.keys()):
            state = self.voice_states.get(guild_id)
            if state and state.voice_client and state.voice_client.is_connected():
                await state.voice_client.disconnect()
            self.cleanup_voice_state(guild_id)


async def setup(bot):
    """Add the Voice cog to the bot."""
    await bot.add_cog(Voice(bot))
