import logging
import time
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.pool import Pool

from src.database.models import Product, PriceHistory
from src.services.keepa_service import KeepaService
from config.config import DATABASE_URL, CHECK_INTERVAL

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # secondi

class MonitorService:
    def __init__(self, notification_service, keepa_service):
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

    def _create_engine(self):
        """Crea l'engine del database con configurazione ottimizzata"""
        return create_engine(
            DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_pre_ping=True,  # Verifica la connessione prima dell'uso
            pool_recycle=3600    # Ricicla connessioni dopo 1 ora
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
            # Verifica la connessione
            db.execute("SELECT 1")
            return db
        except SQLAlchemyError as e:
            logger.error(f"Errore creazione sessione DB: {str(e)}")
            raise

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
            
        Raises:
            SQLAlchemyError: In caso di errori del database
        """
        db = self.get_db()
        try:
            # Verifica se il prodotto esiste già
            existing_product = db.query(Product).filter(Product.asin == asin).first()
            if existing_product:
                existing_product.target_price = target_price
                existing_product.keyword = keyword
                db.commit()
                return existing_product

            # Ottiene il prezzo corrente e il timestamp
            current_price, timestamp = self.keepa_service.get_current_price(asin)

            # Crea nuovo prodotto
            product = Product(
                asin=asin,
                keyword=keyword,
                target_price=target_price,
                last_price=current_price,
                last_check=timestamp
            )
            
            # Aggiunge il prodotto e la prima entry dello storico prezzi
            db.add(product)
            db.flush()  # Per ottenere l'ID del prodotto
            
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
            
        Raises:
            SQLAlchemyError: In caso di errori del database
        """
        db = self.get_db()
        try:
            product = db.query(Product).filter(Product.asin == asin).first()
            if product:
                db.delete(product)
                db.commit()
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
            
        Raises:
            SQLAlchemyError: In caso di errori del database
        """
        db = self.get_db()
        try:
            return db.query(Product).all()
        finally:
            db.close()

    def check_prices(self):
        """Controlla i prezzi di tutti i prodotti monitorati"""
        try:
            db = self.get_db()
            products = db.query(Product).all()
            
            for product in products:
                retries = 0
                while retries < MAX_RETRIES:
                    try:
                        current_price, timestamp = self.keepa_service.get_current_price(product.asin)
                        
                        # Aggiorna il prezzo nel database
                        product.last_price = current_price
                        product.last_check = timestamp
                        
                        # Aggiunge una nuova entry nello storico prezzi
                        price_history = PriceHistory(
                            product_id=product.id,
                            price=current_price,
                            check_date=timestamp
                        )
                        db.add(price_history)
                        
                        # Verifica se il prezzo è sceso sotto il target
                        if current_price <= product.target_price:
                            self.notification_service.send_price_alert(product, current_price)
                        
                        db.commit()
                        break  # Esce dal ciclo di retry se l'operazione è riuscita
                        
                    except SQLAlchemyError as e:
                        retries += 1
                        if retries == MAX_RETRIES:
                            logger.error(
                                f"Errore persistente durante l'aggiornamento del prezzo per {product.asin}: {str(e)}"
                            )
                            break
                        logger.warning(
                            f"Errore durante l'aggiornamento del prezzo per {product.asin}, "
                            f"tentativo {retries}/{MAX_RETRIES}: {str(e)}"
                        )
                        time.sleep(RETRY_DELAY)
                        db.rollback()
                    
                    except Exception as e:
                        logger.error(f"Errore durante il controllo del prezzo per {product.asin}: {str(e)}")
                        break
                        
        except Exception as e:
            logger.error(f"Errore durante il controllo dei prezzi: {str(e)}")
        finally:
            db.close()

    def start_monitoring(self):
        """Avvia il monitoraggio periodico dei prezzi"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Avvio del monitoraggio prezzi")
        
        while self.is_running:
            try:
                self.check_prices()
            except Exception as e:
                logger.error(f"Errore nel ciclo di monitoraggio: {str(e)}")
            finally:
                time.sleep(CHECK_INTERVAL)

    def stop_monitoring(self):
        """Ferma il monitoraggio dei prezzi"""
        self.is_running = False
        logger.info("Monitoraggio prezzi fermato")
