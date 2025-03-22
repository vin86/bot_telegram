# Bot Telegram Monitoraggio Prezzi Amazon

Bot Telegram che permette di monitorare i prezzi dei prodotti Amazon e ricevere notifiche quando il prezzo scende sotto un target desiderato.

## Caratteristiche

- 🔍 Monitoraggio prezzi in tempo reale tramite Keepa API
- 📊 Grafici dettagliati dell'andamento prezzi
- 🎯 Notifiche automatiche quando il prezzo raggiunge il target
- 📝 Gestione lista prodotti monitorati
- 📈 Storico prezzi degli ultimi 7 giorni
- 🔄 Aggiornamento prezzi ogni ora

## Requisiti

- Sistema operativo: Ubuntu/Debian
- Python 3.8 o superiore (preinstallato su Ubuntu)
- Account Telegram
- API Key Keepa
- Bot Token Telegram

Il resto delle dipendenze (librerie Python) verrà installato automaticamente dallo script di installazione.

## Configurazione

1. Crea un nuovo bot Telegram tramite [@BotFather](https://t.me/BotFather) e ottieni il token
2. Registrati su [Keepa](https://keepa.com) e ottieni una API key
3. Crea un file `.env` nella root del progetto con:

```env
TELEGRAM_TOKEN=il_tuo_token_telegram
KEEPA_API_KEY=la_tua_api_key_keepa

# Credenziali Pannello Admin
ADMIN_USERNAME=il_tuo_username_admin
ADMIN_PASSWORD=la_tua_password_admin
```

## Installazione

### Installazione Automatica su Debian/Ubuntu

Se stai utilizzando Debian o Ubuntu, puoi utilizzare il nostro script di installazione automatica:

1. Scarica lo script di installazione:
```bash
wget https://raw.githubusercontent.com/vin86/bot_telegram/install.sh
```

2. Rendi lo script eseguibile:
```bash
chmod +x install.sh
```

3. Esegui lo script come root:
```bash
sudo ./install.sh
```

Lo script:
- Installa tutte le dipendenze necessarie
- Richiede e configura le API keys
- Configura il servizio systemd per l'avvio automatico
- Avvia il bot e il pannello admin

Una volta completata l'installazione:
- Il bot sarà in esecuzione come servizio di sistema
- Il pannello admin sarà accessibile su http://localhost:5000
- I log possono essere visualizzati con `journalctl -u pricetracker`
- Il servizio si avvierà automaticamente al riavvio del sistema

### Installazione Manuale

1. Clona il repository e installa le dipendenze:
```bash
git clone https://github.com/vin86/bot_telegram.git
cd bot_telegram
sudo pip3 install -r requirements.txt
```

## Avvio del Sistema

Per avviare sia il bot che il pannello amministrativo, usa:
```bash
python start.py
```

Questo avvierà:
- Bot Telegram sulla porta predefinita
- Pannello amministrativo su http://localhost:5000

In alternativa, puoi avviare i servizi separatamente:
```bash
# Solo bot Telegram
python main.py

# Solo pannello amministrativo
python admin_dashboard.py
```

## Utilizzo del Bot

1. Apri Telegram e cerca il tuo bot

2. Comandi disponibili:
- `/start` - Inizia a utilizzare il bot
- `/add` - Aggiungi un nuovo prodotto da monitorare
- `/list` - Visualizza la lista dei prodotti monitorati
- `/help` - Mostra l'elenco dei comandi disponibili

### Aggiungere un Prodotto

1. Invia il comando `/add`
2. Incolla il link del prodotto Amazon
3. Inserisci il prezzo target
4. Il bot inizierà a monitorare il prodotto e ti invierà una notifica quando il prezzo scenderà sotto il target

### Visualizzare i Prodotti

- Usa il comando `/list` per vedere tutti i prodotti monitorati
- Per ogni prodotto vedrai:
  * Titolo e immagine
  * Prezzo attuale
  * Prezzo target
  * Prezzo minimo storico
  * Grafico dell'andamento prezzi
  * Pulsanti per aggiornare o rimuovere il monitoraggio

## Pannello di Amministrazione

Il bot include un pannello di amministrazione web che permette di:

1. Visualizzare statistiche generali:
   - Numero totale di utenti
   - Numero totale di prodotti monitorati
   - Media prodotti per utente
   - Prodotti più popolari

2. Gestire gli utenti:
   - Lista completa degli utenti
   - Dettagli per ogni utente
   - Prodotti monitorati per utente

3. Monitorare i prodotti:
   - Visualizzazione prezzi attuali e target
   - Storico prezzi con grafici
   - Link diretti ai prodotti

Per accedere al pannello admin:
1. Configura le credenziali in `.env`
2. Avvia il server admin: `python admin_dashboard.py`
3. Accedi a `http://localhost:5000`

## Note Tecniche

- Il bot controlla i prezzi ogni 5 minuti in batch da 20 prodotti
- I grafici vengono generati utilizzando matplotlib
- Le notifiche vengono inviate solo quando il prezzo scende sotto il target
- Massimo 5 prodotti monitorati per utente
- I dati dei prezzi vengono mantenuti per 30 giorni
- Il pannello admin utilizza Flask e Bootstrap

## Limitazioni

- Solo prodotti Amazon supportati
- Il numero di richieste API è limitato dal piano Keepa
- Il bot deve essere in esecuzione continuamente per il monitoraggio

## Contribuire

Sentiti libero di aprire issues o pull requests per migliorare il bot!

## Licenza

MIT License