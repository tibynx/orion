# ✨ Orion

Orion is a Discord server management and utility bot that provides various administrative and convenience features for Discord server owners and moderators.

## Features

* Message and thread management
* Manage webhooks
* Send messages as the bot or using a webhook
* Play audio files in voice channels
* Customize bot presence and activity
* Restrict commands using Discord's permission system

## Setup

Create an application on the [Discord Developer Portal](https://discord.com/developers/applications), and copy the application ID and the bot token for later.

> [!NOTE]
> This bot intended to be used in only one server at a time. If you want to use it in multiple servers, you will need to create another bot with different bot tokens.

### Docker

If you prefer, you can set up the bot using Docker.

```sh
docker run -d \
  --name=orion \
  -e BOT_TOKEN=your_bot_token_here \
  -e SUCCESS_EMOJI=✅ `#optional` \
  -e ERROR_EMOJI=❌ `#optional` \
  tibynx/orion:latest
```


### Source

Clone the repo and install all required packages! Make sure you have at least Python 3.14 installed!

```sh
git clone https://github.com/tibynx/orion.git
cd orion
pip install -r requirements.txt
```

In the meantime, create an `.env` file according to the `.env.example` file! Do not share your bot token with anyone!

```sh
BOT_TOKEN="your_bot_token_here"
SUCCESS_EMOJI="✅" #optional
ERROR_EMOJI="❌" #optional
```

Then, you can run the bot using the `python main.py` command!

## Usage

After setting up, invite your bot to a server using this premade link! It already contains the proper permissions. Replace `<app-id>` with your bot's appication  ID.

```sh
https://discord.com/oauth2/authorize?client_id=<app-id>&permissions=120796048384&integration_type=0&scope=bot+applications.commands
```
