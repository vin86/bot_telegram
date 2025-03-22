from flask import Flask, render_template, jsonify
from functools import wraps
import os
from database import db
from config import ADMIN_USERNAME, ADMIN_PASSWORD
import flask_login
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if flask_login.request.method == 'POST':
        username = flask_login.request.form['username']
        password = flask_login.request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            login_user(Admin(username))
            return flask_login.redirect(flask_login.url_for('dashboard'))
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
    users = db.users.find()
    return render_template('users.html', users=users)

@app.route('/user/<int:user_id>')
@login_required
def user_detail(user_id):
    """Dettaglio di un utente specifico"""
    user = db.users.find_one({"telegram_id": user_id})
    if not user:
        return "Utente non trovato", 404
    
    products = db.products.find({"user_id": user_id})
    return render_template('user_detail.html', user=user, products=products)

@app.route('/api/stats')
@login_required
def get_general_stats():
    """Statistiche generali del sistema"""
    total_users = db.users.count_documents({})
    total_products = db.products.count_documents({})
    avg_products_per_user = total_products / total_users if total_users > 0 else 0
    
    # Prodotti più monitorati
    popular_products = list(db.products.aggregate([
        {"$group": {
            "_id": "$asin",
            "count": {"$sum": 1},
            "title": {"$first": "$title"}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]))

    return {
        "total_users": total_users,
        "total_products": total_products,
        "avg_products_per_user": round(avg_products_per_user, 2),
        "popular_products": popular_products
    }

@app.route('/api/users/<int:user_id>/products')
@login_required
def get_user_products(user_id):
    """API per ottenere i prodotti di un utente specifico"""
    products = list(db.products.find(
        {"user_id": user_id},
        {"_id": 0}  # esclude il campo _id dalla risposta
    ))
    return jsonify(products)

if __name__ == '__main__':
    app.run(debug=True, port=6689)