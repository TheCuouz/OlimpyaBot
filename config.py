import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Server: TTS Dev SL. Every id can be overridden from the environment.
GUILD_ID = int(os.getenv("GUILD_ID", "1506806457813827684") or 0)

# Per-member welcome and autorole are off: Discord's own onboarding picks the
# language and the Member role. Set the ids to turn them back on.
AUTOROLE_ID = int(os.getenv("AUTOROLE_ID", "0") or 0)
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0") or 0)
COMIENZA_AQUI_CHANNEL_ID = int(os.getenv("COMIENZA_AQUI_CHANNEL_ID", "0") or 0)
CHAT_CHANNEL_ID = int(os.getenv("CHAT_CHANNEL_ID", "0") or 0)
PRESENTACIONES_CHANNEL_ID = int(os.getenv("PRESENTACIONES_CHANNEL_ID", "0") or 0)

# Staff-only channel where joins, leaves and role grants are written down.
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "1548429770889371778") or 0)

# Licence check of the TTS Studio store (studio.journalbytts.xyz).
LICENSE_API = os.getenv("LICENSE_API", "https://studio.journalbytts.xyz/api/v1/licenses")

# Paid products: Discord role name -> store slug.
PRODUCTS = {
    "DominionForge": "dominionforge",
    "TTSCore": "ttscore",
    "SkillsRPG": "skillsrpg",
    "QuestForge": "questforge",
    "EnchantsForge V2": "efv2addon",
    "ShopForge": "shopforge",
    "TradeForge": "tradeforge",
    "ItemForge": "itemforge",
    "AtlasForge": "atlasforge",
}
# Free plugins, for /vouch.
FREE_PRODUCTS = [
    "AfkGuard", "BetterDeathMessages", "ChattyChannels", "ClaimsForge", "CombatLogger",
    "CraftBlockForge", "CrateForge", "EnchantsForge", "HudForge", "ParticleForge",
    "SafeRTP", "SmartHomes",
]
VOUCH_CHANNEL_ID = int(os.getenv("VOUCH_CHANNEL_ID", "1548429713322676324") or 0)
PRODUCT_ROLE_PREFIX = "[ ♣ ] "
CUSTOMER_ROLE = "[ ♦ ] Customer"
# Group dividers that make a customer's profile show the Client Roles / Products blocks.
CUSTOMER_DIVIDERS = ("Client Roles", "Products")

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
    "categories": ["Bug", "Help", "Licence"],
    "priorities": ["Low", "Normal", "High", "Urgent"],
    # Rol del equipo que ve y gestiona los tickets. Se busca primero por ID
    # (fiable aunque renombren el rol); el nombre queda solo como respaldo.
    "staff_role_id": int(os.getenv("STAFF_ROLE_ID", "1548429550030028856") or 0),
    "staff_role_name": "[ ✦ ] Staff",
    "data_file": os.path.join(DATA_DIR, "tickets.json"),
}

CLAIMED_KEYS_FILE = os.path.join(DATA_DIR, "claimed_keys.json")
VOUCHES_FILE = os.path.join(DATA_DIR, "vouches.json")

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