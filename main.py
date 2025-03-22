"""
Punto di ingresso principale del bot Amazon Deals.
"""
import asyncio
import argparse
import sys
import logging
from typing import List

from src.bot_manager import BotManager
from config.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def add_keywords(keywords: List[str]):
    """Aggiunge nuove keywords da monitorare"""
    bot = BotManager()
    for keyword in keywords:
        if await bot.add_keyword(keyword):
            print(f"Keyword aggiunta con successo: {keyword}")
        else:
            print(f"Errore nell'aggiunta della keyword: {keyword}")

def main():
    parser = argparse.ArgumentParser(description="Amazon Deals Bot - Monitoraggio offerte")
    
    parser.add_argument(
        "--add-keywords",
        nargs="+",
        help="Aggiungi una o più keywords da monitorare (es. --add-keywords 'smartphone' 'laptop')"
    )
    
    args = parser.parse_args()

    # Verifica la configurazione
    if not Config.validate_config():
        logger.error("Configurazione non valida. Verifica il file .env")
        sys.exit(1)

    # Se sono state specificate keywords, aggiungile e termina
    if args.add_keywords:
        asyncio.run(add_keywords(args.add_keywords))
        sys.exit(0)

    # Altrimenti avvia il bot normalmente
    try:
        bot = BotManager()
        print("Bot Amazon Deals avviato. Premi CTRL+C per terminare.")
        bot.start()
    except KeyboardInterrupt:
        print("\nArresto del bot in corso...")
    except Exception as e:
        logger.error(f"Errore critico: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()