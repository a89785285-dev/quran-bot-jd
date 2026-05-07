import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8620574210:AAH4cpVvF8k5MlO9Nz5qmrUmbDOmImWMoak')
API_URL = 'https://api.alquran.cloud/v1'

# Default settings
DEFAULT_INTERVAL = 5  # minutes
MIN_INTERVAL = 1      # minutes
MAX_INTERVALS = 1440  # minutes (24 hours)

# Logging
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
