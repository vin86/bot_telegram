#!/bin/bash

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Amazon Price Tracker Bot - Installazione ===${NC}\n"

# Verifica che sia root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Questo script deve essere eseguito come root${NC}" 
   exit 1
fi

# Directory di installazione
INSTALL_DIR="/opt/bot_telegram"

echo -e "${BLUE}Installazione MongoDB...${NC}"
# Aggiungi la chiave del repository MongoDB
curl -fsSL https://pgp.mongodb.com/server-6.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-6.0.gpg --dearmor
# Aggiungi il repository MongoDB
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list

echo -e "${BLUE}Installing system dependencies...${NC}"
apt-get update
apt-get install -y python3 python3-pip git mongodb-org

# Clona il repository
echo -e "\n${BLUE}Clonazione repository...${NC}"
git clone https://github.com/vin86/bot_telegram.git $INSTALL_DIR
cd $INSTALL_DIR

# Richiedi API keys
echo -e "\n${BLUE}Configurazione API keys...${NC}"
read -p "Inserisci il token del bot Telegram: " telegram_token
read -p "Inserisci la API key di Keepa: " keepa_key
read -p "Inserisci username per il pannello admin: " admin_user
read -p "Inserisci password per il pannello admin: " admin_pass

# Crea file .env
echo -e "\n${BLUE}Creazione file configurazione...${NC}"
cat > $INSTALL_DIR/.env << EOF
TELEGRAM_TOKEN=$telegram_token
KEEPA_API_KEY=$keepa_key
MONGODB_URI=mongodb://localhost:27017/
ADMIN_USERNAME=$admin_user
ADMIN_PASSWORD=$admin_pass
EOF

# Crea service systemd
echo -e "\n${BLUE}Configurazione servizio systemd...${NC}"
cat > /etc/systemd/system/pricetracker.service << EOF
[Unit]
Description=Amazon Price Tracker Bot
After=network.target mongod.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/start.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Avvia MongoDB
echo -e "\n${BLUE}Avvio MongoDB...${NC}"
systemctl enable mongod
systemctl start mongod

# Verifica che requirements.txt esista
if [ ! -f "$INSTALL_DIR/requirements.txt" ]; then
    echo -e "${RED}File requirements.txt non trovato${NC}"
    exit 1
fi

# Installa dipendenze Python
echo -e "\n${BLUE}Installazione dipendenze Python...${NC}"
cd $INSTALL_DIR
pip3 install -r requirements.txt

# Avvia il servizio
echo -e "\n${BLUE}Avvio servizio Price Tracker...${NC}"
systemctl daemon-reload
systemctl enable pricetracker
systemctl start pricetracker

# Verifica lo stato
echo -e "\n${BLUE}Verifica stato servizio...${NC}"
systemctl status pricetracker

echo -e "\n${GREEN}Installazione completata!${NC}"
echo -e "Bot Telegram avviato"
echo -e "Pannello admin disponibile su http://localhost:5000"
echo -e "\nComandi utili:"
echo -e "- ${BLUE}systemctl status pricetracker${NC} : Verifica stato servizio"
echo -e "- ${BLUE}systemctl restart pricetracker${NC} : Riavvia servizio"
echo -e "- ${BLUE}journalctl -u pricetracker${NC} : Visualizza log"
echo -e "- ${BLUE}systemctl stop pricetracker${NC} : Ferma servizio"