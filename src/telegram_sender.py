"""
Gestione dell'invio dei messaggi su Telegram.
"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from telegram import Bot, InputMediaPhoto
from telegram.error import TelegramError, RetryAfter
from telegram.constants import ParseMode

from config.config import Config

logger = logging.getLogger(__name__)

class TelegramSender:
    def __init__(self):
        self.bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
        self.channel_id = Config.TELEGRAM_CHANNEL_ID
        self.last_message_time = datetime.now()
        self.min_interval = 1  # Intervallo minimo tra i messaggi in secondi

    async def send_message(self, message_data: Dict[str, Any], retry_count: int = 0) -> bool:
        """
        Invia un messaggio al canale Telegram.
        
        Args:
            message_data: Dizionario contenente il testo e le opzioni del messaggio
            retry_count: Numero di tentativi già effettuati
            
        Returns:
            bool: True se l'invio è riuscito, False altrimenti
        """
        if retry_count >= Config.MAX_RETRIES:
            logger.error(f"Raggiunto numero massimo di tentativi per l'invio del messaggio")
            return False

        # Rispetta l'intervallo minimo tra i messaggi
        now = datetime.now()
        time_since_last = (now - self.last_message_time).total_seconds()
        if time_since_last < self.min_interval:
            await asyncio.sleep(self.min_interval - time_since_last)

        try:
            # Se c'è un'immagine, inviala con il messaggio
            if message_data.get('image_url'):
                await self.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=message_data['image_url'],
                    caption=message_data['text'],
                    parse_mode=ParseMode.HTML
                )
            else:
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=message_data['text'],
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=message_data.get('disable_web_page_preview', True)
                )

            self.last_message_time = datetime.now()
            return True

        except RetryAfter as e:
            # Telegram ci chiede di aspettare
            wait_time = int(str(e).split()[-1])
            logger.warning(f"Rate limit raggiunto. Attendo {wait_time} secondi")
            await asyncio.sleep(wait_time)
            return await self.send_message(message_data, retry_count + 1)

        except TelegramError as e:
            logger.error(f"Errore Telegram durante l'invio del messaggio: {str(e)}")
            if "Too Many Requests" in str(e):
                await asyncio.sleep(5 * (retry_count + 1))  # Backoff esponenziale
                return await self.send_message(message_data, retry_count + 1)
            return False

        except Exception as e:
            logger.error(f"Errore generico durante l'invio del messaggio: {str(e)}")
            return False

    async def send_bulk_messages(self, messages: list[Dict[str, Any]]) -> tuple[int, int]:
        """
        Invia una lista di messaggi rispettando i rate limits.
        
        Args:
            messages: Lista di dizionari contenenti i messaggi da inviare
            
        Returns:
            tuple: (numero messaggi inviati con successo, numero messaggi falliti)
        """
        success_count = 0
        fail_count = 0

        for message in messages:
            if await self.send_message(message):
                success_count += 1
            else:
                fail_count += 1
            # Aggiungi un piccolo delay tra i messaggi per evitare il rate limiting
            await asyncio.sleep(1.5)

        return success_count, fail_count

    async def send_error_notification(self, error: str) -> bool:
        """
        Invia una notifica di errore al canale.
        
        Args:
            error: Messaggio di errore
            
        Returns:
            bool: True se l'invio è riuscito, False altrimenti
        """
        error_message = {
            'text': f"⚠️ <b>Errore del Bot</b>\n\n{error}",
            'parse_mode': ParseMode.HTML,
            'disable_web_page_preview': True
        }
        return await self.send_message(error_message)

    async def test_connection(self) -> bool:
        """
        Testa la connessione con Telegram inviando un messaggio di prova.
        
        Returns:
            bool: True se il test è riuscito, False altrimenti
        """
        test_message = {
            'text': "🔄 Test connessione bot Amazon Deals - OK",
            'parse_mode': ParseMode.HTML,
            'disable_web_page_preview': True
        }
        return await self.send_message(test_message)