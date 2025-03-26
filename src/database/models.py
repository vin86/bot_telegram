from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    asin = Column(String, unique=True, nullable=False)
    keyword = Column(String, nullable=False)
    target_price = Column(Float, nullable=False)
    last_check = Column(DateTime, default=datetime.utcnow)
    last_price = Column(Float)
    
    # Relazione one-to-many con PriceHistory
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product(asin={self.asin}, keyword={self.keyword}, target_price={self.target_price})>"


class PriceHistory(Base):
    __tablename__ = 'price_history'

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    price = Column(Float, nullable=False)
    check_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relazione many-to-one con Product
    product = relationship("Product", back_populates="price_history")

    def __repr__(self):
        return f"<PriceHistory(product_id={self.product_id}, price={self.price}, date={self.check_date})>"


def init_db(database_url):
    """Inizializza il database creando tutte le tabelle necessarie"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine