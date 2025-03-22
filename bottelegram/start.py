import multiprocessing
import sys
import logging
import signal
import asyncio
from main import main as bot_main
from admin_dashboard import app as admin_app

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

def run_bot():
    """Avvia il bot Telegram"""
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

def run_admin():
    """Avvia il pannello amministrativo"""
    try:
        logger.info("Avvio pannello amministrativo...")
        admin_app.run(host='0.0.0.0', port=6689)
    except Exception as e:
        logger.error(f"Errore nell'avvio del pannello admin: {str(e)}")
        sys.exit(1)

def cleanup(bot_process, admin_process):
    """Pulisce e termina i processi"""
    logger.info("Arresto dei servizi...")
    bot_process.terminate()
    admin_process.terminate()
    bot_process.join()
    admin_process.join()
    logger.info("Servizi arrestati con successo")

if __name__ == '__main__':
    # Installa il gestore dei segnali nel processo principale
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Crea i processi
        bot_process = multiprocessing.Process(target=run_bot)
        admin_process = multiprocessing.Process(target=run_admin)

        # Avvia i processi
        logger.info("Avvio dei servizi...")
        bot_process.start()
        admin_process.start()

        # Attendi che i processi terminino
        bot_process.join()
        admin_process.join()

    except KeyboardInterrupt:
        cleanup(bot_process, admin_process)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Errore nell'avvio dei servizi: {str(e)}")
        cleanup(bot_process, admin_process)
        sys.exit(1)