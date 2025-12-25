# ✨ Orion

Orion is a Discord server management and utility bot that provides various administrative and convenience features for Discord server owners and moderators.

## Features

* Message and thread management
* Manage webhooks
* Send messages as the bot or using a webhook
* Customize bot presence and activity
* Restrict commands using Discord's permission system

## Setup

Create an application on the [Discord Developer Portal](https://discord.com/developers/applications), and copy the application ID and the bot token for later.

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
BOT_TOKEN=your_bot_token_here
```

Then, you can run the bot using the `python main.py` command!
