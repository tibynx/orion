from typing import Union

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

from config import EMBED_COLOR, INFO_EMOJI, SUCCESS_EMOJI, ERROR_EMOJI


class Webhook(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # Group for webhook management
    webhook_edit_group = app_commands.Group(
        name="webhookedit",
        description="Edit webhook details",
        default_permissions=discord.Permissions(manage_webhooks=True),
        guild_only=True
    )

    # Group for sending messages
    webhook_send_group = app_commands.Group(
        name="webhookmsg",
        description="Send messages through webhooks",
        default_permissions=discord.Permissions(manage_webhooks=True),
        guild_only=True
    )
    webhook_send_url_group = app_commands.Group(
        name="url",
        description="Use webhook URL to send messages",
        parent=webhook_send_group
    )
    webhook_send_id_group = app_commands.Group(
        name="id",
        description="Use webhook ID to send messages",
        parent=webhook_send_group
    )

    # Get details about a webhook
    @app_commands.command(
        name="webhookget",
        description="Get details about a webhook"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        webhook_id="The ID of the webhook to fetch"
    )
    async def get_webhook(self, interaction: discord.Interaction, webhook_id: str) -> None:
        """Get details about a webhook by its ID"""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            embed = discord.Embed(title=INFO_EMOJI + " Webhook Details", color=EMBED_COLOR)
            embed.add_field(name="Name", value=webhook.name, inline=True)
            embed.add_field(name="Channel", value=webhook.channel.mention, inline=True)
            embed.add_field(name="Type", value=webhook.type.name.title(), inline=True)
            embed.add_field(name="Created by", value=webhook.user.mention, inline=True)
            embed.add_field(name="Created at", value=f"<t:{int(webhook.created_at.timestamp())}:R>", inline=True)
            embed.add_field(name="ID", value=f"`{webhook.id}`", inline=True)
            embed.add_field(name="URL", value=f"||`{webhook.url}`||", inline=False)

            if webhook.avatar:
                embed.set_thumbnail(url=webhook.avatar.url)

            return await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.NotFound:
            return await interaction.response.send_message(f"{ERROR_EMOJI} The specified webhook cannot be found!", ephemeral=True)


    # List all webhooks
    @app_commands.command(
        name="webhooklist",
        description="List all webhooks in the current server"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    async def list_webhook(self, interaction: discord.Interaction) -> None:
        """List all webhooks in the current server"""
        webhooks = await interaction.guild.webhooks()
        if not webhooks:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} No webhooks found in this server!",
                ephemeral=True
            )

        embed = discord.Embed(title=f"{INFO_EMOJI} Webhooks in this Server", color=EMBED_COLOR)
        for webhook in webhooks:
            embed.add_field(
                name=webhook.name,
                value=f"ID: ||`{webhook.id}`||\nURL: ||`{webhook.url}`||\nChannel: {webhook.channel.mention}\nCreated by: {webhook.user.mention}",
                inline=False
            )
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    # Create a webhook
    @app_commands.command(
        name="webhookcreate",
        description="Create a webhook. The webhook will be associated with this bot!"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        channel="The channel to create the webhook in",
        name="The name of the webhook"
    )
    async def create_bot_webhook(
        self, interaction: discord.Interaction,
        channel: Union[discord.TextChannel, discord.ForumChannel, discord.StageChannel, discord.VoiceChannel],
        name: str
    ) -> None:
        """Create a webhook in the specified channel with the given name"""
        webhook = await channel.create_webhook(name=name)
        embed = discord.Embed(title=SUCCESS_EMOJI + " Webhook Created", color=EMBED_COLOR)
        embed.add_field(name="Name", value=webhook.name, inline=True)
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="ID", value=f"`{webhook.id}`", inline=True)
        embed.add_field(name="URL", value=f"||`{webhook.url}`||", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Delete a webhook
    @app_commands.command(
        name="webhookdelete",
        description="Delete a webhook by its ID"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        webhook_id="The ID of the webhook to delete"
    )
    async def delete_webhook(self, interaction: discord.Interaction, webhook_id: str) -> None:
        """Delete a webhook by its ID"""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            await webhook.delete()
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Webhook deleted successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} I do not have permission to delete this webhook!",
                ephemeral=True
            )

    # Send a message through a webhook using its URL
    @webhook_send_url_group.command(
        name="text",
        description="Send a text message through a webhook URL"
    )
    @app_commands.describe(
        webhook_url="The URL of the webhook",
        message="The message to send"
    )
    async def webhook_send_url_text(self, interaction: discord.Interaction, webhook_url: str, message: str) -> None:
        """Send a text message through a webhook URL"""
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                await webhook.send(content=message)

            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Message sent successfully!",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Invalid webhook URL!",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Failed to send message: `{str(e).capitalize()}`",
                ephemeral=True
            )

    # Send a message through a webhook using its ID
    @webhook_send_id_group.command(
        name="text",
        description="Send a text message through a webhook using its ID"
    )
    @app_commands.describe(
        webhook_id="The ID of the webhook",
        message="The message to send"
    )
    async def webhook_send_text_id(self, interaction: discord.Interaction, webhook_id: str, message: str) -> None:
        """Send a text message through a webhook using its ID"""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            await webhook.send(content=message)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Message sent successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
                ephemeral=True
            )

    # Send a message through a webhook from a file using webhook ID
    @webhook_send_id_group.command(
        name="file",
        description="Send contents of a text file through a webhook using its ID"
    )
    @app_commands.describe(
        webhook_id="The ID of the webhook",
        file="The text file containing the message to send"
    )
    async def webhook_send_file(self, interaction: discord.Interaction, webhook_id: str, file: discord.Attachment) -> None:
        """Send the contents of a text file through the specified webhook"""
        if not file.filename.endswith('.txt'):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Only .txt files are supported!",
                ephemeral=True
            )
            return

        try:
            # Download and read the file content
            file_content = await file.read()
            message_content = file_content.decode('utf-8')

            # Check if content exceeds Discord's character limit
            if len(message_content) > 2000:
                await interaction.response.send_message(
                    f"{ERROR_EMOJI} File content exceeds Discord's 2000 character limit! ({len(message_content)} characters)",
                    ephemeral=True
                )
                return

            # Send the message
            webhook = await self.bot.fetch_webhook(webhook_id)
            await webhook.send(content=message_content)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} File contents sent successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
                ephemeral=True
            )


    # Send a message through a webhook from a file using webhook URL
    @webhook_send_url_group.command(
        name="file",
        description="Send contents of a text file through a webhook URL"
    )
    @app_commands.describe(
        webhook_url="The URL of the webhook",
        file="The text file containing the message to send"
    )
    async def webhook_send_file(self, interaction: discord.Interaction, webhook_url: str, file: discord.Attachment) -> None:
        """Send the contents of a text file through the specified webhook"""
        if not file.filename.endswith('.txt'):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Only .txt files are supported!",
                ephemeral=True
            )
            return

        try:
            # Download and read the file content
            file_content = await file.read()
            message_content = file_content.decode('utf-8')

            # Check if content exceeds Discord's character limit
            if len(message_content) > 2000:
                await interaction.response.send_message(
                    f"{ERROR_EMOJI} File content exceeds Discord's 2000 character limit! ({len(message_content)} characters)",
                    ephemeral=True
                )
                return

            # Send the message
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                await webhook.send(content=message_content)

            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} File contents sent successfully!",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Invalid webhook URL!",
                ephemeral=True
            )
        except UnicodeDecodeError:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The file must contain valid text content!",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Failed to send message: `{str(e).capitalize()}`",
                ephemeral=True
            )

    # Change the name of a webhook
    @webhook_edit_group.command(
        name="name",
        description="Edit the name of a webhook"
    )
    @app_commands.describe(
        webhook_id="The ID of the webhook",
        name="The new name of the webhook"
    )
    async def webhook_edit_name(self, interaction: discord.Interaction, webhook_id: str, name: str) -> None:
        """Edit the name of a webhook"""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            await webhook.edit(name=name)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Webhook name updated successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Invalid webhook URL!",
                ephemeral=True
            )

    # Change the avatar of a webhook
    @webhook_edit_group.command(
        name="avatar",
        description="Edit the avatar of a webhook"
    )
    @app_commands.describe(
        webhook_id="The ID of the webhook",
        avatar="The new avatar of the webhook"
    )
    async def webhook_edit_avatar(self, interaction: discord.Interaction, webhook_id: str, avatar: discord.Attachment) -> None:
        """Edit the avatar of a webhook"""
        if not avatar.filename.endswith(('.png', '.jpg', '.jpeg', '.gif')):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Only .png, .jpg, .jpeg, and .gif files are supported!",
                ephemeral=True
            )
            return
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            await webhook.edit(avatar=await avatar.read())
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Webhook avatar updated successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Invalid webhook URL!",
                ephemeral=True
            )


    # Change the channel of a webhook
    @webhook_edit_group.command(
        name="channel",
        description="Edit the channel of a webhook"
    )
    @app_commands.describe(
        webhook_id="The ID of the webhook",
        channel="The new channel of the webhook"
    )
    async def webhook_edit_channel(
        self, interaction: discord.Interaction, webhook_id: str,
        channel: Union[discord.TextChannel, discord.ForumChannel, discord.StageChannel, discord.VoiceChannel]
    ) -> None:
        """Edit the channel of a webhook"""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            await webhook.edit(channel=channel)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Webhook channel updated successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Invalid webhook URL!",
                ephemeral=True
            )



async def setup(bot):
    await bot.add_cog(Webhook(bot))