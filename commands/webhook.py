from typing import Union
import discord
from discord.ext import commands
from discord import app_commands
from config import SUCCESS_EMOJI, ERROR_EMOJI


# TODO: Fix grammar
# TODO: Do pylint, and fix code
# TODO: Add optional attachments to the webhook message modal


# Modal for sending messages via webhook ID
class WebhookSendModal(discord.ui.Modal):
    def __init__(self, bot, webhook: discord.Webhook):
        super().__init__(title=f"Send Message via {webhook.name}")
        self.bot = bot
        self.webhook = webhook

    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder=f"Enter the message to send",
        required=True,
        max_length=2000,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.webhook.send(content=self.message.value)
        await interaction.response.send_message(
            f"{SUCCESS_EMOJI} Message sent successfully!",
            ephemeral=True
        )
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if isinstance(error, discord.NotFound):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} An error occurred while sending the message: `{str(error).capitalize()}`",
                ephemeral=True
            )


# Webhook deletion dialog
class WebookDeleteDialog(discord.ui.LayoutView):
    def __init__(self, webhook: discord.Webhook):
        super().__init__()
        self.webhook = webhook

        container = discord.ui.Container(discord.ui.TextDisplay(f"## Delete {webhook.name}\nAre you sure you want to delete **{webhook.name}** webhook? This action cannot be undone."))
        cancel_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Cancel") # Cancel button
        delete_button = discord.ui.Button(style=discord.ButtonStyle.danger, label="Delete") # Delete button
        cancel_button.callback = self.cancel_button_callback
        delete_button.callback = self.delete_button_callback
        buttons = discord.ui.ActionRow(cancel_button, delete_button) # Add buttons to the row
        container.add_item(buttons)
        self.add_item(container)

    # If we cancel, the message just gets removed
    async def cancel_button_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.delete_original_response()

    # If we delete, it deletes the message, then tries to delete the webhook
    async def delete_button_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            await self.webhook.delete()
            await interaction.delete_original_response()
            await interaction.followup.send(
                f"{SUCCESS_EMOJI} Deleted **{self.webhook.name}** webhook successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.delete_original_response()
            await interaction.followup.send(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.delete_original_response()
            await interaction.followup.send(
                f"{ERROR_EMOJI} I do not have permission to delete this webhook!",
                ephemeral=True
            )


# Webhook buttons
class WebhookButtons(discord.ui.View):
    def __init__(self, webhook: discord.Webhook):
        super().__init__()
        self.webhook = webhook

    # Send message button
    # Sends the webhook message modal
    @discord.ui.button(label="Send Message", style=discord.ButtonStyle.primary)
    async def send_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Prevent sending messages to forum channels
        if isinstance(self.webhook.channel, discord.ForumChannel):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} You cannot send messages to forum webhooks!",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(WebhookSendModal(interaction.client, self.webhook))

    # Show webhook URL button
    # Sends the webhook URL in an ephemeral message
    @discord.ui.button(label="Show Webhook URL", style=discord.ButtonStyle.secondary)
    async def show_url(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"{self.webhook.name}: `{self.webhook.url}`", ephemeral=True)

    # Delete webhook button
    # Sends the webhook deletion confirmation modal
    @discord.ui.button(label="Delete Webhook", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=WebookDeleteDialog(self.webhook), ephemeral=True)


# Separate delete button for channel follower and application webhooks
class WebhookDeleteButton(discord.ui.View):
    def __init__(self, webhook: discord.Webhook):
        super().__init__()
        self.webhook = webhook

    # Delete webhook button
    # Sends the webhook deletion confirmation modal
    @discord.ui.button(label="Delete Webhook", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=WebookDeleteDialog(self.webhook), ephemeral=True)



# Webhook commands
class Webhook(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Group for editing webhooks
    webhook_edit_group = app_commands.Group(
        name="webhookedit",
        description="Edit webhook details",
        default_permissions=discord.Permissions(manage_webhooks=True), # Requires manage webhooks permission
        guild_only=True
    )



    # Get details about a webhook
    @app_commands.command(
        name="webhookget",
        description="Get details about a webhook"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True) # Requires manage webhooks permission
    @app_commands.describe(
        webhook_id="The ID of the webhook to fetch"
    )
    async def webhook_get(self, interaction: discord.Interaction, webhook_id: str) -> None:
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            embed = discord.Embed(
                title=webhook.name,
                color=None,
                description=f"🕔 Created at <t:{int(webhook.created_at.timestamp())}:R> by {webhook.user.mention}"
            )
            embed.add_field(name="Channel", value=webhook.channel.mention, inline=True)
            embed.add_field(name="Type", value=webhook.type.name.title(), inline=True)
            embed.add_field(name="ID", value=f"`{webhook.id}`", inline=True)
            embed.set_thumbnail(url=webhook.display_avatar.url)
            # Check if the webhook user is a bot
            if webhook.user.bot:
                embed.set_footer(text=f"🛈  This webhook is managed by {webhook.user.name}#{webhook.user.discriminator}.")
            # Check if it's an application or channel follower webhook (we can only delete those)
            elif webhook.type == discord.WebhookType.channel_follower or discord.WebhookType.application:
                return await interaction.response.send_message(embed=embed, view=WebhookDeleteButton(webhook), ephemeral=True)
            return await interaction.response.send_message(embed=embed, view=WebhookButtons(webhook), ephemeral=True)
        except discord.NotFound:
            return await interaction.response.send_message(f"{ERROR_EMOJI} The specified webhook cannot be found!", ephemeral=True)


    # List all webhooks
    @app_commands.command(
        name="webhooklist",
        description="List all webhooks in the current server"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True) # Requires manage webhooks permission
    async def webhook_list(self, interaction: discord.Interaction) -> None:
        webhooks = await interaction.guild.webhooks()
        # Check if there are no webhooks
        if not webhooks:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} No webhooks found in this server!",
                ephemeral=True
            )
        embed = discord.Embed(title=f"Webhooks in {interaction.guild.name}", color=None)
        for webhook in webhooks:
            embed.add_field(
                name=webhook.name,
                value=f"Channel: {webhook.channel.mention}\nCreated by: {webhook.user.mention}\nID: `{webhook.id}`",
                inline=False
            )
        embed.set_footer(text="🛈  Use the /webhookget command to get details about a specific webhook.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)


    # Create a webhook
    @app_commands.command(
        name="webhookcreate",
        description="Create a webhook. The webhook will be associated with this bot!"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True) # Requires manage webhooks permission
    @app_commands.describe(
        channel="The channel to create the webhook in",
        name="The name of the webhook"
    )
    async def webhook_create(
        self, interaction: discord.Interaction,
        channel: Union[discord.TextChannel, discord.ForumChannel, discord.StageChannel, discord.VoiceChannel],
        name: str
    ) -> None:
        webhook = await channel.create_webhook(name=name)
        embed = discord.Embed(
            title=webhook.name,
            color=None,
            description=f"🕔 Created at <t:{int(webhook.created_at.timestamp())}:R> by {webhook.user.mention}"
        )
        embed.add_field(name="Channel", value=webhook.channel.mention, inline=True)
        embed.add_field(name="Type", value=webhook.type.name.title(), inline=True)
        embed.add_field(name="ID", value=f"`{webhook.id}`", inline=True)
        embed.set_thumbnail(url=webhook.display_avatar.url)
        # We don't check if the webhook user is a bot, because it always will be
        embed.set_footer(text=f"🛈  Use the /webhookedit commands to edit this webhook's details.")
        await interaction.response.send_message(f"{SUCCESS_EMOJI} Created **{webhook.name}** webhook!", embed=embed, view=WebhookButtons(webhook), ephemeral=True)


    # Delete a webhook (sends confirmation modal)
    @app_commands.command(
        name="webhookdelete",
        description="Delete a webhook"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        webhook_id="The ID of the webhook to delete"
    )
    async def webhook_delete(self, interaction: discord.Interaction, webhook_id: str) -> None:
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
                ephemeral=True
            )
            return
        await interaction.response.send_message(view=WebookDeleteDialog(webhook), ephemeral=True)


    # Send a message through a webhook using its ID (opens modal)
    @app_commands.command(
        name="webhookmsg",
        description="Send a message through a webhook"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        webhook_id="The ID of the webhook to send the message through"
    )
    async def webhook_send(self, interaction: discord.Interaction, webhook_id: str) -> None:
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
                ephemeral=True
            )
            return
        # Prevent sending messages to forum channels
        if isinstance(webhook.channel, discord.ForumChannel):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} You cannot send messages to forum webhooks!",
                ephemeral=True
            )
            return
        # Check if it's a channel follower or application webhook
        if webhook.type == discord.WebhookType.channel_follower or discord.WebhookType.application:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} You cannot send messages with this webhook!",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(WebhookSendModal(self.bot, webhook)) # Send the webhook message modal


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
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            # Check if it's a channel follower or application webhook
            if webhook.type == discord.WebhookType.channel_follower or discord.WebhookType.application:
                return await interaction.response.send_message(f"{ERROR_EMOJI} You cannot rename this webhook!", ephemeral=True)
            old_name = webhook.name
            await webhook.edit(name=name)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} **{old_name}** webhook's name has been changed to **{webhook.name}** successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
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
        if not avatar.filename.endswith(('.png', '.jpg', '.jpeg', '.gif')):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} Only .png, .jpg, .jpeg, and .gif files are supported!",
                ephemeral=True
            )
            return
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            # Check if it's a channel follower or application webhook
            if webhook.type == discord.WebhookType.channel_follower or discord.WebhookType.application:
                return await interaction.response.send_message(
                    f"{ERROR_EMOJI} You cannot change the avatar for this webhook!",
                    ephemeral=True
                )
            await webhook.edit(avatar=await avatar.read())
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} **{webhook.name}** webhook's avatar changed successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
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
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            # Check if it's a channel follower or application webhook
            if webhook.type == discord.WebhookType.channel_follower or discord.WebhookType.application:
                return await interaction.response.send_message(
                    f"{ERROR_EMOJI} You cannot change channel for this webhook!",
                    ephemeral=True
                )
            await webhook.edit(channel=channel)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} **{webhook.channel}** webhook's channel updated successfully!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found!",
                ephemeral=True
            )



async def setup(bot):
    await bot.add_cog(Webhook(bot))