import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from src.services.keepa_service import KeepaService
from src.services.monitor_service import MonitorService
from src.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Stati della conversazione
KEYWORD, SELECT_PRODUCT, TARGET_PRICE = range(3)

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
            products = await self.keepa_service.search_products(keyword)
            
            if not products:
                await update.message.reply_text(
                    "❌ Nessun prodotto trovato. Riprova con un'altra parola chiave."
                )
                return ConversationHandler.END
            
            # Memorizza i risultati temporaneamente
            self.temp_data[user_id] = {
                'keyword': keyword,
                'products': products
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
            
            # Recupera i dati temporanei
            temp_data = self.temp_data.get(user_id, {})
            if not temp_data:
                await query.message.reply_text("❌ Sessione scaduta. Riavvia il processo con /monitor")
                return ConversationHandler.END
            
            # Ottiene l'indice del prodotto selezionato
            product_index = int(query.data.split('_')[1])
            selected_product = temp_data['products'][product_index]
            
            # Memorizza il prodotto selezionato
            temp_data['selected_product'] = selected_product
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
            temp_data = self.temp_data.get(user_id, {})
            if not temp_data:
                await update.message.reply_text("❌ Sessione scaduta. Riavvia il processo con /monitor")
                return ConversationHandler.END
            
            selected_product = temp_data['selected_product']
            
            # Aggiunge il prodotto al monitoraggio
            product = await self.monitor_service.add_product_to_monitor(
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
        products = await self.monitor_service.get_monitored_products()
        await self.notification_service.send_status_message(products)

    async def delete_product_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /delete"""
        products = await self.monitor_service.get_monitored_products()
        
        if not products:
            await update.message.reply_text("❌ Nessun prodotto monitorato.")
            return ConversationHandler.END
        
        keyboard = []
        for product in products:
            button = [InlineKeyboardButton(
                f"{product.keyword} - €{product.target_price:.2f}",
                callback_data=f"delete_{product.asin}"
            )]
            keyboard.append(button)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🗑️ Seleziona il prodotto da rimuovere:",
            reply_markup=reply_markup
        )

    async def delete_product_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce la selezione del prodotto da eliminare"""
        query = update.callback_query
        await query.answer()
        
        try:
            asin = query.data.split('_')[1]
            if await self.monitor_service.remove_product(asin):
                await query.message.reply_text("✅ Prodotto rimosso dal monitoraggio.")
            else:
                await query.message.reply_text("❌ Prodotto non trovato.")
                
        except Exception as e:
            logger.error(f"Errore durante la rimozione: {str(e)}")
            await query.message.reply_text("❌ Si è verificato un errore durante la rimozione.")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /status"""
        products = await self.monitor_service.get_monitored_products()
        await self.notification_service.send_status_message(products)

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
                SELECT_PRODUCT: [CallbackQueryHandler(self.monitor_select_product, pattern='^product_')],
                TARGET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.monitor_target_price)]
            },
            fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
        )
        
        return [
            CommandHandler('start', self.start),
            CommandHandler('help', self.help),
            monitor_conv_handler,
            CommandHandler('list', self.list_products),
            CommandHandler('delete', self.delete_product_start),
            CallbackQueryHandler(self.delete_product_select, pattern='^delete_'),
            CommandHandler('status', self.status)
        ]