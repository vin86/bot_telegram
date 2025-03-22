import asyncio
import logging
from telegram.ext import Application
from dotenv import load_dotenv
import os

from config import TELEGRAM_TOKEN
from bot_handlers import get_handlers
from price_tracker import PriceTracker

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start_bot(application: Application):
    """Inizializza e avvia il bot"""
    # Aggiungi gli handler
    for handler in get_handlers():
        application.add_handler(handler)

    # Crea e avvia il price tracker
    price_tracker = PriceTracker(application.bot)
    application.bot_data['price_tracker'] = price_tracker
    price_tracker.start()

    # Inizializza e avvia il polling
    await application.initialize()
    await application.start()
    try:
        await application.run_polling(allowed_updates=["message", "callback_query"])
    except Exception:
        if 'price_tracker' in application.bot_data:
            application.bot_data['price_tracker'].stop()
        raise

async def main():
    """Funzione principale che avvia il bot"""
    # Verifica che le variabili d'ambiente necessarie siano presenti
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN non trovato nelle variabili d'ambiente")

    # Crea l'applicazione del bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    try:
        await start_bot(application)
    except Exception as e:
        logger.error(f"Errore durante l'esecuzione del bot: {str(e)}")
        raise
    finally:
        try:
            await application.shutdown()
        except Exception as e:
            logger.error(f"Errore durante l'arresto del bot: {str(e)}")

if __name__ == '__main__':
    # Carica le variabili d'ambiente
    load_dotenv()
    
    try:
        # Avvia il bot
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interruzione manuale rilevata")
    except Exception as e:
        logger.error(f"Errore durante l'avvio del bot: {str(e)}")
