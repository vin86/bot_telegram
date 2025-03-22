"""
Client per l'interazione con le API di Keepa.
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

from config.config import Config

class KeepaClient:
    def __init__(self):
        self.api_key = Config.KEEPA_API_KEY
        self.base_url = "https://api.keepa.com"
        self.domain = "1"  # 1 = amazon.it

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    def _convert_keepa_price(self, keepa_price: int) -> float:
        """Converte il prezzo dal formato Keepa (intero) a euro (float)"""
        return float(keepa_price / 100) if keepa_price != -1 else 0.0

    def _convert_keepa_time(self, keepa_time: int) -> datetime:
        """Converte il timestamp Keepa in datetime"""
        return datetime.fromtimestamp(keepa_time * 60)

    async def search_products(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Cerca prodotti su Amazon tramite Keepa.
        
        Args:
            keyword: La parola chiave da cercare
            
        Returns:
            Lista di prodotti trovati con i loro dettagli
        """
        if not self._session:
            raise RuntimeError("Client non inizializzato. Usa 'async with'")

        endpoint = "/query"  # Cambiato da /search a /query
        params = {
            "key": self.api_key,
            "domain": self.domain,
            "selection": {
                "title": keyword,
                "categoryId": None,  # Cerca in tutte le categorie
                "priceTypes": [0],  # 0 = Amazon price
                "deltaRange": [0, Config.PRICE_HISTORY_DAYS],  # Ultimi X giorni
                "deltaPercent": -20,  # Cerca prodotti con almeno 20% di sconto
                "deltaDropOnly": True,  # Solo riduzioni di prezzo
                "sortType": 2  # Ordina per sconto percentuale
            }
        }

        try:
            async with self._session.post(
                f"{self.base_url}{endpoint}",
                json=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("products", [])
                else:
                    error_text = await response.text()
                    raise Exception(f"Keepa API error: {error_text}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error during Keepa search: {str(e)}")

    async def get_product_details(self, asin: str) -> Dict[str, Any]:
        """
        Ottiene i dettagli di un prodotto specifico tramite ASIN.
        
        Args:
            asin: Amazon Standard Identification Number
            
        Returns:
            Dettagli del prodotto inclusa la storia dei prezzi
        """
        if not self._session:
            raise RuntimeError("Client non inizializzato. Usa 'async with'")

        endpoint = "/product"
        params = {
            "key": self.api_key,
            "domain": self.domain,
            "asin": asin,
            "offers": 1,  # Include le offerte
            "stats": Config.PRICE_HISTORY_DAYS  # Statistiche per gli ultimi X giorni
        }

        try:
            async with self._session.get(
                f"{self.base_url}{endpoint}",
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    products = data.get("products", [])
                    if products:
                        product = products[0]
                        return self._process_product_data(product)
                    raise Exception(f"Prodotto non trovato: {asin}")
                else:
                    error_text = await response.text()
                    raise Exception(f"Keepa API error: {error_text}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error during Keepa product lookup: {str(e)}")

    def _process_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa i dati grezzi del prodotto da Keepa.
        
        Args:
            product: Dati grezzi del prodotto da Keepa
            
        Returns:
            Dati del prodotto processati
        """
        # Estrai i prezzi dalla cronologia
        price_history = product.get("csv", [])
        if not price_history or len(price_history) < 1:
            return {}

        # Il primo array contiene i prezzi Amazon
        amazon_prices = price_history[0]
        valid_prices = [self._convert_keepa_price(p) for p in amazon_prices if p > 0]
        
        if not valid_prices:
            return {}

        current_price = valid_prices[0] if valid_prices else 0
        lowest_price = min(valid_prices) if valid_prices else 0
        highest_price = max(valid_prices) if valid_prices else 0

        return {
            "asin": product.get("asin", ""),
            "title": product.get("title", ""),
            "current_price": current_price,
            "lowest_price_30d": lowest_price,
            "highest_price_30d": highest_price,
            "image_url": f"https://images-amazon.com/images/P/{product.get('asin')}.jpg"
        }

    def calculate_discount_percentage(self, current_price: float, highest_price: float) -> float:
        """
        Calcola la percentuale di sconto.
        
        Args:
            current_price: Prezzo corrente
            highest_price: Prezzo più alto
            
        Returns:
            Percentuale di sconto
        """
        if highest_price <= 0 or current_price <= 0:
            return 0.0
        discount = ((highest_price - current_price) / highest_price) * 100
        return round(discount, 2)
