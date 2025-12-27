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
        await interaction.response.defer()
        await interaction.delete_original_response()

    async def confirm_button_callback(self, interaction: discord.Interaction) -> None:
        """Confirm the playback override."""
        self.confirmed = True
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
    def __init__(self, bot):
        """Initialize the cog with the bot instance."""
        self.bot = bot
        self.voice_states = {}  # guild_id -> VoiceState

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
                except Exception:
                    pass
            # Cancel cleanup task if exists
            if state.cleanup_task and not state.cleanup_task.done():
                state.cleanup_task.cancel()
            del self.voice_states[guild_id]

    async def disconnect_voice(self, voice_client: discord.VoiceClient):
        """Disconnect from voice channel and cleanup."""
        if voice_client and voice_client.is_connected():
            guild_id = voice_client.guild.id
            await voice_client.disconnect()
            self.cleanup_voice_state(guild_id)

    def after_playback(self, guild_id: int, error):
        """Callback after playback finishes or encounters an error."""
        if error:
            self.bot.logger.error(f"Playback error in guild {guild_id}: {error}")
        
        state = self.get_voice_state(guild_id)
        if state.voice_client and state.voice_client.is_connected():
            # Schedule disconnection
            state.cleanup_task = asyncio.create_task(
                self.disconnect_voice(state.voice_client)
            )

    @staticmethod
    def is_valid_audio_file(file_bytes: bytes) -> bool:
        """Check if the file is a valid audio file using magic bytes."""
        kind = filetype.guess(file_bytes)
        if kind is None:
            return False
        # Common audio MIME types
        valid_audio_types = {
            'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave', 'audio/x-wav',
            'audio/ogg', 'audio/flac', 'audio/x-flac', 'audio/aac', 'audio/m4a',
            'audio/x-m4a', 'audio/mp4', 'audio/webm', 'audio/opus'
        }
        return kind.mime in valid_audio_types

    @app_commands.command(
        name="play",
        description="Play an audio file in your current voice or stage channel."
    )
    @app_commands.guild_only()
    @app_commands.describe(
        audio_file="The audio file to play"
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

        # Download and validate the file
        try:
            file_bytes = await audio_file.read()
        except Exception as error:
            self.bot.logger.error(f"Failed to read audio file: {error}")
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to download the audio file.",
                ephemeral=True
            )

        # Validate file type
        if not self.is_valid_audio_file(file_bytes):
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Invalid file type. Please upload a valid audio file "
                "(MP3, WAV, OGG, FLAC, AAC, M4A, OPUS, WebM).",
                ephemeral=True
            )

        # Check if something is already playing
        if state.is_playing or state.is_paused:
            # Show confirmation dialog
            dialog = PlayConfirmationDialog(state.current_player.display_name)
            await interaction.followup.send(
                view=dialog,
                ephemeral=True
            )
            # Wait for user response (timeout after 60 seconds)
            try:
                await asyncio.wait_for(
                    asyncio.create_task(self._wait_for_dialog_close(dialog)),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                pass

            if not dialog.confirmed:
                return

            # Stop current playback
            if state.voice_client and state.voice_client.is_playing():
                state.voice_client.stop()

        # Save file to temp location
        try:
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
                    await state.voice_client.move_to(user_channel)
            else:
                state.voice_client = await user_channel.connect()

            # If it's a stage channel, try to become a speaker
            if isinstance(user_channel, discord.StageChannel):
                try:
                    await interaction.guild.me.edit(suppress=False)
                except discord.Forbidden:
                    pass  # Already a speaker or no permission

        except discord.ClientException as error:
            self.bot.logger.error(f"Failed to connect to voice channel: {error}")
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to connect to the voice channel.",
                ephemeral=True
            )

        # Create audio source with volume control
        try:
            audio_source = discord.FFmpegPCMAudio(temp_path)
            audio_source = discord.PCMVolumeTransformer(audio_source, volume=state.current_volume)
            state.audio_source = audio_source
        except Exception as error:
            self.bot.logger.error(f"Failed to create audio source: {error}")
            await self.disconnect_voice(state.voice_client)
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Failed to process the audio file.",
                ephemeral=True
            )

        # Play the audio
        state.voice_client.play(
            audio_source,
            after=lambda e: self.after_playback(interaction.guild_id, e)
        )
        state.is_playing = True
        state.is_paused = False
        state.current_player = interaction.user

        await interaction.followup.send(
            f"{SUCCESS_EMOJI} Now playing **{audio_file.filename}** "
            f"for {interaction.user.mention}.",
            ephemeral=True
        )

    async def _wait_for_dialog_close(self, dialog: PlayConfirmationDialog):
        """Wait for dialog to be closed."""
        while not dialog.confirmed and dialog.is_dispatching():
            await asyncio.sleep(0.1)

    @app_commands.command(
        name="pause",
        description="Pause the currently playing audio."
    )
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction) -> None:
        """Pause the current audio playback."""
        state = self.get_voice_state(interaction.guild_id)

        if not state.voice_client or not state.voice_client.is_connected():
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I'm not connected to a voice channel.",
                ephemeral=True
            )

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

        if not state.voice_client or not state.voice_client.is_connected():
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I'm not connected to a voice channel.",
                ephemeral=True
            )

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

        if not state.voice_client or not state.voice_client.is_connected():
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I'm not connected to a voice channel.",
                ephemeral=True
            )

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
    async def volume(self, interaction: discord.Interaction, volume: int) -> None:
        """Adjust the volume of the current playback."""
        state = self.get_voice_state(interaction.guild_id)

        if not state.voice_client or not state.voice_client.is_connected():
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I'm not connected to a voice channel.",
                ephemeral=True
            )

        if volume < 0 or volume > 200:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} Volume must be between 0 and 200.",
                ephemeral=True
            )

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


async def setup(bot):
    """Add the Voice cog to the bot."""
    await bot.add_cog(Voice(bot))
