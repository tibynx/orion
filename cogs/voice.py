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
    def __init__(self, current_player_name: str):
        """Initialize the dialog with the current player's name."""
        super().__init__()
        self.confirmed = False
        self.responded = asyncio.Event()
        self.timed_out = False
        self.current_player_name = current_player_name

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## File Already Playing\n"
                f"**{current_player_name}** is currently playing a file. "
                "Do you want to stop their playback and play your file instead?"
            )
        )
        # Cancel button
        cancel_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary, label="Cancel"
        )
        # Confirm button
        confirm_button = discord.ui.Button(
            style=discord.ButtonStyle.danger, label="Stop and Play"
        )
        cancel_button.callback = self.cancel_button_callback
        confirm_button.callback = self.confirm_button_callback
        buttons = discord.ui.ActionRow(cancel_button, confirm_button)
        container.add_item(buttons)
        self.add_item(container)

    async def cancel_button_callback(self, interaction: discord.Interaction) -> None:
        """Cancel the playback and remove the dialog."""
        if self.timed_out:
            # Defer, delete the original dialog, then send followup
            # This pattern works with components v2 (LayoutView)
            await interaction.response.defer()
            await interaction.delete_original_response()
            await interaction.followup.send(
                f"{ERROR_EMOJI} This confirmation has expired. Please try the command again.",
                ephemeral=True
            )
            return
        self.confirmed = False
        self.responded.set()
        await interaction.response.defer()
        await interaction.delete_original_response()

    async def confirm_button_callback(self, interaction: discord.Interaction) -> None:
        """Confirm the playback override."""
        if self.timed_out:
            # Defer, delete the original dialog, then send followup
            # This pattern works with components v2 (LayoutView)
            await interaction.response.defer()
            await interaction.delete_original_response()
            await interaction.followup.send(
                f"{ERROR_EMOJI} This confirmation has expired. Please try the command again.",
                ephemeral=True
            )
            return
        self.confirmed = True
        self.responded.set()
        await interaction.response.defer()
        await interaction.delete_original_response()


