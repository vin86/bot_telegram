"""
Configurazione principale del bot Amazon Deals.
Gestisce le variabili d'ambiente e le impostazioni generali.
"""
import os
from dotenv import load_dotenv
from typing import Dict, List

# Carica le variabili d'ambiente dal file .env
load_dotenv()

class Config:
    # Credenziali
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    KEEPA_API_KEY = os.getenv('KEEPA_API_KEY')
    TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
    AMAZON_REFERRAL_CODE = os.getenv('AMAZON_REFERRAL_CODE')

    # Configurazioni Amazon
    AMAZON_DOMAIN = "amazon.it"
    AMAZON_BASE_URL = f"https://www.{AMAZON_DOMAIN}/dp/"

    # Configurazioni Keepa
    KEEPA_UPDATE_INTERVAL = 30  # minuti
    PRICE_HISTORY_DAYS = 30
    
    # Configurazioni monitoraggio
    MINIMUM_DISCOUNT_PERCENT = 20  # Sconto minimo per notifica
    CHECK_INTERVAL = 300  # Secondi tra i controlli (5 minuti)
    MAX_RETRIES = 3  # Numero massimo di tentativi per richieste fallite
    
    # Cache e Database
    DATABASE_URL = "sqlite:///deals.db"
    CACHE_DURATION = 3600  # Durata della cache in secondi (1 ora)

    @staticmethod
    def validate_config() -> bool:
        """
        Valida che tutte le configurazioni necessarie siano presenti.
        """
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'KEEPA_API_KEY',
            'TELEGRAM_CHANNEL_ID',
            'AMAZON_REFERRAL_CODE'
        ]
        
        missing_vars = [var for var in required_vars if not getattr(Config, var)]
        
        if missing_vars:
            print(f"Errore: Variabili d'ambiente mancanti: {', '.join(missing_vars)}")
            print("Crea un file .env con le variabili richieste")
            return False
        return True

    @staticmethod
    def get_product_url(asin: str) -> str:
        """
        Genera l'URL del prodotto Amazon con il referral code.
        """
        base_url = f"{Config.AMAZON_BASE_URL}{asin}"
        if Config.AMAZON_REFERRAL_CODE:
            return f"{base_url}?tag={Config.AMAZON_REFERRAL_CODE}"
        return base_url