"""
Formattazione dei messaggi per Telegram con le offerte Amazon.
"""
from typing import Dict, Any
import html
from datetime import datetime

from config.config import Config

class MessageFormatter:
    @staticmethod
    def format_price(price: float) -> str:
        """Formatta il prezzo in formato EUR"""
        return f"{price:.2f}€"

    @staticmethod
    def format_deal_message(product_data: Dict[str, Any], discount_percentage: float) -> Dict[str, Any]:
        """
        Formatta un messaggio per un'offerta Amazon.
        
        Args:
            product_data: Dati del prodotto da Keepa
            discount_percentage: Percentuale di sconto calcolata
            
        Returns:
            Dizionario con testo del messaggio e altre opzioni di formattazione
        """
        # Escape dei caratteri speciali HTML
        title = html.escape(product_data['title'])
        current_price = MessageFormatter.format_price(product_data['current_price'])
        lowest_price = MessageFormatter.format_price(product_data['lowest_price_30d'])
        highest_price = MessageFormatter.format_price(product_data['highest_price_30d'])
        
        # Creazione del link al prodotto con referral code
        product_url = Config.get_product_url(product_data['asin'])
        
        # Costruzione del messaggio
        message = (
            f"🔥 <b>OFFERTA AMAZON!</b> 🔥\n\n"
            f"📦 <b>{title}</b>\n\n"
            f"💰 <b>Prezzo Attuale:</b> {current_price}\n"
            f"📉 <b>Prezzo più basso (30gg):</b> {lowest_price}\n"
            f"📈 <b>Prezzo più alto (30gg):</b> {highest_price}\n"
            f"🏷️ <b>Sconto:</b> {discount_percentage:.1f}%\n\n"
            f"🛒 <a href='{product_url}'>Acquista su Amazon</a>"
        )

        # Se disponibile, aggiungi il link all'immagine
        image_url = product_data.get('image_url')
        
        return {
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': not bool(image_url),
            'image_url': image_url
        }

    @staticmethod
    def format_error_message(error: str) -> Dict[str, Any]:
        """
        Formatta un messaggio di errore.
        
        Args:
            error: Messaggio di errore
            
        Returns:
            Dizionario con testo del messaggio e opzioni di formattazione
        """
        message = (
            f"⚠️ <b>Errore</b>\n\n"
            f"{html.escape(error)}\n"
            f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        
        return {
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }

    @staticmethod
    def format_status_message(status: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formatta un messaggio di stato del bot.
        
        Args:
            status: Dizionario con informazioni sullo stato
            
        Returns:
            Dizionario con testo del messaggio e opzioni di formattazione
        """
        keywords = status.get('keywords', [])
        products = status.get('products', 0)
        last_check = status.get('last_check', datetime.utcnow())
        
        keywords_str = "\n".join([f"- {k}" for k in keywords]) if keywords else "Nessuna keyword configurata"
        
        message = (
            f"📊 <b>Stato del Bot</b>\n\n"
            f"🔍 <b>Keywords monitorate:</b>\n{keywords_str}\n\n"
            f"📦 <b>Prodotti monitorati:</b> {products}\n"
            f"🕒 <b>Ultimo controllo:</b> {last_check.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return {
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }

    @staticmethod
    def format_test_message() -> Dict[str, Any]:
        """
        Crea un messaggio di test per verificare la connessione con Telegram.
        
        Returns:
            Dizionario con testo del messaggio e opzioni di formattazione
        """
        message = (
            f"✅ <b>Test Bot Amazon Deals</b>\n\n"
            f"Il bot è online e funzionante.\n"
            f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        
        return {
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }