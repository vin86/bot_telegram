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
            # Configura i parametri di ricerca
            finder_params = {
                'title': keyword,
                'category': 0,  # Tutte le categorie
                'priceTypes': ['AMAZON'],  # Solo prezzi Amazon
                'deltaPriceInPercent': 20,  # Minimo 20% di sconto
                'deltaRange': Config.PRICE_HISTORY_DAYS,  # Ultimi X giorni
                'deltaAtLeast': 1000,  # Almeno 10€ di sconto
                'deltaLastSeen': 48,  # Visto nelle ultime 48 ore
                'sortType': 'DELTA_PERCENT_DROPDOWN',  # Ordina per sconto percentuale
                'itemsPerPage': 10  # Limita i risultati
            }

            # Esegui la ricerca in modo asincrono
            products = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self.api.product_finder(**finder_params)
            )

            if not products:
                return []

            # Ottieni i dettagli completi per i prodotti trovati
            asins = [p.get('asin') for p in products if p.get('asin')]
            if not asins:
                return []

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
            # Configura i parametri per la query dei prodotti
            product_params = {
                'offers': True,  # Include le offerte
                'update': None,  # Non forzare l'aggiornamento
                'rating': True,  # Include le valutazioni
                'stats': Config.PRICE_HISTORY_DAYS,  # Statistiche per gli ultimi X giorni
                'tracking': Config.PRICE_HISTORY_DAYS  # Tracking per gli ultimi X giorni
            }

            # Ottieni i dettagli in un thread separato
            products = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self.api.query(asins, **product_params)
            )

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
            # Estrai i dati principali
            stats = product.get('stats', {})
            
            # Ottieni i prezzi
            current = stats.get('current', {})
            avg30 = stats.get('avg30', {})
            
            current_price = current.get('price', 0.0)
            lowest_price = avg30.get('min', 0.0)
            highest_price = avg30.get('max', 0.0)

            # Calcola lo sconto
            discount = self.calculate_discount_percentage(current_price, highest_price)

            return {
                "asin": product.get('asin', ''),
                "title": product.get('title', ''),
                "current_price": current_price,
                "lowest_price_30d": lowest_price,
                "highest_price_30d": highest_price,
                "discount_percent": discount,
                "rating": product.get('rating', {}).get('avg', 0.0),
                "rating_count": product.get('rating', {}).get('count', 0),
                "category": product.get('categoryTree', [])[-1] if product.get('categoryTree') else None,
                "image_url": product.get('imagesCSV', '').split(',')[0] if product.get('imagesCSV') else None,
                "last_update": datetime.fromtimestamp(product.get('lastUpdate', 0)),
                "url": f"https://www.amazon.it/dp/{product.get('asin')}"
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
