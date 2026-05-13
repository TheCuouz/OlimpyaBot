import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN no está configurado en el archivo .env")

INTENTS = {
    "MESSAGE_CONTENT": True,
    "GUILD_MESSAGES": True,
    "DIRECT_MESSAGES": True,
}

RESPONSES = {
    "desidia": "Que pasa perro?",
}


TICKET_CONFIG = {
    "enabled": True,
    "categories": ["Bug", "Support", "Feature Request"],
    "priorities": ["Low", "Medium", "High", "Critical"],
    "staff_role_name": "Staff",
    "data_file": "data/tickets.json",
}