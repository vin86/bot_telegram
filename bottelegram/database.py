from typing import Dict, List, Optional
import sqlite3
from datetime import datetime
import json
import os
from config import DATABASE_PATH

def dict_factory(cursor, row):
    """Converte le righe del database in dizionari"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

class DatabaseManager:
    def __init__(self):
        # Assicurati che la directory esista
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        self.conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        self.conn.row_factory = dict_factory
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._create_indexes()

    def _create_tables(self):
        """Crea le tabelle necessarie se non esistono"""
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP,
                last_active TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                asin TEXT,
                url TEXT,
                title TEXT,
                image_url TEXT,
                target_price REAL,
                current_price REAL,
                min_historic_price REAL,
                price_history TEXT,
                status TEXT,
                created_at TIMESTAMP,
                last_checked TIMESTAMP,
                last_notification TIMESTAMP,
                UNIQUE(user_id, asin)
            );
        ''')
        self.conn.commit()

    def _create_indexes(self):
        """Crea gli indici necessari per ottimizzare le query"""
        self.cursor.executescript('''
            CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id);
            CREATE INDEX IF NOT EXISTS idx_products_asin ON products(asin);
            CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
        ''')
        self.conn.commit()

    def add_user(self, telegram_id: int, username: str) -> Dict:
        """Aggiunge un nuovo utente o aggiorna uno esistente"""
        current_time = datetime.utcnow()
        self.cursor.execute('''
            INSERT INTO users (telegram_id, username, created_at, last_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                last_active = excluded.last_active
        ''', (telegram_id, username, current_time, current_time))
        self.conn.commit()
        return self.get_user(telegram_id)

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Recupera le informazioni di un utente"""
        self.cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        return self.cursor.fetchone()

    def add_product(self, user_id: int, data: Dict) -> Dict:
        """Aggiunge un nuovo prodotto da monitorare"""
        current_time = datetime.utcnow()
        price_history = data.get('price_history', [])
        
        self.cursor.execute('''
            INSERT INTO products (
                user_id, asin, url, title, image_url, target_price,
                current_price, min_historic_price, price_history,
                status, created_at, last_checked, last_notification
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, asin) DO UPDATE SET
                url = excluded.url,
                title = excluded.title,
                image_url = excluded.image_url,
                target_price = excluded.target_price,
                current_price = excluded.current_price,
                min_historic_price = excluded.min_historic_price,
                price_history = excluded.price_history,
                status = excluded.status,
                last_checked = excluded.last_checked
        ''', (
            user_id, data['asin'], data['url'], data['title'],
            data.get('image_url'), data['target_price'],
            data.get('current_price'), data.get('min_historic_price'),
            json.dumps(price_history), 'active', current_time,
            current_time, None
        ))
        self.conn.commit()
        return self.get_product(user_id, data['asin'])

    def get_user_products(self, user_id: int) -> List[Dict]:
        """Recupera tutti i prodotti monitorati da un utente"""
        self.cursor.execute('SELECT * FROM products WHERE user_id = ?', (user_id,))
        products = self.cursor.fetchall()
        for product in products:
            if product['price_history']:
                product['price_history'] = json.loads(product['price_history'])
        return products

    def get_product(self, user_id: int, asin: str) -> Optional[Dict]:
        """Recupera un prodotto specifico di un utente"""
        self.cursor.execute(
            'SELECT * FROM products WHERE user_id = ? AND asin = ?',
            (user_id, asin)
        )
        product = self.cursor.fetchone()
        if product and product['price_history']:
            product['price_history'] = json.loads(product['price_history'])
        return product

    def update_product_price(self, user_id: int, asin: str, price: float):
        """Aggiorna il prezzo di un prodotto e lo storico prezzi"""
        current_time = datetime.utcnow()
        
        # Recupera lo storico prezzi attuale
        product = self.get_product(user_id, asin)
        if not product:
            return
            
        price_history = product['price_history'] or []
        price_history.append({
            'price': price,
            'timestamp': current_time.isoformat()
        })

        self.cursor.execute('''
            UPDATE products
            SET current_price = ?,
                last_checked = ?,
                price_history = ?
            WHERE user_id = ? AND asin = ?
        ''', (price, current_time, json.dumps(price_history), user_id, asin))
        self.conn.commit()

    def remove_product(self, user_id: int, asin: str):
        """Rimuove un prodotto dal monitoraggio"""
        self.cursor.execute(
            'DELETE FROM products WHERE user_id = ? AND asin = ?',
            (user_id, asin)
        )
        self.conn.commit()

    def get_all_active_products(self) -> List[Dict]:
        """Recupera tutti i prodotti attivi da monitorare"""
        self.cursor.execute('SELECT * FROM products WHERE status = ?', ('active',))
        products = self.cursor.fetchall()
        for product in products:
            if product['price_history']:
                product['price_history'] = json.loads(product['price_history'])
        return products

    def update_last_notification(self, user_id: int, asin: str):
        """Aggiorna la data dell'ultima notifica inviata"""
        self.cursor.execute('''
            UPDATE products
            SET last_notification = ?
            WHERE user_id = ? AND asin = ?
        ''', (datetime.utcnow(), user_id, asin))
        self.conn.commit()

    def close(self):
        """Chiude la connessione al database"""
        self.conn.close()

# Istanza globale del database manager
db = DatabaseManager()