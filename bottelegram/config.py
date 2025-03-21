from dotenv import load_dotenv
import os

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Configurazione Bot Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Configurazione Keepa
KEEPA_API_KEY = os.getenv('KEEPA_API_KEY')

# Configurazione MongoDB
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'amazon_price_tracker'
PRODUCTS_COLLECTION = 'products'
USERS_COLLECTION = 'users'

# Configurazione Price Tracker
CHECK_INTERVAL = 300  # Controlla i prezzi ogni 5 minuti
KEEPA_TOKENS_PER_MINUTE = 20  # Limite token Keepa per minuto
KEEPA_BATCH_SIZE = 20  # Numero di prodotti per batch

# Configurazione Admin Dashboard
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'changeme')  # Cambiare in produzione!
MAX_PRODUCTS_PER_USER = 5
PRICE_HISTORY_DAYS = 30

# Configurazione Grafici
CHART_WIDTH = 800
CHART_HEIGHT = 400
CHART_DPI = 100

# Messaggi del Bot
WELCOME_MESSAGE = """
Benvenuto nel Bot di Monitoraggio Prezzi Amazon! 🛒

Come affiliato Amazon, guadagno un compenso per ogni acquisto idoneo.

Comandi disponibili:
/add - Aggiungi un nuovo prodotto da monitorare
/list - Visualizza i tuoi prodotti monitorati
/help - Mostra questo messaggio di aiuto
"""

HELP_MESSAGE = """
📝 Comandi Disponibili:

/start - Inizia a utilizzare il bot
/add - Aggiungi un nuovo prodotto da monitorare
/list - Visualizza la lista dei prodotti monitorati
/help - Mostra questo messaggio di aiuto

Per aggiungere un prodotto:
1. Invia il comando /add
2. Incolla il link del prodotto Amazon
3. Inserisci il prezzo target

Ti avviserò quando il prezzo scenderà sotto il target! 🎯
"""

# Regex pattern per validare i link Amazon
# ID Affiliazione Amazon
AMAZON_AFFILIATE_ID = "bot047-21"

# Regex pattern per validare i link Amazon
AMAZON_URL_PATTERN = r'https?://(?:www\.)?amazon\.[a-z.]{2,6}/(?:[^"\'/]*/?){0,8}(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)'