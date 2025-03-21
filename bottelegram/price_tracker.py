from typing import List, Dict
import logging
from datetime import datetime
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from math import ceil
from telegram import Bot

from database import db
from keepa_client import keepa_client
from chart_generator import chart_generator
from config import CHECK_INTERVAL, KEEPA_TOKENS_PER_MINUTE, KEEPA_BATCH_SIZE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceTracker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = BackgroundScheduler()
        self.setup_scheduler()

    def setup_scheduler(self):
        """Configura lo scheduler per il controllo periodico dei prezzi"""
        self.scheduler.add_job(
            self.check_all_products,
            trigger=IntervalTrigger(seconds=CHECK_INTERVAL),
            id='price_check',
            name='Controllo prezzi periodico',
            replace_existing=True
        )

    def start(self):
        """Avvia lo scheduler"""
        self.scheduler.start()
        logger.info("Price tracker avviato")

    def stop(self):
        """Ferma lo scheduler"""
        self.scheduler.shutdown()
        logger.info("Price tracker fermato")

    async def check_all_products(self):
        """Controlla i prezzi di tutti i prodotti attivi in batch"""
        try:
            # Recupera tutti i prodotti attivi
            products = db.get_all_active_products()
            if not products:
                return

            # Calcola il numero di batch necessari
            total_batches = ceil(len(products) / KEEPA_BATCH_SIZE)
            seconds_per_request = 60 / KEEPA_TOKENS_PER_MINUTE
            
            logger.info(f"Avvio controllo prezzi: {len(products)} prodotti in {total_batches} batch")
            logger.info(f"Rate limit: {KEEPA_TOKENS_PER_MINUTE} token/min ({seconds_per_request:.1f} sec per richiesta)")

            for i in range(0, len(products), KEEPA_BATCH_SIZE):
                # Prendi il batch corrente
                batch = products[i:i + KEEPA_BATCH_SIZE]
                current_batch = i//KEEPA_BATCH_SIZE + 1
                logger.info(f"Batch {current_batch}/{total_batches}: controllo {len(batch)} prodotti")

                # Controlla i prezzi per questo batch
                price_drops = keepa_client.check_price_drops(batch)

                # Invia notifiche per i price drops trovati
                for product in price_drops:
                    await self.send_price_drop_notification(product)

                # Attendi il tempo necessario prima del prossimo batch per rispettare il rate limit
                if i + KEEPA_BATCH_SIZE < len(products):
                    wait_time = seconds_per_request
                    logger.info(f"Attendo {wait_time:.1f} secondi prima del prossimo batch...")
                    await asyncio.sleep(wait_time)

            logger.info(f"Completato il controllo di tutti i {len(products)} prodotti in {total_batches} batch")
                
        except Exception as e:
            logger.error(f"Errore durante il controllo dei prezzi: {str(e)}")

    async def send_price_drop_notification(self, product: Dict):
        """
        Invia una notifica quando il prezzo di un prodotto scende sotto il target.
        
        Args:
            product: Dizionario contenente le informazioni del prodotto
        """
        try:
            # Genera il grafico dei prezzi
            chart = chart_generator.generate_price_chart(
                product['price_history'],
                product['target_price'],
                product['title']
            )

            # Prepara il messaggio
            message = self._format_price_drop_message(product)

            # Invia la notifica con il grafico
            await self.bot.send_photo(
                chat_id=product['user_id'],
                photo=chart,
                caption=message,
                parse_mode='HTML'
            )

            # Aggiorna la data dell'ultima notifica
            db.update_last_notification(product['user_id'], product['asin'])
            
            logger.info(f"Notifica inviata per il prodotto {product['asin']}")

        except Exception as e:
            logger.error(f"Errore nell'invio della notifica: {str(e)}")

    def _format_price_drop_message(self, product: Dict) -> str:
        """
        Formatta il messaggio di notifica per un price drop.
        
        Args:
            product: Dizionario contenente le informazioni del prodotto
            
        Returns:
            str: Messaggio formattato in HTML
        """
        return f"""
🎯 <b>Prezzo Target Raggiunto!</b>

📦 <b>Prodotto:</b> {product['title']}

💰 <b>Prezzo Attuale:</b> €{product['current_price']:.2f}
🎯 <b>Prezzo Target:</b> €{product['target_price']:.2f}
📉 <b>Prezzo Minimo Storico:</b> €{product['min_historic_price']:.2f}

🔗 <a href="{product['url']}">Vedi su Amazon</a>

📊 Grafico dell'andamento prezzi degli ultimi 7 giorni sopra.

Come affiliato Amazon, guadagno un compenso per ogni acquisto idoneo.
"""

    async def update_product_info(self, user_id: int, asin: str) -> Dict:
        """
        Aggiorna le informazioni di un prodotto.
        
        Args:
            user_id: ID dell'utente Telegram
            asin: ASIN del prodotto
            
        Returns:
            Dict: Informazioni aggiornate del prodotto
        """
        try:
            product = db.get_product(user_id, asin)
            if not product:
                return None

            # Recupera le informazioni aggiornate da Keepa
            info = keepa_client.get_product_info(product['url'])
            if not info:
                return None

            # Aggiorna il prezzo nel database
            if info['current_price']:
                db.update_product_price(user_id, asin, info['current_price'])

            # Aggiorna il prodotto con le nuove informazioni
            product.update(info)
            
            return product

        except Exception as e:
            logger.error(f"Errore nell'aggiornamento del prodotto: {str(e)}")
            return None