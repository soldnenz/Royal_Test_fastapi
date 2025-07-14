import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
COLLECTION_NAME = "question_reports"

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_WARNING_TOPIC = os.getenv("TELEGRAM_WARNING_TOPIC")

# Bot Configuration
POLLING_INTERVAL = 60  # seconds (1 minute) 