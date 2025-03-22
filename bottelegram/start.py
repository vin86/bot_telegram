import sys
import logging
import signal
import asyncio
from main import main as bot_main

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Gestisce i segnali di interruzione"""
    logger.info(f"Ricevuto segnale di interruzione {signum}")
    sys.exit(0)

if __name__ == '__main__':
    try:
        logger.info("Avvio bot Telegram...")
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Installa il gestore dei segnali
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Avvia il bot
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        logger.info("Bot fermato manualmente")
    except Exception as e:
        logger.error(f"Errore nell'avvio del bot: {str(e)}")
        sys.exit(1)
