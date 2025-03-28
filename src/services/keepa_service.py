import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time
import keepa
from config.config import KEEPA_API_KEY, MAX_REQUESTS_PER_MINUTE, CACHE_DURATION

logger = logging.getLogger(__name__)

class KeepaService:
    def __init__(self):
        if not KEEPA_API_KEY:
            raise ValueError("Keepa API key non configurata")
            
        self.api = keepa.Keepa(KEEPA_API_KEY)
        self.request_times: List[datetime] = []
        self.cache: Dict[str, tuple[dict, datetime]] = {}
        
    def _check_rate_limit(self):
        """Gestisce il rate limiting delle richieste API"""
        now = datetime.utcnow()
        # Rimuove le richieste più vecchie di un minuto
        self.request_times = [t for t in self.request_times if now - t < timedelta(minutes=1)]
        
        if len(self.request_times) >= MAX_REQUESTS_PER_MINUTE:
            wait_time = 60 - (now - self.request_times[0]).seconds
            logger.info(f"Rate limit raggiunto. Attendo {wait_time} secondi")
            time.sleep(wait_time)
        
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

    def _extract_price(self, product: dict) -> tuple[float, datetime]:
        """
        Estrae il prezzo più recente da un prodotto
        
        Returns:
            Tupla con (prezzo, timestamp)
        """
        try:
            logger.debug(f"Estrazione prezzo per ASIN: {product.get('asin')}")
            
            # Prova prima con stats perché contiene il prezzo più recente
            if 'stats' in product and isinstance(product['stats'], dict):
                logger.debug(f"Stats disponibile: {product['stats'].keys()}")
                stats = product['stats']
                if 'current' in stats and stats['current'] and stats['current'][0] > 0:
                    price = float(stats['current'][0]) / 100
                    logger.debug(f"Prezzo corrente trovato in stats: {price}")
                    return price, datetime.utcnow()

            # Poi prova con il campo csv che contiene i dati grezzi
            if 'csv' in product and product['csv']:
                logger.debug(f"CSV disponibile: {product['csv']}")
                # Il primo array (indice 0) contiene i prezzi Amazon
                amazon_prices = product['csv'][0] if len(product['csv']) > 0 else []
                amazon_times = product['csv'][1] if len(product['csv']) > 1 else []  # Array dei timestamp
                
                if amazon_prices and amazon_times:
                    # Cerca l'ultimo prezzo valido
                    for i, price in enumerate(reversed(amazon_prices)):
                        if price is not None and price > 0:
                            price = float(price) / 100  # Converti centesimi in euro
                            timestamp = datetime.fromtimestamp(amazon_times[-(i+1)])
                            logger.debug(f"Prezzo trovato in csv[0]: {price} al {timestamp}")
                            return price, timestamp

            # Se non trova niente in csv, prova a ottenere il prezzo dai dati Amazon
            if 'data' in product and isinstance(product['data'], dict):
                logger.debug(f"Data disponibile: {product['data'].keys()}")
                for key in ['AMAZON', 'AMAZON_NEW', 'MARKET_NEW']:
                    price_data = product['data'].get(key, [])
                    if price_data:
                        for price in reversed(price_data):
                            if price is not None and price > 0:
                                price = float(price) / 100
                                logger.debug(f"Prezzo trovato in data/{key}: {price}")
                                return price, datetime.utcnow()

            logger.warning(f"Nessun prezzo valido trovato per ASIN {product.get('asin')}")
            return 0.0, datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Errore nell'estrazione del prezzo: {str(e)}")
            return 0.0

    def search_products(self, keyword: str) -> List[dict]:
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

        self._check_rate_limit()
        
        try:
            # Controlla se l'input è un ASIN (10 caratteri alfanumerici)
            is_asin = len(keyword) == 10 and keyword.isalnum()
            
            # Ottiene gli ASIN dei prodotti
            if is_asin:
                asins = [keyword]
            else:
                # Cerca per titolo
                search_params = {
                    'title': keyword,
                    'productType': 0  # 0 = STANDARD product type in Keepa API
                }
                asins = self.api.product_finder(search_params, domain='IT')
            
            logger.debug(f"ASINs trovati: {asins}")
            
            if not asins:
                logger.info(f"Nessun prodotto trovato per: {keyword}")
                return []
            
            # Prendiamo solo i primi 5 risultati
            asins = asins[:5]
            
            # Ottiene i dettagli dei prodotti
            products_data = self.api.query(asins)
            logger.debug(f"Risposta query prodotti: {products_data}")
            
            if not products_data:
                logger.warning("Nessun dato prodotto restituito dalla query")
                return []
            
            # Formatta i risultati
            formatted_products = []
            for product in products_data:
                if not isinstance(product, dict):
                    logger.warning(f"Prodotto non valido: {product}")
                    continue
                    
                try:
                    # Estrae il prezzo e il timestamp
                    current_price, timestamp = self._extract_price(product)
                    
                    # Verifica che l'ASIN sia presente
                    asin = product.get('asin')
                    if not asin:
                        logger.warning("Prodotto senza ASIN, skip")
                        continue
                        
                    # Formatta il prodotto con controlli null-safe
                    formatted_product = {
                        'asin': asin,
                        'title': product.get('title', 'Titolo non disponibile'),
                        'current_price': current_price,
                        'image_url': (product.get('imagesCSV', '').split(',')[0]
                                    if product.get('imagesCSV') else None),
                        'url': f"https://www.amazon.it/dp/{asin}"
                    }
                    
                    # Validazione completa del prodotto
                    is_valid = (
                        formatted_product['title'] != 'Titolo non disponibile' and
                        current_price > 0 and
                        formatted_product['asin']
                    )
                    
                    if is_valid:
                        logger.debug(f"Prodotto formattato: {formatted_product}")
                        formatted_products.append(formatted_product)
                    else:
                        logger.warning(
                            f"Prodotto scartato - Validazione fallita: "
                            f"ASIN={asin}, "
                            f"Title={formatted_product['title']}, "
                            f"Price={current_price}"
                        )
                    
                except Exception as e:
                    logger.warning(f"Errore nel parsing del prodotto {product.get('asin')}: {str(e)}")
                    continue
            
            self._save_to_cache(cache_key, formatted_products)
            return formatted_products
            
        except Exception as e:
            logger.error(f"Errore durante la ricerca dei prodotti: {str(e)}")
            raise

    def get_product_price_history(self, asin: str) -> dict:
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

        self._check_rate_limit()
        
        try:
            # Ottiene i dati del prodotto forzando l'aggiornamento
            products = self.api.query(asin, offers=1, update=1)
            if not products or not isinstance(products, list) or len(products) == 0:
                raise ValueError(f"Prodotto non trovato: {asin}")
            
            product = products[0]
            if not isinstance(product, dict):
                raise ValueError(f"Dati prodotto non validi: {asin}")
            
            logger.debug(f"Dati prodotto grezzi: {product}")
            
            # Estrae il prezzo corrente e il timestamp
            current_price, last_update = self._extract_price(product)
            if current_price == 0.0:
                raise ValueError(f"Prezzo non disponibile per: {asin}")
            
            # Prepara lo storico prezzi
            price_history = {
                'asin': asin,
                'title': product.get('title', 'Titolo non disponibile'),
                'current_price': current_price,
                'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S'),
                'lowest_price': current_price,  # Per ora usiamo il prezzo corrente
                'highest_price': current_price, # Per ora usiamo il prezzo corrente
                'image_url': (product.get('imagesCSV', '').split(',')[0]
                            if product.get('imagesCSV') else None),
                'url': f"https://www.amazon.it/dp/{asin}"
            }
            
            logger.debug(f"Storico prezzi formattato: {price_history}")
            self._save_to_cache(cache_key, price_history)
            return price_history
            
        except Exception as e:
            logger.error(f"Errore durante il recupero dello storico prezzi: {str(e)}")
            raise

    def get_current_price(self, asin: str) -> tuple[float, datetime]:
        """
        Ottiene il prezzo corrente di un prodotto e il timestamp dell'ultimo aggiornamento
        
        Args:
            asin: L'ASIN del prodotto Amazon
            
        Returns:
            Tupla con (prezzo corrente, timestamp ultimo aggiornamento)
        """
        try:
            self._check_rate_limit()
            products = self.api.query(asin, offers=1, update=1)
            if not products or not isinstance(products, list) or len(products) == 0:
                raise ValueError(f"Prodotto non trovato: {asin}")
            
            product = products[0]
            if not isinstance(product, dict):
                raise ValueError(f"Dati prodotto non validi: {asin}")
            
            price, timestamp = self._extract_price(product)
            logger.debug(f"Prezzo estratto per {asin}: {price}€ al {timestamp}")
            return price, timestamp
            
        except Exception as e:
            logger.error(f"Errore durante il recupero del prezzo corrente: {str(e)}")
            raise