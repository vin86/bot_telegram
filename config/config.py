import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Configurazione Bot Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_GROUP_ID = os.getenv('TELEGRAM_GROUP_ID')

# Configurazione Keepa
KEEPA_API_KEY = os.getenv('KEEPA_API_KEY')

# Configurazione Database
DATABASE_URL = 'sqlite:///keepabot.db'

# Configurazione Monitoraggio
CHECK_INTERVAL = 60  # Intervallo di controllo in secondi
MAX_REQUESTS_PER_MINUTE = 60  # Limite richieste Keepa
PRICE_HISTORY_DAYS = 30  # Giorni di storico prezzi da visualizzare

# Configurazione Cache
CACHE_DURATION = 300  # Durata della cache in secondi

# Configurazione Logger
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = 'keepabot.log'