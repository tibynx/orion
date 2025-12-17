import os
from dotenv import load_dotenv

load_dotenv()


TOKEN = os.getenv('BOT_TOKEN')
SUCCESS_EMOJI = os.getenv('SUCCESS_EMOJI', '✅')
ERROR_EMOJI = os.getenv('ERROR_EMOJI', '❌')