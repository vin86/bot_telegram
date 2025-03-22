import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import List, Dict
import io
from datetime import datetime, timedelta
from config import CHART_WIDTH, CHART_HEIGHT, CHART_DPI

class ChartGenerator:
    @staticmethod
    def generate_price_chart(
        price_history: List[Dict],
        target_price: float,
        title: str
    ) -> bytes:
        """
        Genera un grafico dell'andamento dei prezzi.
        
        Args:
            price_history: Lista di dizionari con timestamp e price
            target_price: Prezzo target impostato dall'utente
            title: Titolo del prodotto
            
        Returns:
            bytes: Immagine del grafico in formato PNG
        """
        # Crea una nuova figura con le dimensioni specificate
        plt.figure(figsize=(CHART_WIDTH/CHART_DPI, CHART_HEIGHT/CHART_DPI), dpi=CHART_DPI)
        
        # Estrai date e prezzi
        dates = [entry['timestamp'] for entry in price_history]
        prices = [entry['price'] for entry in price_history]
        
        # Imposta lo stile del grafico
        plt.style.use('seaborn')
        
        # Crea il grafico principale
        plt.plot(dates, prices, 'b-', label='Prezzo', linewidth=2)
        
        # Aggiungi la linea del prezzo target
        plt.axhline(y=target_price, color='r', linestyle='--', label='Prezzo Target')
        
        # Trova e marca il prezzo minimo
        min_price = min(prices)
        min_date = dates[prices.index(min_price)]
        plt.plot(min_date, min_price, 'go', label='Prezzo Minimo')
        
        # Configurazione assi e labels
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.gca().xaxis.set_major_locator(mdates.DayLocator())
        
        # Titolo e labels
        plt.title(f"Andamento Prezzi (ultimi 30 giorni) - {title[:50]}..." if len(title) > 50 else f"Andamento Prezzi (ultimi 30 giorni) - {title}")
        plt.xlabel('Data')
        plt.ylabel('Prezzo (€)')
        
        # Rotazione date per migliore leggibilità
        plt.xticks(rotation=45)
        
        # Aggiungi griglia
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Aggiungi legenda
        plt.legend()
        
        # Adatta il layout
        plt.tight_layout()
        
        # Salva il grafico in un buffer di memoria
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=CHART_DPI)
        buf.seek(0)
        
        # Chiudi la figura per liberare memoria
        plt.close()
        
        return buf.getvalue()

    @staticmethod
    def add_price_annotations(
        plt,
        dates: List[datetime],
        prices: List[float],
        min_price: float,
        current_price: float
    ):
        """Aggiunge annotazioni per prezzi significativi"""
        # Annota il prezzo minimo
        min_idx = prices.index(min_price)
        plt.annotate(
            f'Min: €{min_price:.2f}',
            xy=(dates[min_idx], min_price),
            xytext=(10, 10),
            textcoords='offset points',
            ha='left',
            va='bottom',
            bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0')
        )
        
        # Annota il prezzo corrente
        plt.annotate(
            f'Attuale: €{current_price:.2f}',
            xy=(dates[-1], current_price),
            xytext=(10, -10),
            textcoords='offset points',
            ha='left',
            va='top',
            bbox=dict(boxstyle='round,pad=0.5', fc='lightblue', alpha=0.5),
            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0')
        )

# Istanza globale del generatore di grafici
chart_generator = ChartGenerator()