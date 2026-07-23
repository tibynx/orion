"""Configuration settings for the Discord bot."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
SUCCESS_EMOJI = os.getenv('SUCCESS_EMOJI', '✅')
ERROR_EMOJI = os.getenv('ERROR_EMOJI', '❌')
PREVIOUS_EMOJI = os.getenv('PREVIOUS_EMOJI', '◀️')
NEXT_EMOJI = os.getenv('NEXT_EMOJI', '▶️')
EXCLUDED_EMOJIS = [
    e.strip() for e in os.getenv('EXCLUDED_EMOJIS', '').split(',') if e.strip()
]
MAX_REACTION_EMOJIS = min(int(os.getenv('MAX_REACTION_EMOJIS', '25')), 25)
