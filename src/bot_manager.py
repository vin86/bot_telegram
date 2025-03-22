"""
Gestore principale del bot che coordina tutte le operazioni.
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
import signal
import sys

from config.config import Config
from .database import Database
from .keepa_client import KeepaClient
from .message_formatter import MessageFormatter
from .telegram_sender import TelegramSender

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BotManager:
    def __init__(self):
        self.db = Database()
        self.telegram = TelegramSender()
        self.formatter = MessageFormatter()
        self.running = False
        self.setup_signal_handlers()

    def setup_signal_handlers(self):
        """Configura i gestori dei segnali per uno shutdown pulito"""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._shutdown_handler)

    def _shutdown_handler(self, signum, frame):
        """Gestisce lo shutdown pulito del bot"""
        logger.info("Ricevuto segnale di shutdown...")
        self.running = False

    async def add_keyword(self, keyword: str) -> bool:
        """
        Aggiunge una nuova keyword da monitorare.
        
        Args:
            keyword: Parola chiave da aggiungere
            
        Returns:
            bool: True se l'operazione è riuscita
        """
        try:
            self.db.add_keyword(keyword)
            logger.info(f"Aggiunta nuova keyword: {keyword}")
            return True
        except Exception as e:
            logger.error(f"Errore nell'aggiunta della keyword: {str(e)}")
            return False

    async def check_product(self, product_data: Dict[str, Any], keyword_id: int) -> bool:
        """
        Controlla un singolo prodotto e invia una notifica se è in offerta.
        
        Args:
            product_data: Dati del prodotto da Keepa
            keyword_id: ID della keyword associata
            
        Returns:
            bool: True se il prodotto è stato processato con successo
        """
        try:
            current_price = product_data['current_price']
            highest_price = product_data['highest_price_30d']
            
            # Calcola lo sconto
            discount = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
            
            # Se lo sconto supera la soglia minima
            if discount >= Config.MINIMUM_DISCOUNT_PERCENT:
                # Aggiorna il prodotto nel database
                self.db.update_product(
                    asin=product_data['asin'],
                    title=product_data['title'],
                    current_price=current_price,
                    lowest_price_30d=product_data['lowest_price_30d'],
                    highest_price_30d=highest_price,
                    keyword_id=keyword_id
                )
                
                # Formatta e invia il messaggio
                message = self.formatter.format_deal_message(product_data, discount)
                if await self.telegram.send_message(message):
                    logger.info(f"Notifica inviata per il prodotto: {product_data['asin']}")
                    return True
                
            return False
        except Exception as e:
            logger.error(f"Errore nel controllo del prodotto {product_data.get('asin')}: {str(e)}")
            return False

    async def monitor_keywords(self):
        """Monitora le keywords attive e cerca nuove offerte"""
        async with KeepaClient() as keepa:
            keywords = self.db.get_active_keywords()
            
            for keyword in keywords:
                try:
                    # Cerca prodotti per la keyword
                    products = await keepa.search_products(keyword.keyword)
                    
                    for product in products:
                        # Ottieni dettagli completi del prodotto
                        details = await keepa.get_product_details(product['asin'])
                        if details:
                            await self.check_product(details, keyword.id)
                            
                    # Aggiorna il timestamp dell'ultimo controllo
                    keyword.last_check = datetime.utcnow()
                    
                except Exception as e:
                    logger.error(f"Errore nel monitoraggio della keyword {keyword.keyword}: {str(e)}")
                    continue
                
                # Piccola pausa tra le keyword per rispettare i rate limit
                await asyncio.sleep(2)

    async def run(self):
        """Avvia il ciclo principale del bot"""
        logger.info("Avvio del bot Amazon Deals...")
        
        # Verifica la configurazione
        if not Config.validate_config():
            logger.error("Configurazione non valida. Il bot non può partire.")
            return

        # Test della connessione Telegram
        if not await self.telegram.test_connection():
            logger.error("Test connessione Telegram fallito. Il bot non può partire.")
            return

        self.running = True
        last_cleanup = datetime.now()

        while self.running:
            try:
                await self.monitor_keywords()
                
                # Pulizia periodica del database (ogni 24 ore)
                if (datetime.now() - last_cleanup).days >= 1:
                    self.db.cleanup_old_history()
                    last_cleanup = datetime.now()
                
                # Attendi prima del prossimo ciclo
                await asyncio.sleep(Config.CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Errore nel ciclo principale: {str(e)}")
                await self.telegram.send_error_notification(str(e))
                await asyncio.sleep(60)  # Attendi un minuto prima di riprovare

        logger.info("Bot terminato.")

    def start(self):
        """Avvia il bot in modo asincrono"""
        asyncio.run(self.run())

    def stop(self):
        """Ferma il bot"""
        self.running = False
        logger.info("Arresto del bot in corso...")