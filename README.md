# Amazon Deals Bot

Bot Telegram per il monitoraggio automatico delle offerte Amazon utilizzando l'API di Keepa.

## Caratteristiche

- Monitoraggio di keywords specifiche su Amazon
- Notifiche in tempo reale delle offerte su canale Telegram
- Tracking dei prezzi storici ultimi 30 giorni
- Supporto per referral code Amazon
- Gestione automatica delle rate limits
- Database SQLite per la persistenza dei dati

## Requisiti

- Python 3.9+
- Account Keepa con API key
- Bot Telegram (ottenuto da @BotFather)
- Canale Telegram

## Installazione

1. Clona il repository:
```bash
git clone <repository-url>
cd amazon-deals-bot
```

2. Installa le dipendenze:
```bash
pip install -r requirements.txt
```

3. Copia il file di esempio delle variabili d'ambiente:
```bash
cp .env.example .env
```

4. Configura le variabili d'ambiente nel file `.env`:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
KEEPA_API_KEY=your_keepa_api_key_here
TELEGRAM_CHANNEL_ID=your_channel_id_here
AMAZON_REFERRAL_CODE=your-20
```

## Configurazione

### Ottenere le Credenziali

1. **Bot Telegram**:
   - Vai su [@BotFather](https://t.me/botfather)
   - Crea un nuovo bot con `/newbot`
   - Copia il token fornito

2. **Channel ID Telegram**:
   - Crea un canale
   - Aggiungi il bot come amministratore
   - Inoltra un messaggio dal canale a [@userinfobot](https://t.me/userinfobot)
   - Copia l'ID del canale (inizia con -100)

3. **Keepa API Key**:
   - Registrati su [Keepa](https://keepa.com)
   - Vai su [API Access](https://keepa.com/#!api)
   - Ottieni la tua API key

4. **Amazon Referral Code**:
   - Iscriviti al programma affiliati Amazon
   - Usa il tuo tag di tracking (es. 'tuonome-20')

## Utilizzo

### Avvio del Bot

```bash
python main.py
```

### Aggiungere Keywords da Monitorare

```bash
python main.py --add-keywords "smartphone" "laptop" "tablet"
```

## Configurazione Avanzata

Le impostazioni avanzate possono essere modificate nel file `config/config.py`:

- `KEEPA_UPDATE_INTERVAL`: Intervallo di aggiornamento Keepa (minuti)
- `PRICE_HISTORY_DAYS`: Giorni di storia prezzi da considerare
- `MINIMUM_DISCOUNT_PERCENT`: Sconto minimo per la notifica
- `CHECK_INTERVAL`: Intervallo tra i controlli
- `MAX_RETRIES`: Numero massimo di tentativi per le richieste

## Struttura del Progetto

```
amazon_deals_bot/
├── config/
│   ├── __init__.py
│   └── config.py
├── src/
│   ├── __init__.py
│   ├── bot_manager.py
│   ├── keepa_client.py
│   ├── database.py
│   ├── message_formatter.py
│   └── telegram_sender.py
├── .env
├── .env.example
├── requirements.txt
└── main.py
```

## Troubleshooting

1. **Errori di Connessione Telegram**:
   - Verifica che il bot token sia corretto
   - Assicurati che il bot sia amministratore del canale
   - Controlla che l'ID del canale sia corretto

2. **Errori API Keepa**:
   - Verifica che la API key sia valida
   - Controlla il credito API rimanente
   - Verifica i rate limits

3. **Database Errors**:
   - Assicurati di avere i permessi di scrittura
   - Controlla lo spazio su disco
   - Verifica l'integrità del database

## Contribuire

Contributi e suggerimenti sono benvenuti! Per favore, apri una issue o una pull request.

## Licenza

Questo progetto è distribuito sotto licenza MIT. Vedi il file `LICENSE` per maggiori dettagli.