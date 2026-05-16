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
    "categories": ["Bug", "Soporte", "Sugerencia"],
    "priorities": ["Baja", "Media", "Alta", "Crítica"],
    "staff_role_name": "Staff",
    "data_file": "data/tickets.json",
}

EMBED_CONFIG = {
    "colors": {
        "rojo": 0xFF0000,
        "azul": 0x0000FF,
        "verde": 0x00FF00,
        "amarillo": 0xFFFF00,
        "morado": 0x800080,
        "naranja": 0xFFA500,
        "negro": 0x000000,
        "blanco": 0xFFFFFF,
    },
    "limits": {
        "title": 256,
        "description": 4096,
        "field_name": 256,
        "field_value": 1024,
        "max_fields": 25,
        "total_embed": 6000,
    },
    "timeout_seconds": 1800,
}