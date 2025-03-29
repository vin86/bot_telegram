import logging
import time
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.pool import Pool
from collections import defaultdict

from src.database.models import Product, PriceHistory
from src.services.keepa_service import KeepaService
from config.config import (
    DATABASE_URL, 
    CHECK_INTERVAL,
    PRICE_HISTORY_RETENTION_DAYS,
    MIN_PRICE_CHANGE_PERCENT,
    BATCH_SIZE
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # secondi

class MonitorService:
    def __init__(self, notification_service, keepa_service: KeepaService):
        """
        Inizializza il servizio di monitoraggio
        
        Args:
            notification_service: Istanza del servizio di notifica
            keepa_service: Istanza del servizio Keepa
        """
        self.keepa_service = keepa_service
        self.notification_service = notification_service
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.is_running = False
        self.monitoring_task = None
        self.price_trends: Dict[str, List[float]] = defaultdict(list)

    def _create_engine(self):
        """Crea l'engine del database con configurazione ottimizzata"""
        return create_engine(
            DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_pre_ping=True,
            pool_recycle=3600
        )

    @staticmethod
    def _retry_on_db_error(func):
        """Decorator per gestire i retry sugli errori del database"""
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < MAX_RETRIES:
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    retries += 1
                    if retries == MAX_RETRIES:
                        logger.error(f"Errore database dopo {MAX_RETRIES} tentativi: {str(e)}")
                        raise
                    logger.warning(f"Errore connessione DB, tentativo {retries}/{MAX_RETRIES}: {str(e)}")
                    time.sleep(RETRY_DELAY)
        return wrapper

    def get_db(self) -> Session:
        """Crea una nuova sessione del database con gestione errori"""
        try:
            db = self.SessionLocal()
            db.execute(text("SELECT 1"))
            return db
        except SQLAlchemyError as e:
            logger.error(f"Errore creazione sessione DB: {str(e)}")
            raise

    def _cleanup_old_history(self, db: Session):
        """Rimuove i dati storici più vecchi di PRICE_HISTORY_RETENTION_DAYS"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=PRICE_HISTORY_RETENTION_DAYS)
            db.query(PriceHistory).filter(PriceHistory.check_date < cutoff_date).delete()
            db.commit()
            logger.info(f"Pulizia storico prezzi precedente a {cutoff_date} completata")
        except SQLAlchemyError as e:
            logger.error(f"Errore durante la pulizia dello storico prezzi: {str(e)}")
            db.rollback()

    def _analyze_price_trend(self, asin: str, current_price: float) -> Tuple[float, str]:
        """Analizza il trend del prezzo per un prodotto"""
        prices = self.price_trends[asin]
        prices.append(current_price)
        
        # Mantiene solo gli ultimi 10 prezzi
        if len(prices) > 10:
            prices.pop(0)
        
        if len(prices) < 2:
            return 0, "stabile"
            
        avg_price = sum(prices[:-1]) / len(prices[:-1])
        price_change = ((current_price - avg_price) / avg_price) * 100
        
        if price_change <= -5:
            return price_change, "in calo"
        elif price_change >= 5:
            return price_change, "in aumento"
        return price_change, "stabile"

    @_retry_on_db_error
    def add_product_to_monitor(self, asin: str, keyword: str, target_price: float) -> Product:
        """
        Aggiunge un nuovo prodotto da monitorare
        
        Args:
            asin: ASIN del prodotto Amazon
            keyword: Parola chiave usata per trovare il prodotto
            target_price: Prezzo target per le notifiche
            
        Returns:
            Istanza del prodotto creato
        """
        db = self.get_db()
        try:
            existing_product = db.query(Product).filter(Product.asin == asin).first()
            if existing_product:
                existing_product.target_price = target_price
                existing_product.keyword = keyword
                db.commit()
                return existing_product

            current_price, timestamp = self.keepa_service.get_current_price(asin)

            product = Product(
                asin=asin,
                keyword=keyword,
                target_price=target_price,
                last_price=current_price,
                last_check=timestamp
            )
            
            db.add(product)
            db.flush()
            
            price_history = PriceHistory(
                product_id=product.id,
                price=current_price,
                check_date=timestamp
            )
            db.add(price_history)
            
            db.commit()
            return product
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Errore durante l'aggiunta del prodotto: {str(e)}")
            raise
        finally:
            db.close()

    @_retry_on_db_error
    def remove_product(self, asin: str) -> bool:
        """
        Rimuove un prodotto dal monitoraggio
        
        Args:
            asin: ASIN del prodotto da rimuovere
            
        Returns:
            True se il prodotto è stato rimosso con successo
        """
        db = self.get_db()
        try:
            product = db.query(Product).filter(Product.asin == asin).first()
            if product:
                db.delete(product)
                db.commit()
                self.price_trends.pop(asin, None)  # Rimuove il trend dei prezzi
                return True
            return False
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Errore durante la rimozione del prodotto: {str(e)}")
            raise
        finally:
            db.close()

    @_retry_on_db_error
    def get_monitored_products(self) -> List[Product]:
        """
        Ottiene la lista di tutti i prodotti monitorati
        
        Returns:
            Lista di prodotti monitorati
        """
        db = self.get_db()
        try:
            return db.query(Product).all()
        finally:
            db.close()

    async def check_prices_batch(self, products: List[Product], db: Session):
        """Controlla i prezzi per un batch di prodotti"""
        tasks = []
        for product in products:
            tasks.append(self.keepa_service.get_current_price(product.asin))
            
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for product, result in zip(products, results):
                if isinstance(result, Exception):
                    logger.error(f"Errore nel controllo prezzo per {product.asin}: {str(result)}")
                    continue
                    
                current_price, timestamp = result
                
                # Analizza il trend del prezzo
                price_change, trend = self._analyze_price_trend(product.asin, current_price)
                
                # Aggiorna il prodotto solo se il cambiamento di prezzo è significativo
                if abs(price_change) >= MIN_PRICE_CHANGE_PERCENT:
                    product.last_price = current_price
                    product.last_check = timestamp
                    
                    price_history = PriceHistory(
                        product_id=product.id,
                        price=current_price,
                        check_date=timestamp
                    )
                    db.add(price_history)
                    
                    # Notifica se il prezzo è sceso sotto il target o se c'è un calo significativo
                    if (current_price <= product.target_price or 
                        (trend == "in calo" and price_change <= -10)):
                        await self.notification_service.send_price_alert(
                            product, 
                            current_price,
                            trend=trend,
                            change_percent=price_change
                        )
                    
            db.commit()
            
        except Exception as e:
            logger.error(f"Errore durante il controllo batch: {str(e)}")
            db.rollback()

    async def check_prices(self):
        """Controlla i prezzi di tutti i prodotti monitorati"""
        db = None
        try:
            db = self.get_db()
            products = db.query(Product).all()
            
            # Cleanup periodico dello storico prezzi
            self._cleanup_old_history(db)
            
            # Processa i prodotti in batch per ottimizzare le chiamate API
            for i in range(0, len(products), BATCH_SIZE):
                batch = products[i:i + BATCH_SIZE]
                await self.check_prices_batch(batch, db)
                
        except Exception as e:
            logger.error(f"Errore durante il controllo dei prezzi: {str(e)}")
        finally:
            if db is not None:
                db.close()

    async def start_monitoring(self):
        """Avvia il monitoraggio periodico dei prezzi"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Avvio del monitoraggio prezzi")
        
        while self.is_running:
            try:
                await self.check_prices()
            except Exception as e:
                logger.error(f"Errore nel ciclo di monitoraggio: {str(e)}")
            finally:
                await asyncio.sleep(CHECK_INTERVAL)

    def stop_monitoring(self):
        """Ferma il monitoraggio dei prezzi"""
        self.is_running = False
        logger.info("Monitoraggio prezzi fermato")
