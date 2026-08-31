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


def _parse_max_reaction_emojis() -> int:
    """Parse MAX_REACTION_EMOJIS from env, clamping to [1, 25] with safe fallback."""
    try:
        val = int(os.getenv('MAX_REACTION_EMOJIS', '25'))
        return max(1, min(val, 25))
    except ValueError:
        return 25


MAX_REACTION_EMOJIS = _parse_max_reaction_emojis()
