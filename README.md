# KeepaBot - Monitoraggio Prezzi Amazon

Bot Telegram per il monitoraggio dei prezzi di Amazon utilizzando le API di Keepa. Il bot permette di monitorare i prodotti e ricevere notifiche quando i prezzi scendono sotto una soglia specificata.

## Caratteristiche

- 🔍 Ricerca prodotti su Amazon
- 📊 Monitoraggio prezzi in tempo reale
- 📈 Grafici dello storico prezzi
- 🔔 Notifiche automatiche su Telegram
- 💰 Impostazione prezzi target personalizzati
- 📋 Gestione di multiple prodotti

## Requisiti

- Python 3.9 o superiore
- Account Keepa con API Key
- Bot Telegram (creato tramite @BotFather)
- Gruppo Telegram per le notifiche

## Installazione

1. Clona il repository:
```bash
git clone https://github.com/tuousername/keepabot.git
cd keepabot
```

2. Crea un ambiente virtuale e attivalo:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oppure
venv\Scripts\activate  # Windows
```

3. Installa le dipendenze:
```bash
pip install -r requirements.txt
```

4. Copia il file .env.example in .env:
```bash
cp .env.example .env
```

5. Configura le variabili d'ambiente nel file .env:
- `TELEGRAM_TOKEN`: Token del bot Telegram (ottenuto da @BotFather)
- `TELEGRAM_GROUP_ID`: ID del gruppo Telegram dove inviare le notifiche
- `KEEPA_API_KEY`: API Key di Keepa

## Utilizzo

1. Avvia il bot:
```bash
python main.py
```

2. Nel gruppo Telegram configurato, usa i seguenti comandi:
- `/start` - Inizializza il bot
- `/monitor` - Monitora un nuovo prodotto
- `/list` - Lista prodotti monitorati
- `/delete` - Rimuovi un prodotto dal monitoraggio
- `/status` - Stato del sistema
- `/help` - Mostra l'elenco dei comandi

## Monitoraggio Prezzi

1. Usa `/monitor` per iniziare il monitoraggio di un nuovo prodotto
2. Inserisci una parola chiave per cercare il prodotto
3. Seleziona il prodotto dalla lista dei risultati
4. Inserisci il prezzo target
5. Il bot notificherà nel gruppo quando il prezzo scenderà sotto il target

## Note Tecniche

- Il monitoraggio avviene ogni minuto
- Limite di 60 richieste al minuto (piano Basic di Keepa)
- I prezzi storici vengono salvati nel database locale
- I grafici mostrano l'andamento degli ultimi 30 giorni

## Licenza

MIT License - vedi il file [LICENSE](LICENSE) per i dettagli.