import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN", "")
GUILD_ID = os.getenv("GUILD_ID", "")
OWNER_1_ID = os.getenv("OWNER_1_ID", "OWNER_1_ID")
OWNER_2_ID = os.getenv("OWNER_2_ID", "OWNER_2_ID")
TRANSFER_CHANNEL_ID = os.getenv("TRANSFER_CHANNEL_ID", "")
