import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from typing import Dict, Any

from src.services.keepa_service import KeepaService
from src.services.monitor_service import MonitorService
from src.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Stati della conversazione
KEYWORD, SELECT_PRODUCT, TARGET_PRICE = range(3)

# Timeout della conversazione (in secondi)
CONVERSATION_TIMEOUT = 300  # 5 minuti

class CommandHandlers:
    def __init__(self, monitor_service: MonitorService, notification_service: NotificationService):
        """
        Inizializza gli handlers dei comandi
        
        Args:
            monitor_service: Servizio di monitoraggio
            notification_service: Servizio di notifica
        """
        self.monitor_service = monitor_service
        self.notification_service = notification_service
        self.keepa_service = KeepaService()
        self.temp_data: Dict[int, Dict[str, Any]] = {}
        self._cleanup_task = None

    async def start_cleanup_task(self):
        """Avvia il task di pulizia in background"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def _periodic_cleanup(self):
        """Task periodico per la pulizia dei dati temporanei"""
        while True:
            try:
                await self._cleanup_temp_data()
                await asyncio.sleep(60)  # Controlla ogni minuto
            except Exception as e:
                logger.error(f"Errore nel task di pulizia: {str(e)}")
                await asyncio.sleep(300)  # In caso di errore, attende 5 minuti

    async def _cleanup_temp_data(self):
        """Rimuove i dati temporanei scaduti"""
        now = datetime.now()
        expired_keys = [
            user_id for user_id, data in self.temp_data.items()
            if 'timestamp' in data and now - data['timestamp'] > timedelta(seconds=CONVERSATION_TIMEOUT)
        ]
        
        for key in expired_keys:
            del self.temp_data[key]
            
        if expired_keys:
            logger.debug(f"Rimossi {len(expired_keys)} record scaduti dai dati temporanei")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /start"""
        welcome_message = (
            "👋 Benvenuto nel bot di monitoraggio prezzi Keepa!\n\n"
            "Comandi disponibili:\n"
            "/monitor - Monitora un nuovo prodotto\n"
            "/list - Lista prodotti monitorati\n"
            "/delete - Rimuovi un prodotto dal monitoraggio\n"
            "/status - Stato del sistema con grafici\n"
            "/history <ASIN> - Storico prezzi di un prodotto\n"
            "/help - Mostra questo messaggio"
        )
        await update.message.reply_text(welcome_message)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /help"""
        await self.start(update, context)

    async def monitor_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Avvia il processo di monitoraggio di un nuovo prodotto"""
        await self.start_cleanup_task()
        
        await update.message.reply_text(
            "🔍 Inserisci la parola chiave o l'ASIN del prodotto da cercare:"
        )
        return KEYWORD

    async def monitor_keyword(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce la ricerca del prodotto per parola chiave"""
        keyword = update.message.text
        user_id = update.effective_user.id
        processing_message = await update.message.reply_text("🔍 Ricerca prodotti in corso...")
        
        try:
            products = await self.keepa_service.search_products(keyword)
            await processing_message.delete()
            
            if not products:
                await update.message.reply_text(
                    "❌ Nessun prodotto trovato. Riprova con un'altra parola chiave."
                )
                return ConversationHandler.END
            
            self.temp_data[user_id] = {
                'keyword': keyword,
                'products': products,
                'timestamp': datetime.now()
            }
            
            keyboard = []
            for i, product in enumerate(products[:5]):
                title = product['title'][:50] + "..." if len(product['title']) > 50 else product['title']
                price = product['current_price']
                lowest = product.get('lowest_price', price)
                highest = product.get('highest_price', price)
                
                button = [InlineKeyboardButton(
                    f"{title}\n💰 €{price:.2f} (Min: €{lowest:.2f}, Max: €{highest:.2f})",
                    callback_data=f"product_{i}"
                )]
                keyboard.append(button)
            
            keyboard.append([InlineKeyboardButton("❌ Annulla", callback_data="cancel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📦 Seleziona il prodotto da monitorare:",
                reply_markup=reply_markup
            )
            return SELECT_PRODUCT
            
        except Exception as e:
            logger.error(f"Errore durante la ricerca: {str(e)}")
            await processing_message.delete()
            await update.message.reply_text(
                "❌ Si è verificato un errore durante la ricerca. Riprova più tardi."
            )
            return ConversationHandler.END

    async def monitor_select_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce la selezione del prodotto"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        try:
            await query.answer()
            
            if query.data == "cancel":
                if user_id in self.temp_data:
                    del self.temp_data[user_id]
                await query.message.edit_text("❌ Operazione annullata.")
                return ConversationHandler.END
            
            temp_data = self.temp_data.get(user_id)
            if not temp_data:
                await query.message.edit_text("❌ Sessione scaduta. Riavvia il processo con /monitor")
                return ConversationHandler.END
            
            product_index = int(query.data.split('_')[1])
            selected_product = temp_data['products'][product_index]
            
            temp_data['selected_product'] = selected_product
            temp_data['timestamp'] = datetime.now()
            self.temp_data[user_id] = temp_data
            
            # Mostra il grafico dello storico prezzi
            price_history = await self.keepa_service.get_product_price_history(selected_product['asin'])
            
            await self.notification_service.send_price_alert(
                product=None,  # Non è ancora un prodotto monitorato
                current_price=selected_product['current_price'],
                preview_mode=True,
                product_data={
                    'title': selected_product['title'],
                    'asin': selected_product['asin'],
                    'url': selected_product['url'],
                    'image_url': selected_product.get('image_url'),
                    'price_history': price_history
                }
            )
            
            await query.message.reply_text(
                f"💰 Inserisci il prezzo target per {selected_product['title'][:50]}...\n"
                f"Prezzo attuale: €{selected_product['current_price']:.2f}\n"
                f"Minimo storico: €{selected_product.get('lowest_price', selected_product['current_price']):.2f}"
            )
            return TARGET_PRICE
            
        except Exception as e:
            logger.error(f"Errore durante la selezione: {str(e)}")
            await query.message.edit_text("❌ Si è verificato un errore. Riprova con /monitor")
            return ConversationHandler.END

    async def monitor_target_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce l'inserimento del prezzo target"""
        user_id = update.effective_user.id
        
        try:
            target_price = float(update.message.text.replace('€', '').strip())
            if target_price <= 0:
                raise ValueError("Il prezzo deve essere maggiore di 0")
                
            temp_data = self.temp_data.get(user_id)
            if not temp_data:
                await update.message.reply_text("❌ Sessione scaduta. Riavvia il processo con /monitor")
                return ConversationHandler.END
            
            selected_product = temp_data['selected_product']
            
            product = await self.monitor_service.add_product_to_monitor(
                asin=selected_product['asin'],
                keyword=temp_data['keyword'],
                target_price=target_price
            )
            
            del self.temp_data[user_id]
            
            await update.message.reply_text(
                f"✅ Monitoraggio attivato per {selected_product['title'][:50]}...\n"
                f"Ti notificherò quando il prezzo scenderà sotto €{target_price:.2f}"
            )
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "❌ Inserisci un prezzo valido (es. 29.99)"
            )
            return TARGET_PRICE
            
        except Exception as e:
            logger.error(f"Errore durante l'aggiunta del monitoraggio: {str(e)}")
            await update.message.reply_text(
                "❌ Si è verificato un errore durante l'aggiunta del monitoraggio. Riprova più tardi."
            )
            return ConversationHandler.END

    async def list_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /list"""
        try:
            products = await self.monitor_service.get_monitored_products()
            if not products:
                await update.message.reply_text("📝 Nessun prodotto monitorato.")
                return
            
            await self.notification_service.send_status_message(products)
            
        except Exception as e:
            logger.error(f"Errore durante il listing dei prodotti: {str(e)}")
            await update.message.reply_text(
                "❌ Si è verificato un errore durante il recupero dei prodotti."
            )

    async def delete_product_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /delete"""
        products = await self.monitor_service.get_monitored_products()
        
        if not products:
            await update.message.reply_text("❌ Nessun prodotto monitorato.")
            return
        
        keyboard = []
        for product in products:
            current_price = product.last_price
            target_price = product.target_price
            diff = current_price - target_price
            status_emoji = "🟢" if diff <= 0 else "🔴"
            
            button = [InlineKeyboardButton(
                f"{status_emoji} {product.keyword} - Target: €{target_price:.2f}",
                callback_data=f"delete_{product.asin}"
            )]
            keyboard.append(button)
        
        keyboard.append([InlineKeyboardButton("❌ Annulla", callback_data="cancel_delete")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🗑️ Seleziona il prodotto da rimuovere:",
            reply_markup=reply_markup
        )

    async def delete_product_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce la selezione del prodotto da eliminare"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel_delete":
            await query.message.edit_text("❌ Operazione annullata.")
            return
        
        try:
            asin = query.data.split('_')[1]
            if await self.monitor_service.remove_product(asin):
                await query.message.edit_text("✅ Prodotto rimosso dal monitoraggio.")
            else:
                await query.message.edit_text("❌ Prodotto non trovato.")
                
        except Exception as e:
            logger.error(f"Errore durante la rimozione: {str(e)}")
            await query.message.edit_text(
                "❌ Si è verificato un errore durante la rimozione."
            )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /status"""
        try:
            products = await self.monitor_service.get_monitored_products()
            await self.notification_service.send_status_message(
                products, include_charts=True
            )
        except Exception as e:
            logger.error(f"Errore durante il controllo dello stato: {str(e)}")
            await update.message.reply_text(
                "❌ Si è verificato un errore durante il recupero dello stato."
            )

    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /history"""
        if not context.args:
            await update.message.reply_text(
                "❌ Specificare l'ASIN del prodotto (es. /history B0088PUEPK)"
            )
            return
            
        asin = context.args[0]
        try:
            price_history = await self.keepa_service.get_product_price_history(asin)
            if not price_history:
                await update.message.reply_text(
                    "❌ Prodotto non trovato o storico prezzi non disponibile."
                )
                return
                
            await self.notification_service.send_price_history(
                price_history, include_trend=True
            )
            
        except Exception as e:
            logger.error(f"Errore nel recupero dello storico prezzi: {str(e)}")
            await update.message.reply_text(
                "❌ Si è verificato un errore nel recupero dello storico prezzi."
            )

    def get_handlers(self):
        """
        Restituisce tutti gli handlers dei comandi
        
        Returns:
            Lista di handlers per il bot
        """
        monitor_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('monitor', self.monitor_start)],
            states={
                KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.monitor_keyword)],
                SELECT_PRODUCT: [CallbackQueryHandler(self.monitor_select_product, pattern='^(product_|cancel)')],
                TARGET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.monitor_target_price)]
            },
            fallbacks=[
                CommandHandler('cancel', lambda u, c: ConversationHandler.END),
                MessageHandler(filters.COMMAND, lambda u, c: ConversationHandler.END)
            ],
            conversation_timeout=CONVERSATION_TIMEOUT
        )
        
        return [
            CommandHandler('start', self.start),
            CommandHandler('help', self.help),
            monitor_conv_handler,
            CommandHandler('list', self.list_products),
            CommandHandler('delete', self.delete_product_start),
            CallbackQueryHandler(self.delete_product_select, pattern='^(delete_|cancel_delete)'),
            CommandHandler('status', self.status),
            CommandHandler('history', self.history)
        ]
