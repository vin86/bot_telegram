import os
import logging
import asyncio
from telegram.ext import Application

from src.bot.handlers.commands import CommandHandlers
from src.services.monitor_service import MonitorService
from src.services.notification_service import NotificationService
from src.database.models import init_db
from config.config import (
    TELEGRAM_TOKEN,
    DATABASE_URL,
    LOG_LEVEL,
    LOG_FORMAT,
    LOG_FILE
)

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

async def main():
    try:
        # Inizializza il database
        logger.info("Inizializzazione database...")
        engine = init_db(DATABASE_URL)
        
        # Inizializza i servizi
        logger.info("Inizializzazione servizi...")
        notification_service = NotificationService()
        monitor_service = MonitorService(notification_service)
        
        # Inizializza il bot
        logger.info("Inizializzazione bot Telegram...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Registra gli handlers dei comandi
        command_handlers = CommandHandlers(monitor_service, notification_service)
        for handler in command_handlers.get_handlers():
            application.add_handler(handler)
            
        # Avvia il monitoraggio dei prezzi in background
        logger.info("Avvio monitoraggio prezzi...")
        asyncio.create_task(monitor_service.start_monitoring())
        
        # Avvia il bot
        logger.info("Bot avviato e in ascolto...")
        await application.run_polling()
        
    except Exception as e:
        logger.error(f"Errore durante l'avvio del bot: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot arrestato dall'utente")
    except Exception as e:
        logger.error(f"Errore fatale: {str(e)}")