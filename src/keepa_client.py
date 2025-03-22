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
import json
import numpy as np

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

    def _convert_keepa_price(self, price: Any) -> float:
        """Converte il prezzo da centesimi di euro a euro"""
        try:
            # Se è un oggetto con metodo item(), usalo
            if hasattr(price, 'item'):
                price = price.item()

            # Controllo se è un tipo NumPy
            if hasattr(np, 'ndarray') and isinstance(price, np.ndarray):
                price = float(price)
            elif hasattr(np, 'number') and isinstance(price, np.number):
                price = float(price)
            elif isinstance(price, (int, float)):
                price = float(price)
            else:
                raise TypeError(f"Tipo non supportato: {type(price)}")
            
            if price <= 0:
                return 0.0
            return price / 100.0
        except (TypeError, ValueError) as e:
            logger.debug(f"Errore nella conversione del prezzo: {price}, tipo: {type(price)}, errore: {str(e)}")
            return 0.0

    async def search_products(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Cerca prodotti su Amazon tramite Keepa.
        
        Args:
            keyword: La parola chiave da cercare
            
        Returns:
            Lista di prodotti trovati con i loro dettagli
        """
        try:
            # Debug del tipo di dati ricevuti
            logger.info(f"Ricerca prodotti per keyword: {keyword}")
            
            product_parms = {
                'author': keyword
            }

            products = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self.api.product_finder(product_parms)
            )

            # Debug dei risultati
            logger.debug(f"Risultati ricerca: {json.dumps(products, default=str)}")

            if not products:
                return []

            asins = [p for p in products if isinstance(p, str)][:10]
            if not asins:
                return []

            logger.info(f"ASIN trovati: {asins}")
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
            # Debug della query
            logger.info(f"Richiesta dettagli per ASIN: {asins}")

            products = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self.api.query(asins)
            )

            # Debug dei risultati
            for product in products:
                if product:
                    logger.debug(f"Dettagli prodotto grezzo: {json.dumps(product, default=str)}")

            processed_products = []
            for product in products:
                if product and isinstance(product, dict):
                    try:
                        processed = self._process_product_data(product)
                        if processed:
                            processed_products.append(processed)
                    except Exception as e:
                        logger.error(f"Errore nel processing del prodotto: {str(e)}, tipo dati: {type(product)}")
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
            # Debug dei dati del prodotto
            logger.debug(f"Processing prodotto: {product.get('asin')}")

            csv = product.get('csv', [])
            if not csv or len(csv) < 1:
                logger.debug("Nessun dato CSV trovato")
                return None

            amazon_prices = csv[0]
            if not amazon_prices:
                logger.debug("Nessun prezzo Amazon trovato")
                return None

            # Debug dei prezzi grezzi
            logger.debug(f"Prezzi grezzi: {amazon_prices}")

            valid_prices = []
            for price in amazon_prices:
                logger.debug(f"Elaborazione prezzo: {price}, tipo: {type(price)}")
                converted_price = self._convert_keepa_price(price)
                if converted_price > 0:
                    valid_prices.append(converted_price)

            if not valid_prices:
                logger.debug("Nessun prezzo valido trovato")
                return None

            current_price = valid_prices[-1]
            lowest_price = min(valid_prices)
            highest_price = max(valid_prices)
            discount = self.calculate_discount_percentage(current_price, highest_price)

            result = {
                "asin": str(product.get('asin', '')),
                "title": str(product.get('title', '')),
                "current_price": current_price,
                "lowest_price_30d": lowest_price,
                "highest_price_30d": highest_price,
                "discount_percent": discount,
                "url": f"https://www.amazon.it/dp/{product.get('asin')}",
                "image_url": f"https://images-amazon.com/images/P/{product.get('asin')}.jpg"
            }

            logger.debug(f"Dati processati: {json.dumps(result, default=str)}")
            return result

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
