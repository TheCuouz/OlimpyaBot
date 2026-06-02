import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Rol que se asigna automáticamente al entrar un nuevo miembro (autorol).
# Configurable por entorno; por defecto el rol "Trader" del servidor de JBT.
AUTOROLE_ID = int(os.getenv("AUTOROLE_ID", "1313934184150208562") or 0)

# Canal donde Olimpya da la bienvenida a cada nuevo miembro.
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "1313954374799720489") or 0)
# Canales enlazados en la bienvenida (comienza-aquí, chat general y presentaciones).
COMIENZA_AQUI_CHANNEL_ID = int(os.getenv("COMIENZA_AQUI_CHANNEL_ID", "1313986734278574143") or 0)
CHAT_CHANNEL_ID = int(os.getenv("CHAT_CHANNEL_ID", "1505322138427592755") or 0)
PRESENTACIONES_CHANNEL_ID = int(os.getenv("PRESENTACIONES_CHANNEL_ID", "1511123962027970570") or 0)

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN no está configurado en el archivo .env")

INTENTS = {
    "MESSAGE_CONTENT": True,
    "GUILD_MESSAGES": True,
    "DIRECT_MESSAGES": True,
}

# Carpeta persistente. En Railway se monta un volumen y se define DATA_DIR=/data;
# en local cae a ./data. Así los tickets sobreviven a cada redeploy.
DATA_DIR = os.getenv("DATA_DIR", "data")

TICKET_CONFIG = {
    "enabled": True,
    "categories": ["Bug", "Soporte", "Sugerencia"],
    "priorities": ["Baja", "Media", "Alta", "Crítica"],
    # Rol del equipo que ve y gestiona los tickets. Se busca primero por ID
    # (fiable aunque renombren el rol); el nombre queda solo como respaldo.
    "staff_role_id": int(os.getenv("STAFF_ROLE_ID", "1471424172138692674") or 0),
    "staff_role_name": "Staff",
    "data_file": os.path.join(DATA_DIR, "tickets.json"),
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