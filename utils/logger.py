import logging
import os
from datetime import datetime

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

log_filename = os.path.join(
    LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

logger = logging.getLogger("OlimpyaBot")
logger.setLevel(logging.DEBUG)

# Solo file handler — evita problemas de encoding en consola Windows
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
