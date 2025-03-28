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
        self._clean_cache()  # Pulisce la cache all'avvio
        
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

    def _clean_cache(self):
        """Rimuove le entry scadute dalla cache"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if now - timestamp >= timedelta(seconds=CACHE_DURATION)
        ]
        for key in expired_keys:
            del self.cache[key]
        if expired_keys:
            logger.debug(f"Rimosse {len(expired_keys)} entry scadute dalla cache")

    def _get_from_cache(self, key: str) -> Optional[dict]:
        """Recupera i dati dalla cache se ancora validi"""
        self._clean_cache()  # Pulisce la cache prima di ogni accesso
        if key in self.cache:
            data, timestamp = self.cache[key]
            logger.debug(f"Cache hit per {key}")
            return data
        return None

    def _save_to_cache(self, key: str, data: dict):
        """Salva i dati nella cache"""
        self.cache[key] = (data, datetime.utcnow())

    def _extract_price_history(self, product: dict) -> tuple[float, float, float, datetime]:
        """
        Estrae lo storico prezzi completo
        
        Returns:
            Tupla con (prezzo corrente, prezzo minimo, prezzo massimo, timestamp)
        """
        try:
            asin = product.get('asin')
            logger.debug(f"Estrazione prezzi per ASIN: {asin}")

            current_price = 0.0
            min_price = float('inf')
            max_price = 0.0
            now = datetime.utcnow()

            if 'stats' in product and product['stats']:
                stats = product['stats']
                
                # Estrai il prezzo corrente
                if 'current' in stats and stats['current'] and len(stats['current']) > 0:
                    current_price = float(stats['current'][0]) / 100 if stats['current'][0] > 0 else 0.0
                
                # Estrai min/max dagli ultimi 90 giorni se disponibili
                if 'price90days' in stats:
                    prices = [p for p in stats['price90days'] if p and p > 0]
                    if prices:
                        min_price = min(prices) / 100
                        max_price = max(prices) / 100

            # Se non abbiamo trovato prezzi storici, usa il prezzo corrente
            if min_price == float('inf'):
                min_price = current_price
            if max_price == 0.0:
                max_price = current_price

            logger.debug(
                f"Prezzi estratti per {asin}: "
                f"corrente={current_price}€, "
                f"min={min_price}€, "
                f"max={max_price}€"
            )
            
            return current_price, min_price, max_price, now
            
        except Exception as e:
            logger.error(f"Errore nell'estrazione dei prezzi: {str(e)}")
            return 0.0, 0.0, 0.0, datetime.utcnow()

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
            products_data = self.api.query(asins, domain='IT', stat=True, update=1)
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
                    # Estrae prezzi e timestamp
                    current_price, min_price, max_price, timestamp = self._extract_price_history(product)
                    
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
                        'lowest_price': min_price,
                        'highest_price': max_price,
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
            products = self.api.query(asin, domain='IT', stat=True, update=1)
            if not products or not isinstance(products, list) or len(products) == 0:
                raise ValueError(f"Prodotto non trovato: {asin}")
            
            product = products[0]
            if not isinstance(product, dict):
                raise ValueError(f"Dati prodotto non validi: {asin}")
            
            logger.debug(f"Dati prodotto grezzi: {product}")
            
            # Estrae prezzi e timestamp
            current_price, min_price, max_price, last_update = self._extract_price_history(product)
            if current_price == 0.0:
                raise ValueError(f"Prezzo non disponibile per: {asin}")
            
            # Prepara lo storico prezzi
            price_history = {
                'asin': asin,
                'title': product.get('title', 'Titolo non disponibile'),
                'current_price': current_price,
                'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S'),
                'lowest_price': min_price,
                'highest_price': max_price,
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
        Ottiene il prezzo corrente di un prodotto
        
        Args:
            asin: L'ASIN del prodotto Amazon
            
        Returns:
            Tupla con (prezzo corrente, timestamp)
        
        Raises:
            ValueError: Se il prodotto non è trovato o i dati non sono validi
        """
        try:
            self._check_rate_limit()
            
            # Prima controlla la cache
            cache_key = f"price_{asin}"
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                return cached_data['price'], cached_data['timestamp']
            
            products = self.api.query(asin, domain='IT', stat=True, update=1)
            if not products or not isinstance(products, list) or len(products) == 0:
                raise ValueError(f"Prodotto non trovato: {asin}")
            
            product = products[0]
            if not isinstance(product, dict):
                raise ValueError(f"Dati prodotto non validi: {asin}")
            
            current_price, _, _, timestamp = self._extract_price_history(product)
            if current_price == 0.0:
                raise ValueError(f"Prezzo non disponibile per: {asin}")
            
            # Salva in cache
            self._save_to_cache(cache_key, {
                'price': current_price,
                'timestamp': timestamp
            })
            
            logger.debug(f"Prezzo estratto per {asin}: {current_price}€ al {timestamp}")
            return current_price, timestamp
            
        except Exception as e:
            logger.error(f"Errore durante il recupero del prezzo corrente: {str(e)}")
            raise
