import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file config.env
load_dotenv('config.env')

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
PRICE_HISTORY_RETENTION_DAYS = 90  # Giorni di mantenimento dati storici nel database
MIN_PRICE_CHANGE_PERCENT = 1.0  # Variazione minima percentuale per notifiche
BATCH_SIZE = 5  # Numero di prodotti da processare in batch

# Configurazione Notifiche
NOTIFICATION_BATCH_SIZE = 3  # Numero massimo di notifiche in batch
NOTIFICATION_COOLDOWN = 3600  # Tempo minimo tra notifiche per lo stesso prodotto (secondi)

# Configurazione Cache
CACHE_DURATION = 300  # Durata della cache in secondi

# Configurazione Logger
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = 'keepabot.log'

# Configurazione Backup
BACKUP_ENABLED = True
BACKUP_INTERVAL = 86400  # Intervallo di backup in secondi (24 ore)
BACKUP_RETENTION = 7  # Numero di backup da mantenere

# Configurazione Grafica
CHART_DPI = 150  # Qualità dei grafici generati
CHART_WIDTH = 10  # Larghezza dei grafici in pollici
CHART_HEIGHT = 6  # Altezza dei grafici in pollici