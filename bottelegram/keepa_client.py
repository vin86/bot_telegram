from typing import Dict, Optional, List
import keepa
import re
from datetime import datetime, timedelta
import logging
from config import KEEPA_API_KEY, AMAZON_URL_PATTERN, AMAZON_AFFILIATE_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KeepaClient:
    def __init__(self):
        self.api = keepa.Keepa(KEEPA_API_KEY)

    def add_affiliate_tag(self, url: str) -> str:
        """Aggiunge il tag di affiliazione al link Amazon."""
        if "?" in url:
            return f"{url}&tag={AMAZON_AFFILIATE_ID}"
        return f"{url}?tag={AMAZON_AFFILIATE_ID}"

    def extract_asin(self, url: str) -> Optional[str]:
        """Estrae l'ASIN da un URL Amazon."""
        match = re.search(AMAZON_URL_PATTERN, url)
        if match:
            return match.group(1)
        return None

    def get_product_info(self, url: str) -> Optional[Dict]:
        """
        Recupera le informazioni del prodotto da un URL Amazon.
        Restituisce un dizionario con titolo, ASIN, prezzo corrente e storico prezzi.
        """
        try:
            asin = self.extract_asin(url)
            if not asin:
                logger.error(f"ASIN non valido per l'URL: {url}")
                return None

            # Recupera i dati del prodotto da Keepa
            products = self.api.query(asin)
            if not products:
                logger.error(f"Nessun prodotto trovato per ASIN: {asin}")
                return None

            product = products[0]
            
            # Recupera lo storico prezzi degli ultimi 30 giorni
            current_time = datetime.utcnow()
            month_ago = current_time - timedelta(days=30)
            
            price_history = self._process_price_history(product, month_ago)
            current_price = self._get_current_price(product)
            min_price = self._get_min_price(price_history)
            all_time_min = self._get_all_time_min_price(product)

            # Aggiungi il tag di affiliazione al link
            affiliate_url = self.add_affiliate_tag(url)
            
            return {
                "asin": asin,
                "url": affiliate_url,
                "title": product['title'],
                "image_url": product.get('imagesCSV', '').split(',')[0],
                "current_price": current_price,
                "min_historic_price": min_price,
                "all_time_min_price": all_time_min,
                "price_history": price_history
            }

        except Exception as e:
            logger.error(f"Errore nel recupero delle informazioni del prodotto: {str(e)}")
            return None

    def _process_price_history(self, product: Dict, start_date: datetime) -> List[Dict]:
        """Processa lo storico prezzi del prodotto."""
        price_history = []
        
        # Keepa fornisce i prezzi in intervalli di 5 minuti
        timestamps = product.get('timestamp', [])
        prices = product.get('data', {}).get('AMAZON', [])

        if not timestamps or not prices:
            return price_history

        start_timestamp = int(start_date.timestamp())

        for timestamp, price in zip(timestamps, prices):
            if timestamp >= start_timestamp:
                if price > 0:  # Keepa usa prezzi negativi per prodotti non disponibili
                    actual_price = price / 100  # Keepa fornisce i prezzi in centesimi
                    price_history.append({
                        "timestamp": datetime.fromtimestamp(timestamp),
                        "price": actual_price
                    })

        return price_history

    def _get_current_price(self, product: Dict) -> Optional[float]:
        """Recupera il prezzo corrente del prodotto."""
        try:
            prices = product.get('data', {}).get('AMAZON', [])
            if prices:
                current_price = prices[-1]
                if current_price > 0:
                    return current_price / 100
            return None
        except Exception:
            return None

    def _get_all_time_min_price(self, product: Dict) -> Optional[float]:
        """Calcola il prezzo più basso di sempre del prodotto."""
        try:
            prices = product.get('data', {}).get('AMAZON', [])
            if not prices:
                return None

            # Filtra i prezzi validi (> 0) e converte in euro
            valid_prices = [price/100 for price in prices if price > 0]
            return min(valid_prices) if valid_prices else None
        except Exception:
            return None

    def _get_min_price(self, price_history: List[Dict]) -> Optional[float]:
        """Calcola il prezzo minimo nel periodo di monitoraggio."""
        if not price_history:
            return None
        
        prices = [entry['price'] for entry in price_history]
        return min(prices) if prices else None

    def check_price_drops(self, products: List[Dict]) -> List[Dict]:
        """
        Controlla quali prodotti hanno raggiunto il prezzo target.
        Restituisce una lista di prodotti con prezzo <= target_price.
        """
        price_drops = []
        
        for product in products:
            try:
                current_info = self.api.query(product['asin'])
                if not current_info:
                    continue

                current_price = self._get_current_price(current_info[0])
                if current_price and current_price <= product['target_price']:
                    price_drops.append({
                        **product,
                        'current_price': current_price
                    })
                    
            except Exception as e:
                logger.error(f"Errore nel controllo del prezzo per {product['asin']}: {str(e)}")
                continue

        return price_drops

# Istanza globale del client Keepa
keepa_client = KeepaClient()