"""
Gestione del database per il monitoraggio delle offerte Amazon.
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from typing import List, Optional

from config.config import Config

Base = declarative_base()

class Keyword(Base):
    """Tabella per le parole chiave da monitorare"""
    __tablename__ = 'keywords'
    
    id = Column(Integer, primary_key=True)
    keyword = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_check = Column(DateTime)
    products = relationship("Product", back_populates="keyword")

class Product(Base):
    """Tabella per i prodotti monitorati"""
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    asin = Column(String, unique=True, nullable=False)
    title = Column(String)
    current_price = Column(Float)
    lowest_price_30d = Column(Float)
    highest_price_30d = Column(Float)
    last_update = Column(DateTime, default=datetime.utcnow)
    keyword_id = Column(Integer, ForeignKey('keywords.id'))
    keyword = relationship("Keyword", back_populates="products")
    price_history = relationship("PriceHistory", back_populates="product")
    last_notification = Column(DateTime)

class PriceHistory(Base):
    """Tabella per lo storico dei prezzi"""
    __tablename__ = 'price_history'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    product = relationship("Product", back_populates="price_history")

class Database:
    def __init__(self):
        self.engine = create_engine(Config.DATABASE_URL)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def add_keyword(self, keyword: str) -> Keyword:
        """Aggiunge una nuova keyword da monitorare"""
        session = self.Session()
        try:
            keyword_obj = Keyword(keyword=keyword.lower())
            session.add(keyword_obj)
            session.commit()
            return keyword_obj
        finally:
            session.close()

    def get_active_keywords(self) -> List[Keyword]:
        """Recupera tutte le keyword attive"""
        session = self.Session()
        try:
            return session.query(Keyword).filter_by(is_active=True).all()
        finally:
            session.close()

    def update_product(self, asin: str, title: str, current_price: float,
                      lowest_price_30d: float, highest_price_30d: float,
                      keyword_id: int) -> Product:
        """Aggiorna o crea un prodotto nel database"""
        session = self.Session()
        try:
            product = session.query(Product).filter_by(asin=asin).first()
            if not product:
                product = Product(asin=asin)
            
            product.title = title
            product.current_price = current_price
            product.lowest_price_30d = lowest_price_30d
            product.highest_price_30d = highest_price_30d
            product.keyword_id = keyword_id
            product.last_update = datetime.utcnow()
            
            # Aggiungi il prezzo corrente allo storico
            price_history = PriceHistory(
                product=product,
                price=current_price
            )
            
            session.add(product)
            session.add(price_history)
            session.commit()
            return product
        finally:
            session.close()

    def get_products_to_check(self, minutes: int = 30) -> List[Product]:
        """Recupera i prodotti da controllare"""
        session = self.Session()
        try:
            cutoff = datetime.utcnow().timestamp() - (minutes * 60)
            return session.query(Product).filter(
                (Product.last_update == None) |
                (Product.last_update <= datetime.fromtimestamp(cutoff))
            ).all()
        finally:
            session.close()

    def update_notification_timestamp(self, product_id: int) -> None:
        """Aggiorna il timestamp dell'ultima notifica per un prodotto"""
        session = self.Session()
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            if product:
                product.last_notification = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def get_price_history(self, product_id: int, days: int = 30) -> List[PriceHistory]:
        """Recupera lo storico prezzi di un prodotto"""
        session = self.Session()
        try:
            cutoff = datetime.utcnow().timestamp() - (days * 24 * 60 * 60)
            return session.query(PriceHistory).filter(
                PriceHistory.product_id == product_id,
                PriceHistory.timestamp >= datetime.fromtimestamp(cutoff)
            ).order_by(PriceHistory.timestamp.desc()).all()
        finally:
            session.close()

    def deactivate_keyword(self, keyword_id: int) -> None:
        """Disattiva una keyword"""
        session = self.Session()
        try:
            keyword = session.query(Keyword).filter_by(id=keyword_id).first()
            if keyword:
                keyword.is_active = False
                session.commit()
        finally:
            session.close()

    def cleanup_old_history(self, days: int = 60) -> None:
        """Rimuove i dati storici più vecchi di X giorni"""
        session = self.Session()
        try:
            cutoff = datetime.utcnow().timestamp() - (days * 24 * 60 * 60)
            session.query(PriceHistory).filter(
                PriceHistory.timestamp < datetime.fromtimestamp(cutoff)
            ).delete()
            session.commit()
        finally:
            session.close()