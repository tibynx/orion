"""Configuration settings for the Discord bot."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
SUCCESS_EMOJI = os.getenv('SUCCESS_EMOJI', '✅')
ERROR_EMOJI = os.getenv('ERROR_EMOJI', '❌')