class VoiceState:
    """Represents the voice state of a guild."""
    def __init__(self):
        """Initialize voice state."""
        self.voice_client: Optional[discord.VoiceClient] = None
        self.current_player: Optional[discord.Member] = None
        self.is_playing = False
        self.is_paused = False
        self.current_volume = 0.5
        self.audio_source: Optional[discord.AudioSource] = None
        self.temp_file_path: Optional[str] = None
        self.cleanup_task: Optional[asyncio.Task] = None


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
        """Initialize the cog with the bot instance."""
        self.bot = bot
        self.voice_states = {}  # guild_id -> VoiceState
        
        # Load Opus library for voice support (especially needed in Docker containers)
        # This attempts to load the system's Opus library if not already loaded
        if not discord.opus.is_loaded():
            try:
                discord.opus.load_opus()
                self.bot.logger.info("Successfully loaded Opus library for voice support")
            except Exception as e:
                self.bot.logger.warning(
                    f"Failed to load Opus library: {e}. Voice playback may not work."
                )

    def get_voice_state(self, guild_id: int) -> VoiceState:
        """Get or create a voice state for a guild."""
        if guild_id not in self.voice_states:
            self.voice_states[guild_id] = VoiceState()
        return self.voice_states[guild_id]

    def cleanup_voice_state(self, guild_id: int):
        """Clean up voice state for a guild."""
        if guild_id in self.voice_states:
            state = self.voice_states[guild_id]
            # Clean up temp file if exists
            if state.temp_file_path and os.path.exists(state.temp_file_path):
                try:
                    os.remove(state.temp_file_path)
                except (OSError, PermissionError) as error:
                    self.bot.logger.warning(
                        f"Failed to remove temp file {state.temp_file_path}: {error}"
                    )
            # Cancel cleanup task if exists
            if state.cleanup_task and not state.cleanup_task.done():
                state.cleanup_task.cancel()
            del self.voice_states[guild_id]

    async def disconnect_voice(self, voice_client: discord.VoiceClient):
        """Disconnect from voice channel and cleanup."""
        if voice_client:
            guild_id = voice_client.guild.id
            # Disconnect even if not showing as connected to ensure cleanup
            if voice_client.is_connected():
                await voice_client.disconnect()
            # Clear the voice_client reference in state before cleanup
            if guild_id in self.voice_states:
                self.voice_states[guild_id].voice_client = None
            self.cleanup_voice_state(guild_id)

    def check_user_in_voice_channel(
        self, interaction: discord.Interaction, state: VoiceState
    ) -> tuple[bool, str]:
        """Check if user is in the same voice channel as the bot.
        
        Returns:
            tuple: (is_valid, error_message) - is_valid is True if check passes,
                   error_message is set if check fails
        """
        if not state.voice_client or not state.voice_client.is_connected():
            return False, f"{ERROR_EMOJI} I'm not connected to a voice channel."
        
        if not interaction.user.voice or interaction.user.voice.channel != state.voice_client.channel:
            return False, f"{ERROR_EMOJI} You must be in the same voice channel as me to use this command."
        
        return True, ""

    def _handle_cleanup_exception(self, guild_id: int):
        """Create a callback function to handle exceptions from cleanup futures."""
        def callback(fut):
            try:
                fut.result()
            except Exception as exc:
                self.bot.logger.error(f"Error during cleanup in guild {guild_id}: {exc}")
        return callback

    def after_playback(self, guild_id: int, error):
        """Callback after playback finishes or encounters an error."""
        if error:
            self.bot.logger.error(f"Playback error in guild {guild_id}: {error}")
        
        state = self.get_voice_state(guild_id)
        if state.voice_client and state.voice_client.is_connected():
            # Schedule disconnection using bot's loop (thread-safe)
            future = asyncio.run_coroutine_threadsafe(
                self.disconnect_voice(state.voice_client),
                self.bot.loop
            )
            # Add callback to log any exceptions
            future.add_done_callback(self._handle_cleanup_exception(guild_id))

    @staticmethod
    def is_valid_audio_file(file_bytes: bytes, filename: str) -> bool:
        """Check if the file is a valid audio file using magic bytes and extension.
        
        Note: M4A audio files are often detected as video/mp4 MIME type because
        they use the MP4 container format. We use file extension as additional
        validation to distinguish M4A audio from MP4 video files.
        """
        kind = filetype.guess(file_bytes)
        if kind is None:
            return False
        
        # Get file extension using os.path.splitext for reliability
        file_ext = os.path.splitext(filename.lower())[1].lstrip('.')
        
        # For video/mp4 MIME type, only accept if extension is m4a (audio)
        if kind.mime == 'video/mp4':
            return file_ext == 'm4a'
        
        # For other MIME types, check against valid audio types
        return kind.mime in Voice.VALID_AUDIO_MIME_TYPES

    @app_commands.command(
        name="play",
        description="Play an audio file in your current voice or stage channel."
    )
    @app_commands.guild_only()
    @app_commands.describe(
        audio_file="Audio file to play (MP3, WAV, OGG, FLAC, AAC, M4A, OPUS, WebM - max 25MB)"
    )
    async def play(
        self, interaction: discord.Interaction, audio_file: discord.Attachment
    ) -> None:
        """Play an audio file in the user's voice channel."""
        await interaction.response.defer(ephemeral=True)

        # Check if user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send(
                f"{ERROR_EMOJI} You must be in a voice or stage channel to use this command.",
                ephemeral=True
            )

        user_channel = interaction.user.voice.channel
        state = self.get_voice_state(interaction.guild_id)

        # Check if bot can connect to the channel
        permissions = user_channel.permissions_for(interaction.guild.me)
        if not permissions.connect or not permissions.speak:
            return await interaction.followup.send(
                f"{ERROR_EMOJI} I don't have permission to connect or speak in that channel.",
                ephemeral=True
            )

        # Download and validate the file BEFORE connecting
        try:
            file_bytes = await audio_file.read()
        except Exception as error:
            self.bot.logger.error(f"Failed to read audio file: {error}")
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to download the audio file.",
                ephemeral=True
            )

        # Validate file type
        if not self.is_valid_audio_file(file_bytes, audio_file.filename):
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Invalid file type. Please upload a valid audio file "
                f"({self.SUPPORTED_FORMATS}).",
                ephemeral=True
            )

        # Check if something is already playing
        if state.is_playing or state.is_paused:
            # Show confirmation dialog
            current_player_name = (
                state.current_player.display_name if state.current_player else "Someone"
            )
            dialog = PlayConfirmationDialog(current_player_name)
            message = await interaction.followup.send(
                view=dialog,
                ephemeral=True
            )
            # Wait for user response (timeout after 60 seconds)
            try:
                await asyncio.wait_for(dialog.responded.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                dialog.timed_out = True
                self.bot.logger.info(
                    f"Play confirmation dialog timed out for user {interaction.user.name} "
                    f"(ID: {interaction.user.id}) in guild {interaction.guild.name}"
                )
                # Delete the dialog message and send a followup instead of editing
                # LayoutView messages can't be edited to plain text properly
                await message.delete()
                await interaction.followup.send(
                    f"{ERROR_EMOJI} Confirmation timed out. Please try again.",
                    ephemeral=True
                )
                return

            if not dialog.confirmed:
                return

            # Stop current playback and update state
            if state.voice_client and state.voice_client.is_playing():
                state.voice_client.stop()
            state.is_playing = False
            state.is_paused = False

        # Save file to temp location
        try:
            # Clean up any existing temp file before creating a new one
            # (only if it's not currently being played)
            if state.temp_file_path and os.path.exists(state.temp_file_path):
                # Only clean up if not currently playing
                if not (state.voice_client and state.voice_client.is_playing()):
                    try:
                        os.remove(state.temp_file_path)
                        state.temp_file_path = None
                    except (OSError, PermissionError) as cleanup_error:
                        self.bot.logger.warning(f"Failed to remove old temp file: {cleanup_error}")
            
            # Create temp file with proper extension
            file_ext = os.path.splitext(audio_file.filename)[1] or '.mp3'
            temp_fd, temp_path = tempfile.mkstemp(suffix=file_ext)
            os.write(temp_fd, file_bytes)
            os.close(temp_fd)
            state.temp_file_path = temp_path
        except Exception as error:
            self.bot.logger.error(f"Failed to save temp file: {error}")
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to process the audio file.",
                ephemeral=True
            )

        # Connect to voice channel
        try:
            if state.voice_client and state.voice_client.is_connected():
                if state.voice_client.channel != user_channel:
                    # Add timeout to prevent hanging
                    await asyncio.wait_for(
                        state.voice_client.move_to(user_channel),
                        timeout=10.0
                    )
            else:
                # Add timeout to prevent hanging
                state.voice_client = await asyncio.wait_for(
                    user_channel.connect(),
                    timeout=10.0
                )

            # If it's a stage channel, try to become a speaker
            if isinstance(user_channel, discord.StageChannel):
                try:
                    await interaction.guild.me.edit(suppress=False)
                except discord.Forbidden:
                    pass  # Already a speaker or no permission

        except asyncio.TimeoutError:
            self.bot.logger.error(f"Connection to voice channel timed out")
            # Terminate the voice handshake if it's still in progress
            if state.voice_client:
                try:
                    await state.voice_client.disconnect(force=True)
                except Exception as disconnect_error:
                    self.bot.logger.warning(f"Error disconnecting after timeout: {disconnect_error}")
                state.voice_client = None
            # Clean up temp file since we won't be playing it
            if state.temp_file_path and os.path.exists(state.temp_file_path):
                try:
                    os.remove(state.temp_file_path)
                    state.temp_file_path = None
                except (OSError, PermissionError) as cleanup_error:
                    self.bot.logger.warning(f"Failed to remove temp file: {cleanup_error}")
            # Use followup.send with wait=False to ensure message is delivered even after dialog
            await interaction.followup.send(
                f"{ERROR_EMOJI} Connection to voice channel timed out. The channel may be unavailable.",
                ephemeral=True,
                wait=False
            )
            return
        except discord.ClientException as error:
            self.bot.logger.error(f"Failed to connect to voice channel: {error}")
            # Clean up temp file since we won't be playing it
            if state.temp_file_path and os.path.exists(state.temp_file_path):
                try:
                    os.remove(state.temp_file_path)
                    state.temp_file_path = None
                except (OSError, PermissionError) as cleanup_error:
                    self.bot.logger.warning(f"Failed to remove temp file: {cleanup_error}")
            # Check if it's a user limit error
            error_msg = str(error).lower()
            if "full" in error_msg or "user limit" in error_msg or "maximum" in error_msg:
                # Use followup.send with wait=False to ensure message is delivered even after dialog
                await interaction.followup.send(
                    f"{ERROR_EMOJI} Cannot connect to the voice channel. "
                    "The channel has reached its user limit.",
                    ephemeral=True,
                    wait=False
                )
            else:
                # Use followup.send with wait=False to ensure message is delivered even after dialog
                await interaction.followup.send(
                    f"{ERROR_EMOJI} Failed to connect to the voice channel.",
                    ephemeral=True,
                    wait=False
                )
            return
        except Exception as error:
            self.bot.logger.error(f"Unexpected error connecting to voice channel: {error}")
            # Clean up temp file since we won't be playing it
            if state.temp_file_path and os.path.exists(state.temp_file_path):
                try:
                    os.remove(state.temp_file_path)
                    state.temp_file_path = None
                except (OSError, PermissionError) as cleanup_error:
                    self.bot.logger.warning(f"Failed to remove temp file: {cleanup_error}")
            # Use followup.send with wait=False to ensure message is delivered even after dialog
            await interaction.followup.send(
                f"{ERROR_EMOJI} An unexpected error occurred while connecting to the voice channel.",
                ephemeral=True,
                wait=False
            )
            return

        # Create audio source with volume control
        try:
            audio_source = discord.FFmpegPCMAudio(temp_path)
            audio_source = discord.PCMVolumeTransformer(audio_source, volume=state.current_volume)
            state.audio_source = audio_source
        except FileNotFoundError:
            self.bot.logger.error("FFmpeg not found or not in PATH")
            await self.disconnect_voice(state.voice_client)
            return await interaction.followup.send(
                f"{ERROR_EMOJI} FFmpeg not found or not accessible. Voice playback is unavailable.",
                ephemeral=True
            )
        except Exception as error:
            self.bot.logger.error(f"Failed to create audio source: {error}")
            await self.disconnect_voice(state.voice_client)
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to process the audio file.",
                ephemeral=True
            )

        # Play the audio
        try:
            state.voice_client.play(
                audio_source,
                after=lambda e: self.after_playback(interaction.guild_id, e)
            )
        except discord.opus.OpusNotLoaded:
            self.bot.logger.error("Opus library not found or not loaded")
            await self.disconnect_voice(state.voice_client)
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Opus library not found or not loaded. Voice playback is unavailable.",
                ephemeral=True,
                wait=False
            )
        
        state.is_playing = True
        state.is_paused = False
        state.current_player = interaction.user

        await interaction.followup.send(
            f"{SUCCESS_EMOJI} Now playing **{audio_file.filename}** "
            f"in {user_channel.mention}.",
            ephemeral=True
        )

    @app_commands.command(
        name="pause",
        description="Pause the currently playing audio."
    )
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction) -> None:
        """Pause the current audio playback."""
        state = self.get_voice_state(interaction.guild_id)

        # Check if user is in the same voice channel
        is_valid, error_msg = self.check_user_in_voice_channel(interaction, state)
        if not is_valid:
            return await interaction.response.send_message(error_msg, ephemeral=True)

        if not state.is_playing or state.is_paused:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} No audio is currently playing.",
                ephemeral=True
            )

        state.voice_client.pause()
        state.is_paused = True
        state.is_playing = False

        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Paused playback.",
            ephemeral=True
        )

    @app_commands.command(
        name="resume",
        description="Resume the paused audio."
    )
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction) -> None:
        """Resume paused audio playback."""
        state = self.get_voice_state(interaction.guild_id)

        # Check if user is in the same voice channel
        is_valid, error_msg = self.check_user_in_voice_channel(interaction, state)
        if not is_valid:
            return await interaction.response.send_message(error_msg, ephemeral=True)

        if not state.is_paused:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} Audio is not paused.",
                ephemeral=True
            )

        state.voice_client.resume()
        state.is_paused = False
        state.is_playing = True

        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Resumed playback.",
            ephemeral=True
        )

    @app_commands.command(
        name="stop",
        description="Stop the currently playing audio and disconnect."
    )
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop audio playback and disconnect from voice channel."""
        state = self.get_voice_state(interaction.guild_id)

        # Check if user is in the same voice channel
        is_valid, error_msg = self.check_user_in_voice_channel(interaction, state)
        if not is_valid:
            return await interaction.response.send_message(error_msg, ephemeral=True)

        if state.voice_client.is_playing() or state.voice_client.is_paused():
            state.voice_client.stop()

        await self.disconnect_voice(state.voice_client)

        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Stopped playback and disconnected.",
            ephemeral=True
        )

    @app_commands.command(
        name="volume",
        description="Adjust the playback volume (0-200%)."
    )
    @app_commands.guild_only()
    @app_commands.describe(
        volume="Volume level (0-200)"
    )
    async def volume(
        self, interaction: discord.Interaction, volume: app_commands.Range[int, 0, 200]
    ) -> None:
        """Adjust the volume of the current playback."""
        state = self.get_voice_state(interaction.guild_id)

        # Check if user is in the same voice channel
        is_valid, error_msg = self.check_user_in_voice_channel(interaction, state)
        if not is_valid:
            return await interaction.response.send_message(error_msg, ephemeral=True)

        # Convert percentage to decimal
        volume_decimal = volume / 100.0
        state.current_volume = volume_decimal

        # Update current audio source if playing
        if state.audio_source and isinstance(state.audio_source, discord.PCMVolumeTransformer):
            state.audio_source.volume = volume_decimal

        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Volume set to {volume}%.",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """Handle bot disconnection from voice channel."""
        # Check if the bot was disconnected
        if member == member.guild.me and before.channel and not after.channel:
            state = self.get_voice_state(member.guild.id)
            # Clean up if forcefully disconnected
            if state.voice_client:
                self.cleanup_voice_state(member.guild.id)

    async def cog_unload(self):
        """Clean up resources when cog is unloaded."""
        for guild_id in list(self.voice_states.keys()):
            state = self.voice_states[guild_id]
            if state.voice_client and state.voice_client.is_connected():
                await state.voice_client.disconnect()
            if state.cleanup_task and not state.cleanup_task.done():
                state.cleanup_task.cancel()
                try:
                    await state.cleanup_task
                except asyncio.CancelledError:
                    pass
            self.cleanup_voice_state(guild_id)


async def setup(bot):
    """Add the Voice cog to the bot."""
    await bot.add_cog(Voice(bot))
