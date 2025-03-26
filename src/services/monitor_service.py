import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Product, PriceHistory
from src.services.keepa_service import KeepaService
from config.config import DATABASE_URL, CHECK_INTERVAL

logger = logging.getLogger(__name__)

class MonitorService:
    def __init__(self, notification_service):
        """
        Inizializza il servizio di monitoraggio
        
        Args:
            notification_service: Istanza del servizio di notifica
        """
        self.keepa_service = KeepaService()
        self.notification_service = notification_service
        self.engine = create_engine(DATABASE_URL)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.is_running = False
        self.monitoring_task = None

    def get_db(self) -> Session:
        """Crea una nuova sessione del database"""
        return self.SessionLocal()

    async def add_product_to_monitor(self, asin: str, keyword: str, target_price: float) -> Product:
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
            # Verifica se il prodotto esiste già
            existing_product = db.query(Product).filter(Product.asin == asin).first()
            if existing_product:
                existing_product.target_price = target_price
                existing_product.keyword = keyword
                db.commit()
                return existing_product

            # Ottiene il prezzo corrente
            current_price = await self.keepa_service.get_current_price(asin)
            
            # Crea nuovo prodotto
            product = Product(
                asin=asin,
                keyword=keyword,
                target_price=target_price,
                last_price=current_price,
                last_check=datetime.utcnow()
            )
            
            # Aggiunge il prodotto e la prima entry dello storico prezzi
            db.add(product)
            db.flush()  # Per ottenere l'ID del prodotto
            
            price_history = PriceHistory(
                product_id=product.id,
                price=current_price
            )
            db.add(price_history)
            
            db.commit()
            return product
            
        except Exception as e:
            db.rollback()
            logger.error(f"Errore durante l'aggiunta del prodotto: {str(e)}")
            raise
        finally:
            db.close()

    async def remove_product(self, asin: str) -> bool:
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
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Errore durante la rimozione del prodotto: {str(e)}")
            raise
        finally:
            db.close()

    async def get_monitored_products(self) -> List[Product]:
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

    async def check_prices(self):
        """Controlla i prezzi di tutti i prodotti monitorati"""
        db = self.get_db()
        try:
            products = db.query(Product).all()
            for product in products:
                try:
                    current_price = await self.keepa_service.get_current_price(product.asin)
                    
                    # Aggiorna il prezzo nel database
                    product.last_price = current_price
                    product.last_check = datetime.utcnow()
                    
                    # Aggiunge una nuova entry nello storico prezzi
                    price_history = PriceHistory(
                        product_id=product.id,
                        price=current_price
                    )
                    db.add(price_history)
                    
                    # Verifica se il prezzo è sceso sotto il target
                    if current_price <= product.target_price:
                        await self.notification_service.send_price_alert(product, current_price)
                    
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"Errore durante il controllo del prezzo per {product.asin}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Errore durante il controllo dei prezzi: {str(e)}")
        finally:
            db.close()

    async def start_monitoring(self):
        """Avvia il monitoraggio periodico dei prezzi"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Avvio del monitoraggio prezzi")
        
        while self.is_running:
            await self.check_prices()
            await asyncio.sleep(CHECK_INTERVAL)

    def stop_monitoring(self):
        """Ferma il monitoraggio dei prezzi"""
        self.is_running = False
        logger.info("Monitoraggio prezzi fermato")