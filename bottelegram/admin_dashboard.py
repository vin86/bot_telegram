from flask import Flask, render_template, jsonify, request, redirect, url_for
from functools import wraps
import os
from database import db
from config import ADMIN_USERNAME, ADMIN_PASSWORD
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user

app = Flask(__name__)
app.secret_key = os.urandom(24)  # per la gestione delle sessioni

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class Admin(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    if username == ADMIN_USERNAME:
        return Admin(username)
    return None

@app.route('/logout')
@login_required
def logout():
    """Gestisce il logout dell'utente"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            login_user(Admin(username))
            return redirect(url_for('dashboard'))
        return 'Credenziali non valide'
    return render_template('login.html')

@app.route('/')
@login_required
def dashboard():
    """Pagina principale dashboard"""
    stats = get_general_stats()
    return render_template('dashboard.html', stats=stats)

@app.route('/users')
@login_required
def users_list():
    """Lista di tutti gli utenti"""
    # Esegui una query SQL per ottenere tutti gli utenti
    db.cursor.execute('SELECT * FROM users')
    users = db.cursor.fetchall()
    return render_template('users.html', users=users)

@app.route('/user/<int:user_id>')
@login_required
def user_detail(user_id):
    """Dettaglio di un utente specifico"""
    user = db.get_user(user_id)
    if not user:
        return "Utente non trovato", 404
    
    products = db.get_user_products(user_id)
    return render_template('user_detail.html', user=user, products=products)

@app.route('/api/stats')
@login_required
def get_general_stats():
    """Statistiche generali del sistema"""
    # Conta il numero totale di utenti
    db.cursor.execute('SELECT COUNT(*) as count FROM users')
    total_users = db.cursor.fetchone()['count']

    # Conta il numero totale di prodotti
    db.cursor.execute('SELECT COUNT(*) as count FROM products')
    total_products = db.cursor.fetchone()['count']

    avg_products_per_user = total_products / total_users if total_users > 0 else 0
    
    # Trova i prodotti più monitorati
    db.cursor.execute('''
        SELECT asin, title, COUNT(*) as count 
        FROM products 
        GROUP BY asin 
        ORDER BY count DESC 
        LIMIT 5
    ''')
    popular_products = db.cursor.fetchall()

    return {
        "total_users": total_users,
        "total_products": total_products,
        "avg_products_per_user": round(avg_products_per_user, 2),
        "popular_products": popular_products
    }

@app.route('/logout')
@login_required
def logout():
    """Gestisce il logout dell'utente"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/users/<int:user_id>/products')
@login_required
def get_user_products(user_id):
    """API per ottenere i prodotti di un utente specifico"""
    products = db.get_user_products(user_id)
    return jsonify(products)

if __name__ == '__main__':
    app.run(debug=True, port=6689)
