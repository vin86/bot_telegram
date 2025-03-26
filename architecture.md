# Piano Architetturale - Bot Telegram Keepa

## 1. Architettura del Sistema

```mermaid
graph TB
    A[Bot Telegram] --> B[Controller]
    B --> C[Keepa API Service]
    B --> D[Price Monitor Service]
    B --> E[Database]
    D --> F[Notification Service]
    F --> G[Telegram Group]
    
    E --> |Legge| D
    C --> |Dati Prezzi| D
```

## 2. Componenti Principali

### 2.1 Database (SQLite)
```mermaid
erDiagram
    PRODUCTS {
        int id PK
        string asin
        string keyword
        float target_price
        timestamp last_check
        float last_price
    }
    PRICE_HISTORY {
        int id PK
        int product_id FK
        float price
        timestamp check_date
    }
```

### 2.2 Flusso di Interazione Utente
```mermaid
sequenceDiagram
    User->>Bot: /start
    Bot->>User: Benvenuto! Usa /monitor per iniziare
    User->>Bot: /monitor
    Bot->>User: Inserisci parola chiave
    User->>Bot: "PlayStation 5"
    Bot->>Keepa: Ricerca prodotti
    Keepa->>Bot: Lista prodotti
    Bot->>User: Seleziona prodotto
    User->>Bot: Seleziona prodotto
    Bot->>User: Inserisci prezzo target
    User->>Bot: "400"
    Bot->>Database: Salva monitoraggio
    Bot->>User: Monitoraggio attivato
```

## 3. Funzionalità Principali

### 3.1 Comandi Telegram
- `/start` - Inizializza il bot
- `/monitor` - Avvia processo di monitoraggio nuovo prodotto
- `/list` - Lista prodotti monitorati
- `/delete` - Rimuove un monitoraggio
- `/status` - Stato del sistema e statistiche

### 3.2 Monitoraggio Prezzi
- Controllo ogni minuto dei prezzi
- Gestione delle rate limit di Keepa (60 req/min)
- Coda di priorità per le richieste

### 3.3 Sistema di Notifiche
```
🛍️ [Nome Prodotto]

💰 Prezzo Attuale: €XXX.XX
📉 Prezzo più basso: €XXX.XX
📊 Variazione: XX%

📈 Storico ultimi 30 giorni:
[Grafico]

🔗 Link prodotto: [URL]

[Immagine prodotto]
```

## 4. Struttura del Progetto
```
keepabot/
├── src/
│   ├── bot/
│   │   ├── commands/
│   │   ├── handlers/
│   │   └── keyboards/
│   ├── services/
│   │   ├── keepa_service.py
│   │   ├── monitor_service.py
│   │   └── notification_service.py
│   ├── database/
│   │   ├── models.py
│   │   └── database.py
│   └── utils/
│       ├── price_formatter.py
│       └── chart_generator.py
├── config/
│   └── config.py
├── requirements.txt
└── main.py
```

## 5. Tecnologie

- **Python 3.9+**
- **python-telegram-bot**: Per l'interfaccia Telegram
- **keepa**: Client ufficiale Keepa
- **SQLAlchemy**: ORM per il database
- **Pillow**: Per la generazione dei grafici
- **aiohttp**: Per chiamate API asincrone
- **SQLite**: Database locale

## 6. Gestione degli Errori

### 6.1 Keepa API
- Gestione rate limiting
- Retry automatico in caso di errori temporanei
- Cache dei risultati per ottimizzare le richieste

### 6.2 Telegram
- Gestione disconnessioni
- Retry per messaggi non consegnati
- Gestione errori di formato

### 6.3 Sistema
- Logging completo
- Monitoraggio risorse
- Backup automatico database