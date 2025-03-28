import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters

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
        
        # Dizionario temporaneo per memorizzare i dati della conversazione
        self.temp_data = {}
        # Timer per la pulizia dei dati temporanei
        self._schedule_cleanup()

    def _schedule_cleanup(self):
        """Programma la pulizia periodica dei dati temporanei"""
        self._cleanup_temp_data()

    def _cleanup_temp_data(self):
        """Rimuove i dati temporanei scaduti"""
        now = datetime.now()
        expired_keys = []
        
        for user_id, data in self.temp_data.items():
            if 'timestamp' in data:
                if now - data['timestamp'] > timedelta(seconds=CONVERSATION_TIMEOUT):
                    expired_keys.append(user_id)
        
        for key in expired_keys:
            del self.temp_data[key]
            
        if expired_keys:
            logger.debug(f"Rimossi {len(expired_keys)} record scaduti dai dati temporanei")

    async def _timeout_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il timeout della conversazione"""
        user_id = update.effective_user.id
        if user_id in self.temp_data:
            del self.temp_data[user_id]
        
        await update.message.reply_text(
            "⏰ Timeout della conversazione. Usa /monitor per iniziare una nuova ricerca."
        )
        return ConversationHandler.END

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /start"""
        welcome_message = (
            "👋 Benvenuto nel bot di monitoraggio prezzi Keepa!\n\n"
            "Comandi disponibili:\n"
            "/monitor - Monitora un nuovo prodotto\n"
            "/list - Lista prodotti monitorati\n"
            "/delete - Rimuovi un prodotto dal monitoraggio\n"
            "/status - Stato del sistema\n"
            "/help - Mostra questo messaggio"
        )
        await update.message.reply_text(welcome_message)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /help"""
        await self.start(update, context)

    async def monitor_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Avvia il processo di monitoraggio di un nuovo prodotto"""
        # Imposta il timer di timeout
        context.job_queue.run_once(
            lambda ctx: self._timeout_handler(update, context),
            CONVERSATION_TIMEOUT
        )
        
        await update.message.reply_text(
            "🔍 Inserisci la parola chiave per cercare il prodotto:"
        )
        return KEYWORD

    async def monitor_keyword(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce la ricerca del prodotto per parola chiave"""
        keyword = update.message.text
        user_id = update.effective_user.id
        
        try:
            # Cerca i prodotti su Keepa
            products = self.keepa_service.search_products(keyword)
            
            if not products:
                await update.message.reply_text(
                    "❌ Nessun prodotto trovato. Riprova con un'altra parola chiave."
                )
                return ConversationHandler.END
            
            # Memorizza i risultati temporaneamente
            self.temp_data[user_id] = {
                'keyword': keyword,
                'products': products,
                'timestamp': datetime.now()
            }
            
            # Crea la tastiera inline con i prodotti
            keyboard = []
            for i, product in enumerate(products[:5]):  # Limitiamo a 5 risultati
                title = product['title'][:50] + "..." if len(product['title']) > 50 else product['title']
                price = product['current_price']
                button = [InlineKeyboardButton(
                    f"{title} - €{price:.2f}",
                    callback_data=f"product_{i}"
                )]
                keyboard.append(button)
            
            # Aggiungi pulsante di cancellazione
            keyboard.append([
                InlineKeyboardButton("❌ Annulla", callback_data="cancel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📦 Seleziona il prodotto da monitorare:",
                reply_markup=reply_markup
            )
            return SELECT_PRODUCT
            
        except Exception as e:
            logger.error(f"Errore durante la ricerca: {str(e)}")
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
                await query.message.reply_text("❌ Operazione annullata.")
                return ConversationHandler.END
            
            # Recupera i dati temporanei
            temp_data = self.temp_data.get(user_id)
            if not temp_data:
                await query.message.reply_text("❌ Sessione scaduta. Riavvia il processo con /monitor")
                return ConversationHandler.END
            
            # Ottiene l'indice del prodotto selezionato
            product_index = int(query.data.split('_')[1])
            selected_product = temp_data['products'][product_index]
            
            # Aggiorna il timestamp
            temp_data['selected_product'] = selected_product
            temp_data['timestamp'] = datetime.now()
            self.temp_data[user_id] = temp_data
            
            await query.message.reply_text(
                f"💰 Inserisci il prezzo target per {selected_product['title'][:50]}..."
            )
            return TARGET_PRICE
            
        except Exception as e:
            logger.error(f"Errore durante la selezione: {str(e)}")
            await query.message.reply_text("❌ Si è verificato un errore. Riprova con /monitor")
            return ConversationHandler.END

    async def monitor_target_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce l'inserimento del prezzo target"""
        user_id = update.effective_user.id
        
        try:
            target_price = float(update.message.text.replace('€', '').strip())
            if target_price <= 0:
                raise ValueError("Il prezzo deve essere maggiore di 0")
                
            # Recupera i dati temporanei
            temp_data = self.temp_data.get(user_id)
            if not temp_data:
                await update.message.reply_text("❌ Sessione scaduta. Riavvia il processo con /monitor")
                return ConversationHandler.END
            
            selected_product = temp_data['selected_product']
            
            # Aggiunge il prodotto al monitoraggio
            product = self.monitor_service.add_product_to_monitor(
                asin=selected_product['asin'],
                keyword=temp_data['keyword'],
                target_price=target_price
            )
            
            # Pulisce i dati temporanei
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
            products = self.monitor_service.get_monitored_products()
            if not products:
                await update.message.reply_text("📝 Nessun prodotto monitorato.")
                return
            
            message = "📝 Prodotti monitorati:\n\n"
            for product in products:
                message += f"• {product.keyword}\n"
                message += f"  Prezzo target: €{product.target_price:.2f}\n"
                message += f"  Ultimo prezzo: €{product.last_price:.2f}\n"
                message += f"  Ultimo controllo: {product.last_check.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Errore durante il listing dei prodotti: {str(e)}")
            await update.message.reply_text("❌ Si è verificato un errore durante il recupero dei prodotti.")

    async def delete_product_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /delete"""
        products = self.monitor_service.get_monitored_products()
        
        if not products:
            await update.message.reply_text("❌ Nessun prodotto monitorato.")
            return
        
        keyboard = []
        for product in products:
            button = [InlineKeyboardButton(
                f"{product.keyword} - €{product.target_price:.2f}",
                callback_data=f"delete_{product.asin}"
            )]
            keyboard.append(button)
        
        # Aggiungi pulsante di cancellazione
        keyboard.append([
            InlineKeyboardButton("❌ Annulla", callback_data="cancel_delete")
        ])
        
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
            await query.message.reply_text("❌ Operazione annullata.")
            return
        
        try:
            asin = query.data.split('_')[1]
            if self.monitor_service.remove_product(asin):
                await query.message.reply_text("✅ Prodotto rimosso dal monitoraggio.")
            else:
                await query.message.reply_text("❌ Prodotto non trovato.")
                
        except Exception as e:
            logger.error(f"Errore durante la rimozione: {str(e)}")
            await query.message.reply_text("❌ Si è verificato un errore durante la rimozione.")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /status"""
        try:
            products = self.monitor_service.get_monitored_products()
            if not products:
                await update.message.reply_text("📊 Stato del sistema:\nNessun prodotto monitorato.")
                return
            
            message = "📊 Stato del sistema:\n\n"
            message += f"Prodotti monitorati: {len(products)}\n\n"
            
            for product in products:
                price_diff = product.last_price - product.target_price
                status_emoji = "🟢" if price_diff <= 0 else "🔴"
                
                message += f"{status_emoji} {product.keyword}\n"
                message += f"   Target: €{product.target_price:.2f}\n"
                message += f"   Attuale: €{product.last_price:.2f}\n"
                message += f"   Differenza: €{price_diff:.2f}\n"
                message += f"   Ultimo check: {product.last_check.strftime('%H:%M:%S %d/%m/%Y')}\n\n"
            
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Errore durante il controllo dello stato: {str(e)}")
            await update.message.reply_text("❌ Si è verificato un errore durante il recupero dello stato.")

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
            CommandHandler('status', self.status)
        ]
