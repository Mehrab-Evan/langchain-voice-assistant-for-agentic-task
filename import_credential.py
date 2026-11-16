from dotenv import load_dotenv
import os, json

# Fetch environment variables
load_dotenv()
groq_api_key = os.getenv("GROQ_API")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
EM7_GID = os.getenv("EM7_GID")
TELEGRAM_BOT_TOKEN = os.getenv("DIAMOND_KEBAB")
TEACHERS_OPINION_GID = os.getenv("TEACHERS_OPINION_GID")