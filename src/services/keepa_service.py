import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import keepa
from config.config import KEEPA_API_KEY, MAX_REQUESTS_PER_MINUTE, CACHE_DURATION

logger = logging.getLogger(__name__)

class KeepaService:
    def __init__(self):
        self.api = keepa.Keepa(KEEPA_API_KEY)
        self.request_times: List[datetime] = []
        self.cache: Dict[str, tuple[dict, datetime]] = {}
        
    async def _check_rate_limit(self):
        """Gestisce il rate limiting delle richieste API"""
        now = datetime.utcnow()
        # Rimuove le richieste più vecchie di un minuto
        self.request_times = [t for t in self.request_times if now - t < timedelta(minutes=1)]
        
        if len(self.request_times) >= MAX_REQUESTS_PER_MINUTE:
            wait_time = 60 - (now - self.request_times[0]).seconds
            logger.info(f"Rate limit raggiunto. Attendo {wait_time} secondi")
            await asyncio.sleep(wait_time)
        
        self.request_times.append(now)

    def _get_from_cache(self, key: str) -> Optional[dict]:
        """Recupera i dati dalla cache se ancora validi"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.utcnow() - timestamp < timedelta(seconds=CACHE_DURATION):
                logger.debug(f"Cache hit per {key}")
                return data
            else:
                del self.cache[key]
        return None

    def _save_to_cache(self, key: str, data: dict):
        """Salva i dati nella cache"""
        self.cache[key] = (data, datetime.utcnow())

    async def search_products(self, keyword: str) -> List[dict]:
        """
        Cerca prodotti su Amazon tramite Keepa
        
        Args:
            keyword: La parola chiave da cercare
            
        Returns:
            Lista di prodotti trovati con i relativi dettagli
        """
        cache_key = f"search_{keyword}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        await self._check_rate_limit()
        
        try:
            # Esegue la ricerca tramite l'API Keepa
            products = self.api.search_products(
                keyword,
                domain='it',  # Dominio Amazon.it
                product_type='STANDARD'  # Solo prodotti standard
            )

            # Formatta i risultati
            formatted_products = []
            for product in products:
                formatted_product = {
                    'asin': product['asin'],
                    'title': product.get('title', 'Titolo non disponibile'),
                    'current_price': product.get('current_price', 0.0),
                    'image_url': product.get('imagesCSV', '').split(',')[0] if product.get('imagesCSV') else None,
                    'url': f"https://www.amazon.it/dp/{product['asin']}"
                }
                formatted_products.append(formatted_product)

            self._save_to_cache(cache_key, formatted_products)
            return formatted_products

        except Exception as e:
            logger.error(f"Errore durante la ricerca dei prodotti: {str(e)}")
            raise

    async def get_product_price_history(self, asin: str) -> dict:
        """
        Ottiene lo storico prezzi di un prodotto
        
        Args:
            asin: L'ASIN del prodotto Amazon
            
        Returns:
            Dizionario con lo storico prezzi e altre informazioni sul prodotto
        """
        cache_key = f"history_{asin}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        await self._check_rate_limit()
        
        try:
            # Ottiene i dati del prodotto tramite l'API Keepa
            product = self.api.query(asin)[0]
            
            price_history = {
                'asin': asin,
                'title': product.get('title', 'Titolo non disponibile'),
                'current_price': product.get('current_price', 0.0),
                'lowest_price': product.get('lowest_price', 0.0),
                'highest_price': product.get('highest_price', 0.0),
                'price_history': product.get('price_history', []),
                'image_url': product.get('imagesCSV', '').split(',')[0] if product.get('imagesCSV') else None,
                'url': f"https://www.amazon.it/dp/{asin}"
            }

            self._save_to_cache(cache_key, price_history)
            return price_history

        except Exception as e:
            logger.error(f"Errore durante il recupero dello storico prezzi: {str(e)}")
            raise

    async def get_current_price(self, asin: str) -> float:
        """
        Ottiene il prezzo corrente di un prodotto
        
        Args:
            asin: L'ASIN del prodotto Amazon
            
        Returns:
            Prezzo corrente del prodotto
        """
        try:
            product_data = await self.get_product_price_history(asin)
            return product_data['current_price']
        except Exception as e:
            logger.error(f"Errore durante il recupero del prezzo corrente: {str(e)}")
            raise