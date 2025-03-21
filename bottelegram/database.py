from typing import Dict, List, Optional
from datetime import datetime
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from config import (
    MONGODB_URI,
    DATABASE_NAME,
    PRODUCTS_COLLECTION,
    USERS_COLLECTION
)

class DatabaseManager:
    def __init__(self):
        self.client: MongoClient = MongoClient(MONGODB_URI)
        self.db: Database = self.client[DATABASE_NAME]
        self.users: Collection = self.db[USERS_COLLECTION]
        self.products: Collection = self.db[PRODUCTS_COLLECTION]
        self._setup_indexes()

    def _setup_indexes(self):
        """Crea gli indici necessari per ottimizzare le query"""
        # Indice per la ricerca veloce degli utenti
        self.users.create_index("telegram_id", unique=True)
        
        # Indici per i prodotti
        self.products.create_index("user_id")
        self.products.create_index("asin")
        self.products.create_index([("user_id", 1), ("asin", 1)], unique=True)

    def add_user(self, telegram_id: int, username: str) -> Dict:
        """Aggiunge un nuovo utente o aggiorna uno esistente"""
        user = {
            "telegram_id": telegram_id,
            "username": username,
            "created_at": datetime.utcnow(),
            "last_active": datetime.utcnow()
        }
        
        return self.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": user},
            upsert=True
        )

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Recupera le informazioni di un utente"""
        return self.users.find_one({"telegram_id": telegram_id})

    def add_product(self, user_id: int, data: Dict) -> Dict:
        """Aggiunge un nuovo prodotto da monitorare"""
        product = {
            "user_id": user_id,
            "asin": data["asin"],
            "url": data["url"],
            "title": data["title"],
            "image_url": data.get("image_url"),
            "target_price": data["target_price"],
            "current_price": data.get("current_price"),
            "min_historic_price": data.get("min_historic_price"),
            "price_history": data.get("price_history", []),
            "status": "active",
            "created_at": datetime.utcnow(),
            "last_checked": datetime.utcnow(),
            "last_notification": None
        }
        
        return self.products.update_one(
            {"user_id": user_id, "asin": data["asin"]},
            {"$set": product},
            upsert=True
        )

    def get_user_products(self, user_id: int) -> List[Dict]:
        """Recupera tutti i prodotti monitorati da un utente"""
        return list(self.products.find({"user_id": user_id}))

    def get_product(self, user_id: int, asin: str) -> Optional[Dict]:
        """Recupera un prodotto specifico di un utente"""
        return self.products.find_one({
            "user_id": user_id,
            "asin": asin
        })

    def update_product_price(self, user_id: int, asin: str, price: float):
        """Aggiorna il prezzo di un prodotto e lo storico prezzi"""
        current_time = datetime.utcnow()
        
        self.products.update_one(
            {"user_id": user_id, "asin": asin},
            {
                "$set": {
                    "current_price": price,
                    "last_checked": current_time
                },
                "$push": {
                    "price_history": {
                        "price": price,
                        "timestamp": current_time
                    }
                }
            }
        )

    def remove_product(self, user_id: int, asin: str):
        """Rimuove un prodotto dal monitoraggio"""
        self.products.delete_one({
            "user_id": user_id,
            "asin": asin
        })

    def get_all_active_products(self) -> List[Dict]:
        """Recupera tutti i prodotti attivi da monitorare"""
        return list(self.products.find({"status": "active"}))

    def update_last_notification(self, user_id: int, asin: str):
        """Aggiorna la data dell'ultima notifica inviata"""
        self.products.update_one(
            {"user_id": user_id, "asin": asin},
            {"$set": {"last_notification": datetime.utcnow()}}
        )

    def close(self):
        """Chiude la connessione al database"""
        self.client.close()

# Istanza globale del database manager
db = DatabaseManager()