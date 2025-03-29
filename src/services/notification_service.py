import logging
import io
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import matplotlib.pyplot as plt
from telegram import Bot, InputMediaPhoto
from PIL import Image
import aiohttp
from collections import defaultdict

from config.config import (
    TELEGRAM_TOKEN,
    TELEGRAM_GROUP_ID,
    PRICE_HISTORY_DAYS,
    NOTIFICATION_BATCH_SIZE,
    NOTIFICATION_COOLDOWN
)
from src.database.models import Product, PriceHistory

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        """Inizializza il servizio di notifica"""
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.group_id = TELEGRAM_GROUP_ID
        self.notification_queue = defaultdict(list)  # ASIN -> list of notifications
        self.last_notification: Dict[str, datetime] = {}  # ASIN -> last notification time
        self._batch_lock = asyncio.Lock()
        self._http_session: Optional[aiohttp.ClientSession] = None

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Ottiene una sessione HTTP riutilizzabile"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    def _generate_price_chart(self, product: Product, trend: str = None) -> io.BytesIO:
        """
        Genera un grafico dello storico prezzi
        
        Args:
            product: Prodotto per cui generare il grafico
            trend: Trend del prezzo ('in calo', 'in aumento', 'stabile')
            
        Returns:
            Buffer contenente l'immagine del grafico
        """
        cutoff_date = datetime.utcnow() - timedelta(days=PRICE_HISTORY_DAYS)
        price_history = [ph for ph in product.price_history if ph.check_date >= cutoff_date]
        
        dates = [ph.check_date for ph in price_history]
        prices = [ph.price for ph in price_history]
        
        plt.figure(figsize=(10, 6))
        
        # Colore linea in base al trend
        line_color = {
            'in calo': 'g-',
            'in aumento': 'r-',
            'stabile': 'b-'
        }.get(trend, 'b-')
        
        plt.plot(dates, prices, line_color, label='Prezzo', linewidth=2)
        plt.axhline(
            y=product.target_price,
            color='r',
            linestyle='--',
            label='Prezzo Target',
            alpha=0.7
        )
        
        # Migliora l'aspetto del grafico
        plt.title(f"Storico Prezzi - {product.keyword}", pad=20)
        plt.xlabel("Data", labelpad=10)
        plt.ylabel("Prezzo (€)", labelpad=10)
        plt.grid(True, alpha=0.3)
        plt.legend(loc='upper right', framealpha=0.9)
        plt.xticks(rotation=45)
        
        # Aggiunge annotazioni per min/max
        if prices:
            min_price = min(prices)
            max_price = max(prices)
            min_date = dates[prices.index(min_price)]
            max_date = dates[prices.index(max_price)]
            
            plt.annotate(
                f'Min: €{min_price:.2f}',
                xy=(min_date, min_price),
                xytext=(10, -10),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5)
            )
            plt.annotate(
                f'Max: €{max_price:.2f}',
                xy=(max_date, max_price),
                xytext=(10, 10),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5)
            )
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        
        buf.seek(0)
        return buf

    async def _download_product_image(self, image_url: str) -> Optional[io.BytesIO]:
        """
        Scarica l'immagine del prodotto in modo asincrono
        
        Args:
            image_url: URL dell'immagine da scaricare
            
        Returns:
            Buffer contenente l'immagine o None in caso di errore
        """
        if not image_url:
            return None
            
        try:
            session = await self._get_http_session()
            async with session.get(image_url) as response:
                if response.status == 200:
                    content = await response.read()
                    return io.BytesIO(content)
        except Exception as e:
            logger.error(f"Errore durante il download dell'immagine: {str(e)}")
            return None

    def _format_price_message(
        self,
        product: Product,
        current_price: float,
        trend: str = None,
        change_percent: float = 0
    ) -> str:
        """Formatta il messaggio di notifica prezzo"""
        trend_emoji = {
            'in calo': '📉',
            'in aumento': '📈',
            'stabile': '📊'
        }.get(trend, '📊')

        message = (
            f"🛍️ *{product.keyword}*\n\n"
            f"💰 Prezzo Attuale: €{current_price:.2f}\n"
            f"🎯 Prezzo Target: €{product.target_price:.2f}\n"
            f"{trend_emoji} Trend: {trend or 'Non disponibile'}\n"
            f"📊 Variazione: {change_percent:+.2f}%\n\n"
        )

        if current_price <= product.target_price:
            message += "✨ *Prezzo al minimo!* ✨\n\n"

        message += f"🔗 [Vedi su Amazon]({product.url})"
        return message

    async def _can_send_notification(self, asin: str) -> bool:
        """Verifica se è possibile inviare una notifica per il prodotto"""
        if asin not in self.last_notification:
            return True
            
        time_since_last = datetime.utcnow() - self.last_notification[asin]
        return time_since_last >= timedelta(seconds=NOTIFICATION_COOLDOWN)

    async def send_price_alert(
        self,
        product: Product,
        current_price: float,
        trend: str = None,
        change_percent: float = 0
    ):
        """
        Invia una notifica di prezzo al gruppo Telegram
        
        Args:
            product: Prodotto per cui inviare la notifica
            current_price: Prezzo corrente del prodotto
            trend: Trend del prezzo ('in calo', 'in aumento', 'stabile')
            change_percent: Percentuale di variazione del prezzo
        """
        if not await self._can_send_notification(product.asin):
            async with self._batch_lock:
                self.notification_queue[product.asin].append({
                    'product': product,
                    'current_price': current_price,
                    'trend': trend,
                    'change_percent': change_percent
                })
            return

        try:
            # Prepara i media
            media_group = []
            message = self._format_price_message(
                product, current_price, trend, change_percent
            )

            # Genera e aggiungi il grafico
            chart_buffer = self._generate_price_chart(product, trend)
            media_group.append(
                InputMediaPhoto(
                    media=chart_buffer,
                    caption=message,
                    parse_mode='Markdown'
                )
            )

            # Aggiungi l'immagine del prodotto se disponibile
            if product.image_url:
                image_buffer = await self._download_product_image(product.image_url)
                if image_buffer:
                    media_group.append(InputMediaPhoto(media=image_buffer))

            # Invia il gruppo di media
            await self.bot.send_media_group(
                chat_id=self.group_id,
                media=media_group
            )

            self.last_notification[product.asin] = datetime.utcnow()

        except Exception as e:
            logger.error(f"Errore durante l'invio della notifica: {str(e)}")
            # Fallback: invia solo il messaggio di testo
            try:
                await self.bot.send_message(
                    chat_id=self.group_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Errore anche nel fallback della notifica: {str(e)}")

    async def process_notification_queue(self):
        """Processa la coda delle notifiche in batch"""
        async with self._batch_lock:
            for asin, notifications in self.notification_queue.items():
                if not notifications:
                    continue

                if await self._can_send_notification(asin):
                    # Prendi l'ultima notifica del batch
                    latest = notifications[-1]
                    await self.send_price_alert(
                        latest['product'],
                        latest['current_price'],
                        latest['trend'],
                        latest['change_percent']
                    )
                    # Svuota la coda per questo prodotto
                    self.notification_queue[asin].clear()

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
                trend = "Non disponibile"
                if len(product.price_history) >= 2:
                    last_prices = [ph.price for ph in product.price_history[-2:]]
                    diff = last_prices[1] - last_prices[0]
                    if abs(diff) < 0.01:
                        trend = "Stabile"
                    else:
                        trend = "In aumento" if diff > 0 else "In calo"

                message += (
                    f"• {product.keyword}\n"
                    f"  💰 Prezzo Target: €{product.target_price:.2f}\n"
                    f"  📊 Ultimo Prezzo: €{product.last_price:.2f}\n"
                    f"  📈 Trend: {trend}\n"
                    f"  🕒 Ultimo Controllo: {product.last_check.strftime('%d/%m/%Y %H:%M')}\n\n"
                )

        await self.bot.send_message(
            chat_id=self.group_id,
            text=message,
            parse_mode='Markdown'
        )

    async def cleanup(self):
        """Pulisce le risorse del servizio"""
        if self._http_session:
            await self._http_session.close()
            self._http_session = None