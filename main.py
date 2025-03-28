import logging
import threading
from telegram.ext import ApplicationBuilder, Application
from config.config import TELEGRAM_TOKEN, LOG_LEVEL, LOG_FORMAT, LOG_FILE, DATABASE_URL

from src.services.monitor_service import MonitorService
from src.services.notification_service import NotificationService
from src.services.keepa_service import KeepaService
from src.bot.handlers.commands import CommandHandlers
from src.database.models import init_db

# Configurazione logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def init_services():
    """Inizializza e verifica i servizi"""
    try:
        # Inizializza il database
        logger.info("Inizializzazione database...")
        engine = init_db(DATABASE_URL)
        
        # Verifica la connessione a Keepa
        logger.info("Verifica connessione Keepa API...")
        keepa_service = KeepaService()
        
        # Inizializza i servizi
        logger.info("Inizializzazione servizi...")
        notification_service = NotificationService()
        monitor_service = MonitorService(notification_service, keepa_service)
        
        return notification_service, monitor_service, keepa_service
        
    except Exception as e:
        logger.error(f"Errore durante l'inizializzazione dei servizi: {str(e)}")
        raise

def run_monitoring(monitor_service):
    """Esegue il monitoraggio in un thread separato"""
    try:
        monitor_service.start_monitoring()
    except Exception as e:
        logger.error(f"Errore nel thread di monitoraggio: {str(e)}")

def main():
    """Funzione principale per l'avvio del bot"""
    try:
        # Inizializza i servizi
        notification_service, monitor_service, keepa_service = init_services()
        
        # Inizializza il bot
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Registra gli handlers
        command_handlers = CommandHandlers(monitor_service, notification_service)
        for handler in command_handlers.get_handlers():
            application.add_handler(handler)
        
        # Avvia il monitoraggio in un thread separato
        logger.info("Avvio monitoraggio prezzi...")
        monitoring_thread = threading.Thread(
            target=run_monitoring,
            args=(monitor_service,),
            daemon=True
        )
        monitoring_thread.start()
        # Avvia il bot e invia il messaggio iniziale
        logger.info("Bot avviato e in ascolto...")
        products = monitor_service.get_monitored_products()
        notification_service.send_status(products)
        
        # Avvia il polling
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Errore durante l'esecuzione del bot: {str(e)}")
        raise
    finally:
        # Arresta il monitoraggio
        if monitor_service:
            monitor_service.stop_monitoring()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interruzione da tastiera rilevata")
    except Exception as e:
        logger.error(f"Errore fatale: {str(e)}")
