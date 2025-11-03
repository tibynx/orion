import os
from dotenv import load_dotenv

load_dotenv()


TOKEN = os.getenv('BOT_TOKEN')
EMBED_COLOR = 0xB4BEFE

SUCCESS_EMOJI = ":white_check_mark:"
ERROR_EMOJI = ":x:"
INFO_EMOJI = ":information_source:"