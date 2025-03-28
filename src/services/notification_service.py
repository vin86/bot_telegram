import logging
import io
import asyncio
from datetime import datetime, timedelta
from typing import List
import matplotlib.pyplot as plt
from telegram import Bot
from PIL import Image
import requests

from config.config import TELEGRAM_TOKEN, TELEGRAM_GROUP_ID, PRICE_HISTORY_DAYS
from src.database.models import Product, PriceHistory

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        """Inizializza il servizio di notifica"""
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.group_id = TELEGRAM_GROUP_ID

    def _generate_price_chart(self, product: Product) -> io.BytesIO:
        """
        Genera un grafico dello storico prezzi
        
        Args:
            product: Prodotto per cui generare il grafico
            
        Returns:
            Buffer contenente l'immagine del grafico
        """
        # Filtra lo storico prezzi per gli ultimi PRICE_HISTORY_DAYS giorni
        cutoff_date = datetime.utcnow() - timedelta(days=PRICE_HISTORY_DAYS)
        price_history = [ph for ph in product.price_history if ph.check_date >= cutoff_date]
        
        # Prepara i dati per il grafico
        dates = [ph.check_date for ph in price_history]
        prices = [ph.price for ph in price_history]
        
        # Crea il grafico
        plt.figure(figsize=(10, 6))
        plt.plot(dates, prices, 'b-', label='Prezzo')
        plt.axhline(y=product.target_price, color='r', linestyle='--', label='Prezzo Target')
        
        # Configura il grafico
        plt.title(f"Storico Prezzi - {product.keyword}")
        plt.xlabel("Data")
        plt.ylabel("Prezzo (€)")
        plt.grid(True)
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Salva il grafico in un buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        
        buf.seek(0)
        return buf

    def _download_product_image(self, image_url: str) -> io.BytesIO:
        """
        Scarica l'immagine del prodotto
        
        Args:
            image_url: URL dell'immagine da scaricare
            
        Returns:
            Buffer contenente l'immagine
        """
        try:
            response = requests.get(image_url)
            if response.status_code == 200:
                return io.BytesIO(response.content)
        except Exception as e:
            logger.error(f"Errore durante il download dell'immagine: {str(e)}")
            return None

    async def send_price_alert(self, product: Product, current_price: float):
        """
        Invia una notifica di prezzo al gruppo Telegram
        
        Args:
            product: Prodotto per cui inviare la notifica
            current_price: Prezzo corrente del prodotto
        """
        try:
            # Calcola la variazione percentuale
            if product.price_history:
                old_price = product.price_history[-1].price
                price_change = ((current_price - old_price) / old_price) * 100
            else:
                price_change = 0
            
            # Prepara il messaggio
            message = (
                f"🛍️ *{product.keyword}*\n\n"
                f"💰 Prezzo Attuale: €{current_price:.2f}\n"
                f"🎯 Prezzo Target: €{product.target_price:.2f}\n"
                f"📊 Variazione: {price_change:+.2f}%\n\n"
                f"🔗 [Vedi su Amazon]({product.url})"
            )
            
            # Genera e invia il grafico
            chart_buffer = self._generate_price_chart(product)
            await self.bot.send_photo(
                chat_id=self.group_id,
                photo=chart_buffer,
                caption=message,
                parse_mode='Markdown'
            )
            
            # Se disponibile, invia anche l'immagine del prodotto
            if product.image_url:
                image_buffer = self._download_product_image(product.image_url)
                if image_buffer:
                    await self.bot.send_photo(
                        chat_id=self.group_id,
                        photo=image_buffer,
                        caption=f"📸 Immagine prodotto: {product.keyword}"
                    )
                    
        except Exception as e:
            logger.error(f"Errore durante l'invio della notifica: {str(e)}")
            # Invia almeno il messaggio di testo in caso di errore con le immagini
            await self.bot.send_message(
                chat_id=self.group_id,
                text=message,
                parse_mode='Markdown'
            )

    async def send_status_message(self, products: List[Product]):
        """
        Invia un messaggio di stato con tutti i prodotti monitorati
        
        Args:
            products: Lista dei prodotti monitorati
        """
        if not products:
            message = "📝 *Stato Monitoraggio*\n\nNessun prodotto monitorato al momento."
        else:
            message = "📝 *Stato Monitoraggio*\n\n"
            for product in products:
                message += (
                    f"• {product.keyword}\n"
                    f"  Prezzo Target: €{product.target_price:.2f}\n"
                    f"  Ultimo Prezzo: €{product.last_price:.2f}\n"
                    f"  Ultimo Controllo: {product.last_check.strftime('%d/%m/%Y %H:%M')}\n\n"
                )
        
        await self.bot.send_message(
            chat_id=self.group_id,
            text=message,
            parse_mode='Markdown'
        )

    # Metodo sincrono per il monitor_service
    def notify_price_alert(self, product: Product, current_price: float):
        """Wrapper sincrono per send_price_alert"""
        loop = asyncio.get_event_loop()
        loop.create_task(self.send_price_alert(product, current_price))

    def send_status(self, products: List[Product]):
        """Wrapper sincrono per send_status_message"""
        loop = asyncio.get_event_loop()
        loop.create_task(self.send_status_message(products))