"""
Client per l'interazione con le API di Keepa utilizzando la libreria ufficiale.
Documentazione: https://pypi.org/project/keepa/
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import keepa
import asyncio
from concurrent.futures import ThreadPoolExecutor

from config.config import Config

class KeepaClient:
    def __init__(self):
        self.api = keepa.Keepa(Config.KEEPA_API_KEY)
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._executor.shutdown(wait=True)

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
                'title': keyword
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
            raise Exception(f"Errore durante la ricerca Keepa: {str(e)}")

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
            return [self._process_product_data(p) for p in products if p]

        except Exception as e:
            raise Exception(f"Errore durante il recupero dei dettagli prodotto: {str(e)}")

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

    def _process_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa i dati grezzi del prodotto da Keepa.
        
        Args:
            product: Dati grezzi del prodotto da Keepa
            
        Returns:
            Dati del prodotto processati
        """
        try:
            # Estrai lo storico dei prezzi
            price_history = product.get('data', {}).get('AMAZON', [])
            
            # Calcola i prezzi rilevanti
            current_price = 0
            prices_30d = []
            
            if price_history:
                # Converti i prezzi da keepa (centesimi) a euro
                valid_prices = [p/100 for p in price_history if p > 0]
                if valid_prices:
                    current_price = valid_prices[-1]  # Ultimo prezzo valido
                    prices_30d = valid_prices[-30:]  # Ultimi 30 prezzi

            # Calcola il prezzo più basso e più alto degli ultimi 30 giorni
            lowest_price = min(prices_30d) if prices_30d else 0
            highest_price = max(prices_30d) if prices_30d else 0
            
            # Calcola lo sconto
            discount = self.calculate_discount_percentage(current_price, highest_price)

            return {
                "asin": product.get('asin', ''),
                "title": product.get('title', ''),
                "current_price": current_price,
                "lowest_price_30d": lowest_price,
                "highest_price_30d": highest_price,
                "discount_percent": discount,
                "rating": product.get('stats', {}).get('rating', 0.0),
                "rating_count": product.get('stats', {}).get('count', 0),
                "url": f"https://www.amazon.it/dp/{product.get('asin')}",
                "image_url": f"https://images-amazon.com/images/P/{product.get('asin')}.jpg"
            }

        except Exception as e:
            raise Exception(f"Errore durante il processing dei dati prodotto: {str(e)}")

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
