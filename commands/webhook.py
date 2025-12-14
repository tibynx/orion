from typing import Union

import discord
from discord.ext import commands
from discord import app_commands

from config import EMBED_COLOR, INFO_EMOJI, SUCCESS_EMOJI, ERROR_EMOJI


# TODO: Fix grammar
# TODO: Align code better
# TODO: Do pylint, and fix code


# Modal for sending messages via webhook ID
class WebhookSendModal(discord.ui.Modal, title="Send Message via Webhook"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    webhook_id = discord.ui.TextInput(
        label="Webhook ID",
        placeholder="Enter the webhook ID",
        required=True,
        max_length=20,
    )
    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send",
        required=True,
        max_length=2000,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            webhook = await self.bot.fetch_webhook(self.webhook_id.value)
            if isinstance(webhook.channel, discord.ForumChannel):
                await interaction.response.send_message(
                    f"{ERROR_EMOJI} You cannot send messages to forum webhooks!",
                    ephemeral=True
                )
                return
            await webhook.send(content=self.message.value)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Message sent successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Failed to send message: `{str(e).capitalize()}`",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message(
            f"{ERROR_EMOJI} An error occurred while sending the message: `{str(error).capitalize()}`",
            ephemeral=True
        )


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
        description="Delete a webhook"
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


    # Send a message through a webhook using its ID (opens modal)
    @app_commands.command(
        name="webhookmsg",
        description="Send a message through a webhook"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    async def webhook_send_id(self, interaction: discord.Interaction) -> None:
        """Open a modal to send a message through a webhook ID"""
        await interaction.response.send_modal(WebhookSendModal(self.bot))

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