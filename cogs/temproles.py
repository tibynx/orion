"""Cog for temporary role management commands."""
import asyncio
import os
import json
import tempfile
import discord
from discord.ext import commands, tasks
from discord import app_commands
from config import SUCCESS_EMOJI, ERROR_EMOJI

_bot_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
TEMP_ROLES_FILE = os.path.join(_bot_dir, "temp_roles_db.json")


class TempRoles(commands.Cog):
    """Cog for managing temporary roles."""
    def __init__(self, bot):
        """Initialize the cog with the bot instance."""
        self.bot = bot
        self.temp_roles_lock = asyncio.Lock()
        self.check_temp_roles.start()

    async def cog_unload(self):
        """Cancel the background task when cog is unloaded."""
        self.check_temp_roles.cancel()

    async def load_temp_roles(self) -> list:
        """Asynchronously load temporary roles from the JSON file."""
        def _load():
            if not os.path.exists(TEMP_ROLES_FILE):
                return []
            try:
                with open(TEMP_ROLES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.bot.logger.error(f"Failed to load temp roles: {e}")
                return []
        return await asyncio.to_thread(_load)

    async def save_temp_roles(self, data: list) -> None:
        """Asynchronously save temporary roles to the JSON file."""
        def _save():
            tmp_path = None
            try:
                temp_dir = os.path.dirname(TEMP_ROLES_FILE) or "."
                fd, tmp_path = tempfile.mkstemp(
                    dir=temp_dir,
                    prefix="temp_roles_",
                    suffix=".json"
                )
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                os.replace(tmp_path, TEMP_ROLES_FILE)
            except Exception as e:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
                self.bot.logger.error(f"Failed to save temp roles: {e}")
        await asyncio.to_thread(_save)

    @tasks.loop(seconds=30)
    async def check_temp_roles(self):
        """Periodically check and remove expired temporary roles, and check for manual removals."""
        await self.bot.wait_until_ready()
        try:
            async with self.temp_roles_lock:
                temp_roles = await self.load_temp_roles()
                if not temp_roles:
                    return

                now = discord.utils.utcnow().timestamp()
                updated_temp_roles = []
                changed = False

                for record in temp_roles:
                    guild_id = record["guild_id"]
                    user_id = record["user_id"]
                    role_id = record["role_id"]
                    expires_at = record["expires_at"]

                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        # Keep the record if the guild is temporarily unavailable
                        updated_temp_roles.append(record)
                        continue

                    role = guild.get_role(role_id)
                    if not role:
                        # Role was deleted from the server
                        self.bot.logger.info(
                            f"Temporary role with ID {role_id} no longer exists. Cleaning up record."
                        )
                        changed = True
                        continue

                    member = guild.get_member(user_id)
                    if not member:
                        try:
                            member = await guild.fetch_member(user_id)
                        except discord.NotFound:
                            # Member left the server
                            self.bot.logger.info(
                                f"Member with ID {user_id} not found in guild. Cleaning up record."
                            )
                            changed = True
                            continue
                        except discord.HTTPException:
                            # Temporary issue, keep record
                            updated_temp_roles.append(record)
                            continue

                    # Check if expired
                    if now >= expires_at:
                        changed = True
                        # Check if the role was removed manually
                        if role not in member.roles:
                            self.bot.logger.info(
                                f"Temporary role '{role.name}' for user {member} was already removed "
                                "manually (detected at expiration). Cleaning up record."
                            )
                            continue

                        # Try to remove the role
                        try:
                            await member.remove_roles(role, reason="Temporary role expired.")
                            self.bot.logger.info(
                                f"Temporary role '{role.name}' expired and was removed from {member}."
                            )
                        except discord.Forbidden:
                            self.bot.logger.warning(
                                f"Cannot remove expired role '{role.name}' "
                                f"from {member}: Missing permissions."
                            )
                            # We discard the record because we can't remove it anyway
                            # (avoid infinite error loops)
                            continue
                        except discord.HTTPException as e:
                            self.bot.logger.error(
                                f"HTTP error trying to remove expired role "
                                f"'{role.name}' from {member}: {e.text}"
                            )
                            # Keep it to try again next time
                            updated_temp_roles.append(record)
                            changed = False
                    else:
                        # Not expired yet. Proactively check if it was removed manually.
                        if role not in member.roles:
                            self.bot.logger.info(
                                f"Temporary role '{role.name}' for user {member} was removed manually. "
                                "Cleaning up record."
                            )
                            changed = True
                            continue
                        updated_temp_roles.append(record)

                if changed:
                    await self.save_temp_roles(updated_temp_roles)
        except Exception as e:
            self.bot.logger.error(f"Error in check_temp_roles loop: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Listener to detect if a temporary role was removed manually by a moderator."""
        # Find if any removed role was a temporary role
        removed_roles = [r for r in before.roles if r not in after.roles]
        if not removed_roles:
            return

        try:
            async with self.temp_roles_lock:
                temp_roles = await self.load_temp_roles()
                if not temp_roles:
                    return

                updated_temp_roles = []
                changed = False
                removed_role_ids = {r.id for r in removed_roles}

                for record in temp_roles:
                    if (record["guild_id"] == before.guild.id and
                        record["user_id"] == before.id and
                        record["role_id"] in removed_role_ids):
                        self.bot.logger.info(
                            f"Temporary role ID {record['role_id']} was manually "
                            f"removed from {before}. Cleaning up record."
                        )
                        changed = True
                    else:
                        updated_temp_roles.append(record)

                if changed:
                    await self.save_temp_roles(updated_temp_roles)
        except Exception as e:
            self.bot.logger.error(
                f"Error in on_member_update listener for temp roles: {e}",
                exc_info=True
            )

    # Add temporary role
    @app_commands.command(
        name="temproleadd",
        description="Temporarily give a role to a user."
    )
    @app_commands.describe(
        user="The user to give the role to.",
        role="The role to temporarily give.",
        duration="The amount of duration to give the role for."
    )
    @app_commands.choices(duration=[
        app_commands.Choice(name="30 minutes", value=30 * 60),
        app_commands.Choice(name="1 hour", value=1 * 3600),
        app_commands.Choice(name="2 hours", value=2 * 3600),
        app_commands.Choice(name="6 hours", value=6 * 3600),
        app_commands.Choice(name="12 hours", value=12 * 3600),
        app_commands.Choice(name="1 day", value=1 * 86400),
        app_commands.Choice(name="3 days", value=3 * 86400),
        app_commands.Choice(name="5 days", value=5 * 86400),
        app_commands.Choice(name="1 week", value=7 * 86400),
    ])
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    async def temprole_add(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: discord.Role,
        duration: app_commands.Choice[int]
    ):
        """Temporarily give a role to a user for a specified duration."""
        # Defer response as database/api checks can take some time
        await interaction.response.defer(ephemeral=True)

        # Check bot's permission
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I do not have permission to manage roles in this server.",
                ephemeral=True
            )
            return

        # Check user's hierarchy (unless guild owner or has administrator permission)
        is_admin = interaction.user.guild_permissions.administrator
        if (interaction.user != interaction.guild.owner and
                not is_admin and
                role >= interaction.user.top_role):
            await interaction.followup.send(
                f"{ERROR_EMOJI} You cannot assign a role that is equal to or "
                "higher than your top role in the hierarchy.",
                ephemeral=True
            )
            return

        # Check bot's hierarchy
        if role >= interaction.guild.me.top_role:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I cannot assign this role because it is equal "
                "to or higher than my top role in the hierarchy.",
                ephemeral=True
            )
            return

        # Check if it's the guild's managed role (e.g. booster role, bot role)
        if role.managed:
            await interaction.followup.send(
                f"{ERROR_EMOJI} I cannot assign this role because it is managed by an integration.",
                ephemeral=True
            )
            return

        async with self.temp_roles_lock:
            # Load active temp roles
            temp_roles = await self.load_temp_roles()
            has_role = role in user.roles

            # Check if already tracked as a temp role
            tracked_record = None
            for record in temp_roles:
                if (record["guild_id"] == interaction.guild.id and
                        record["user_id"] == user.id and
                        record["role_id"] == role.id):
                    tracked_record = record
                    break

            # If they already have the role, but it's not a temp role, reject
            if has_role and not tracked_record:
                await interaction.followup.send(
                    f"{ERROR_EMOJI} This user already has the role {role.mention}.",
                    ephemeral=True
                )
                return

            expires_at = discord.utils.utcnow().timestamp() + duration.value

            # Assign role if they don't have it
            if not has_role:
                try:
                    await user.add_roles(
                        role,
                        reason=f"Temporary role given by {interaction.user} for {duration.name}"
                    )
                except discord.Forbidden:
                    await interaction.followup.send(
                        f"{ERROR_EMOJI} I do not have permission to assign this role.",
                        ephemeral=True
                    )
                    return

            # Save or update database record
            expires_timestamp = int(expires_at)
            if tracked_record:
                tracked_record["expires_at"] = expires_at
                message_text = (
                    f"{SUCCESS_EMOJI} Updated temporary role {role.mention} for "
                    f"{user.mention} to expire at <t:{expires_timestamp}:F> "
                    f"(<t:{expires_timestamp}:R>)."
                )
            else:
                temp_roles.append({
                    "guild_id": interaction.guild.id,
                    "user_id": user.id,
                    "role_id": role.id,
                    "expires_at": expires_at
                })
                message_text = (
                    f"{SUCCESS_EMOJI} Successfully gave {role.mention} to "
                    f"{user.mention} until <t:{expires_timestamp}:F> "
                    f"(<t:{expires_timestamp}:R>)."
                )

            await self.save_temp_roles(temp_roles)
        await interaction.followup.send(message_text, ephemeral=True)


async def setup(bot):
    """Add the TempRoles cog to the bot."""
    await bot.add_cog(TempRoles(bot))
