"""
Client per l'interazione con le API di Keepa utilizzando la libreria ufficiale.
Documentazione: https://pypi.org/project/keepa/
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import keepa
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from config.config import Config

logger = logging.getLogger(__name__)

class KeepaClient:
    def __init__(self):
        self.api = keepa.Keepa(Config.KEEPA_API_KEY)
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._executor.shutdown(wait=True)

    def _safe_float_conversion(self, value: Any) -> float:
        """Converte in modo sicuro un valore a float"""
        try:
            if hasattr(value, 'item'):  # Per gestire i tipi numpy
                value = value.item()
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _convert_keepa_price(self, price: Any) -> float:
        """Converte il prezzo da centesimi di euro a euro"""
        price_float = self._safe_float_conversion(price)
        if price_float <= 0:
            return 0.0
        return price_float / 100.0

    async def search_products(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Cerca prodotti su Amazon tramite Keepa.
        
        Args:
            keyword: La parola chiave da cercare
            
        Returns:
            Lista di prodotti trovati con i loro dettagli
        """
        try:
            # Configura i parametri di ricerca come un dizionario
            product_parms = {
                'author': keyword  # Usa author invece di title come suggerito nella documentazione
            }

            # Esegui la ricerca in modo asincrono
            products = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self.api.product_finder(product_parms)
            )

            if not products:
                return []

            # Filtra gli ASIN validi
            asins = [p for p in products if isinstance(p, str)][:10]
            if not asins:
                return []

            # Ottieni i dettagli completi per i prodotti trovati
            return await self.get_products_details(asins)

        except Exception as e:
            logger.error(f"Errore durante la ricerca Keepa: {str(e)}")
            return []

    async def get_products_details(self, asins: List[str]) -> List[Dict[str, Any]]:
        """
        Ottiene i dettagli di più prodotti tramite i loro ASIN.
        
        Args:
            asins: Lista di ASIN Amazon
            
        Returns:
            Lista di dettagli dei prodotti
        """
        try:
            # Ottieni i dettagli in un thread separato
            products = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self.api.query(asins)
            )

            # Processa solo i prodotti validi
            processed_products = []
            for product in products:
                if product and isinstance(product, dict):
                    try:
                        processed = self._process_product_data(product)
                        if processed:
                            processed_products.append(processed)
                    except Exception as e:
                        logger.error(f"Errore nel processing del prodotto: {str(e)}")
                        continue

            return processed_products

        except Exception as e:
            logger.error(f"Errore durante il recupero dei dettagli prodotto: {str(e)}")
            return []

    def _process_product_data(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa i dati grezzi del prodotto da Keepa.
        
        Args:
            product: Dati grezzi del prodotto da Keepa
            
        Returns:
            Dati del prodotto processati
        """
        try:
            # Estrai i prezzi
            csv = product.get('csv', [])
            if not csv or len(csv) < 1:
                return None

            # I prezzi Amazon sono nel primo array
            amazon_prices = csv[0]
            if not amazon_prices:
                return None

            # Converti i prezzi da centesimi a euro e filtra i valori validi
            valid_prices = []
            for price in amazon_prices:
                converted_price = self._convert_keepa_price(price)
                if converted_price > 0:
                    valid_prices.append(converted_price)

            if not valid_prices:
                return None

            current_price = valid_prices[-1]  # Ultimo prezzo disponibile
            lowest_price = min(valid_prices)
            highest_price = max(valid_prices)
            
            # Calcola lo sconto
            discount = self.calculate_discount_percentage(current_price, highest_price)

            return {
                "asin": str(product.get('asin', '')),
                "title": str(product.get('title', '')),
                "current_price": current_price,
                "lowest_price_30d": lowest_price,
                "highest_price_30d": highest_price,
                "discount_percent": discount,
                "url": f"https://www.amazon.it/dp/{product.get('asin')}",
                "image_url": f"https://images-amazon.com/images/P/{product.get('asin')}.jpg"
            }

        except Exception as e:
            logger.error(f"Errore nel processing dei dati del prodotto: {str(e)}")
            return None

    def calculate_discount_percentage(self, current_price: float, highest_price: float) -> float:
        """
        Calcola la percentuale di sconto.
        
        Args:
            current_price: Prezzo corrente
            highest_price: Prezzo più alto
            
        Returns:
            Percentuale di sconto
        """
        try:
            if highest_price <= 0 or current_price <= 0:
                return 0.0
            discount = ((highest_price - current_price) / highest_price) * 100
            return round(discount, 2)
        except:
            return 0.0

    async def get_product_details(self, asin: str) -> Optional[Dict[str, Any]]:
        """
        Ottiene i dettagli di un singolo prodotto tramite ASIN.
        
        Args:
            asin: Amazon Standard Identification Number
            
        Returns:
            Dettagli del prodotto inclusa la storia dei prezzi
        """
        products = await self.get_products_details([asin])
        return products[0] if products else None
