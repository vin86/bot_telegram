from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)
import logging
from typing import Dict, Optional

from database import db
from keepa_client import keepa_client
from chart_generator import chart_generator
from config import (
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    MAX_PRODUCTS_PER_USER
)

# Stati della conversazione
WAITING_FOR_URL = 1
WAITING_FOR_PRICE = 2

# Callback data patterns
REMOVE_PRODUCT = "remove_"
REFRESH_PRODUCT = "refresh_"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BotHandler:
    def __init__(self):
        self.conversations: Dict[int, Dict] = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /start"""
        if not update.effective_user:
            return

        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"

        # Registra o aggiorna l'utente nel database
        db.add_user(user_id, username)

        await update.message.reply_text(
            WELCOME_MESSAGE,
            parse_mode='HTML'
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /help"""
        await update.message.reply_text(
            HELP_MESSAGE,
            parse_mode='HTML'
        )

    async def add_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inizia il processo di aggiunta di un nuovo prodotto"""
        if not update.effective_user:
            return

        user_id = update.effective_user.id
        
        # Controlla il limite di prodotti per utente
        products = db.get_user_products(user_id)
        if len(products) >= MAX_PRODUCTS_PER_USER:
            await update.message.reply_text(
                f"⚠️ Hai raggiunto il limite massimo di {MAX_PRODUCTS_PER_USER} prodotti monitorati.\n"
                "Rimuovi alcuni prodotti prima di aggiungerne altri."
            )
            return ConversationHandler.END

        await update.message.reply_text(
            "📦 Inviami il link del prodotto Amazon che vuoi monitorare:"
        )
        
        return WAITING_FOR_URL

    async def process_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processa l'URL del prodotto inviato dall'utente"""
        if not update.effective_user or not update.message:
            return ConversationHandler.END

        user_id = update.effective_user.id
        url = update.message.text.strip()

        # Recupera le informazioni del prodotto
        product_info = keepa_client.get_product_info(url)
        if not product_info:
            await update.message.reply_text(
                "❌ Link non valido o prodotto non trovato.\n"
                "Assicurati di inviare un link Amazon valido e riprova con /add"
            )
            return ConversationHandler.END

        # Salva le informazioni del prodotto nella conversazione
        self.conversations[user_id] = product_info

        await update.message.reply_text(
            f"✅ Prodotto trovato: {product_info['title']}\n\n"
            f"💰 Prezzo attuale: €{product_info['current_price']:.2f}\n"
            f"📉 Prezzo minimo (30 giorni): €{product_info['min_historic_price']:.2f}\n"
            f"📉 Prezzo più basso di sempre: €{product_info['all_time_min_price']:.2f}\n\n"
            "Inserisci il prezzo target (es. 29.99):"
        )

        return WAITING_FOR_PRICE

    async def process_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processa il prezzo target inserito dall'utente"""
        if not update.effective_user or not update.message:
            return ConversationHandler.END

        user_id = update.effective_user.id
        
        try:
            target_price = float(update.message.text.replace(',', '.'))
            if target_price <= 0:
                raise ValueError("Il prezzo deve essere maggiore di zero")

            product_info = self.conversations.get(user_id)
            if not product_info:
                await update.message.reply_text(
                    "❌ Sessione scaduta. Riprova con /add"
                )
                return ConversationHandler.END

            # Aggiungi il prezzo target alle informazioni del prodotto
            product_info['target_price'] = target_price

            # Salva il prodotto nel database
            db.add_product(user_id, product_info)

            # Genera e invia il grafico dei prezzi
            chart = chart_generator.generate_price_chart(
                product_info['price_history'],
                target_price,
                product_info['title']
            )

            await update.message.reply_photo(
                photo=chart,
                caption=(
                    f"✅ Monitoraggio attivato!\n\n"
                    f"📦 {product_info['title']}\n"
                    f"💰 Prezzo attuale: €{product_info['current_price']:.2f}\n"
                    f"🎯 Prezzo target: €{target_price:.2f}\n"
                    f"📉 Prezzo minimo (30 giorni): €{product_info['min_historic_price']:.2f}\n"
                    f"📉 Prezzo più basso di sempre: €{product_info['all_time_min_price']:.2f}\n\n"
                    "Ti avviserò quando il prezzo scenderà sotto il target!\n\n"
                    "Come affiliato Amazon, guadagno un compenso per ogni acquisto idoneo."
                )
            )

            # Pulisci i dati della conversazione
            del self.conversations[user_id]

        except (ValueError, KeyError) as e:
            await update.message.reply_text(
                "❌ Prezzo non valido. Inserisci un numero valido (es. 29.99)"
            )
            return WAITING_FOR_PRICE

        return ConversationHandler.END

    async def list_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mostra la lista dei prodotti monitorati"""
        if not update.effective_user:
            return

        user_id = update.effective_user.id
        products = db.get_user_products(user_id)

        if not products:
            await update.message.reply_text(
                "📝 Non stai monitorando alcun prodotto.\n"
                "Usa /add per iniziare a monitorare un prodotto!"
            )
            return

        for product in products:
            # Genera il grafico aggiornato
            chart = chart_generator.generate_price_chart(
                product['price_history'],
                product['target_price'],
                product['title']
            )

            # Crea i pulsanti inline
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔄 Aggiorna",
                        callback_data=f"{REFRESH_PRODUCT}{product['asin']}"
                    ),
                    InlineKeyboardButton(
                        "❌ Rimuovi",
                        callback_data=f"{REMOVE_PRODUCT}{product['asin']}"
                    )
                ]
            ]

            await update.message.reply_photo(
                photo=chart,
                caption=(
                    f"📦 {product['title']}\n\n"
                    f"💰 Prezzo attuale: €{product['current_price']:.2f}\n"
                    f"🎯 Prezzo target: €{product['target_price']:.2f}\n"
                    f"📉 Prezzo minimo (30 giorni): €{product['min_historic_price']:.2f}\n"
                    f"📉 Prezzo più basso di sempre: €{product['all_time_min_price']:.2f}\n"
                    f"🔄 Ultimo controllo: {product['last_checked'].strftime('%d/%m/%Y %H:%M')}\n\n"
                    f"🔗 <a href='{product['url']}'>Vedi su Amazon</a>\n\n"
                    "Come affiliato Amazon, guadagno un compenso per ogni acquisto idoneo."
                ),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce i pulsanti inline"""
        if not update.callback_query or not update.effective_user:
            return

        query = update.callback_query
        user_id = update.effective_user.id
        
        # Estrai l'azione e l'ASIN dal callback data
        action = query.data[:7]  # "remove_" o "refresh"
        asin = query.data[7:]

        if action == REMOVE_PRODUCT:
            # Rimuovi il prodotto
            db.remove_product(user_id, asin)
            await query.answer("Prodotto rimosso dal monitoraggio!")
            await query.message.edit_caption(
                caption="❌ Prodotto rimosso dal monitoraggio",
                reply_markup=None
            )

        elif action == REFRESH_PRODUCT:
            # Aggiorna le informazioni del prodotto
            product = await context.bot_data['price_tracker'].update_product_info(user_id, asin)
            
            if product:
                # Genera nuovo grafico
                chart = chart_generator.generate_price_chart(
                    product['price_history'],
                    product['target_price'],
                    product['title']
                )

                # Aggiorna il messaggio con le nuove informazioni
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🔄 Aggiorna",
                            callback_data=f"{REFRESH_PRODUCT}{asin}"
                        ),
                        InlineKeyboardButton(
                            "❌ Rimuovi",
                            callback_data=f"{REMOVE_PRODUCT}{asin}"
                        )
                    ]
                ]

                await query.message.edit_media(
                    media=chart,
                    caption=(
                        f"📦 {product['title']}\n\n"
                        f"💰 Prezzo attuale: €{product['current_price']:.2f}\n"
                        f"🎯 Prezzo target: €{product['target_price']:.2f}\n"
                        f"📉 Minimo storico: €{product['min_historic_price']:.2f}\n"
                        f"🔄 Ultimo controllo: {product['last_checked'].strftime('%d/%m/%Y %H:%M')}\n\n"
                        f"🔗 <a href='{product['url']}'>Vedi su Amazon</a>\n\n"
                        "Come affiliato Amazon, guadagno un compenso per ogni acquisto idoneo."
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await query.answer("Informazioni aggiornate!")
            else:
                await query.answer("❌ Errore nell'aggiornamento delle informazioni")

# Crea l'istanza del gestore del bot
bot_handler = BotHandler()

# Definisci gli handler per i comandi
def get_handlers():
    """Restituisce tutti gli handler del bot"""
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', bot_handler.add_product)],
        states={
            WAITING_FOR_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.process_url)
            ],
            WAITING_FOR_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.process_price)
            ]
        },
        fallbacks=[],
    )

    return [
        CommandHandler('start', bot_handler.start),
        CommandHandler('help', bot_handler.help),
        CommandHandler('list', bot_handler.list_products),
        CallbackQueryHandler(bot_handler.handle_button),
        conv_handler
    ]