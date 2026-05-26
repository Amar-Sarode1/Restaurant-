"""
Patil and Sons Restaurant - Python Flask Backend
Database: SQLite
Run: python app.py
API runs on: http://localhost:5000
"""

from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import hashlib
import os
import json
from datetime import datetime
import re

app = Flask(__name__, static_folder='.')

# ─────────────────────────────────────────────
#  DATABASE SETUP
# ─────────────────────────────────────────────
DB_PATH = 'Patil_restaurant.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # dict-like rows
    return conn

def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    c = conn.cursor()

    # ── USERS table ──
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            phone       TEXT UNIQUE NOT NULL,
            email       TEXT,
            address     TEXT,
            password    TEXT NOT NULL,
            joined_on   TEXT DEFAULT (date('now')),
            is_active   INTEGER DEFAULT 1
        )
    ''')

    # ── SESSIONS table ──
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ── ORDERS table ──
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code   TEXT UNIQUE NOT NULL,
            user_id      INTEGER,
            customer_name TEXT NOT NULL,
            phone        TEXT NOT NULL,
            address      TEXT,
            order_type   TEXT NOT NULL,   -- delivery / pickup
            items        TEXT NOT NULL,   -- JSON string
            subtotal     REAL NOT NULL,
            delivery_fee REAL DEFAULT 0,
            total        REAL NOT NULL,
            payment_method TEXT NOT NULL,
            status       TEXT DEFAULT 'placed',  -- placed/preparing/delivered
            notes        TEXT,
            created_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ── REVIEWS table ──
    c.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            order_id   INTEGER,
            rating     INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment    TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ── ADDRESSES table ──
    c.execute('''
        CREATE TABLE IF NOT EXISTS addresses (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            label      TEXT DEFAULT 'Home',
            address    TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("  Database initialized:", DB_PATH)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token(user_id, phone):
    raw = f"{user_id}:{phone}:{datetime.now().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()

def get_user_from_token(token):
    if not token:
        return None
    conn = get_db()
    row = conn.execute(
        'SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=?',
        (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

@app.after_request
def after_request(response):
    return cors_headers(response)

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return jsonify({}), 200


# ─────────────────────────────────────────────
#  AUTH ROUTES
# ─────────────────────────────────────────────

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name    = (data.get('name') or '').strip()
    phone   = (data.get('phone') or '').strip().replace(' ', '')
    email   = (data.get('email') or '').strip()
    address = (data.get('address') or '').strip()
    password = (data.get('password') or '').strip()

    # Validation
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    if not phone or len(phone) < 10:
        return jsonify({'success': False, 'message': 'Valid mobile number required'}), 400
    if not password or len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    conn = get_db()
    try:
        # Check duplicate phone
        existing = conn.execute('SELECT id FROM users WHERE phone=?', (phone,)).fetchone()
        if existing:
            return jsonify({'success': False, 'message': 'Mobile number already registered. Please login.'}), 409

        hashed_pw = hash_password(password)
        c = conn.execute(
            'INSERT INTO users (name, phone, email, address, password) VALUES (?,?,?,?,?)',
            (name, phone, email, address, hashed_pw)
        )
        user_id = c.lastrowid

        # Save default address
        if address:
            conn.execute(
                'INSERT INTO addresses (user_id, label, address, is_default) VALUES (?,?,?,1)',
                (user_id, 'Home', address)
            )

        conn.commit()

        # Create session token
        token = generate_token(user_id, phone)
        conn.execute('INSERT INTO sessions (token, user_id) VALUES (?,?)', (token, user_id))
        conn.commit()

        user = conn.execute('SELECT id,name,phone,email,address,joined_on FROM users WHERE id=?', (user_id,)).fetchone()
        return jsonify({
            'success': True,
            'message': f'Welcome, {name}! Account created successfully.',
            'token': token,
            'user': dict(user)
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    phone    = (data.get('phone') or '').strip().replace(' ', '')
    password = (data.get('password') or '').strip()

    if not phone or not password:
        return jsonify({'success': False, 'message': 'Phone and password required'}), 400

    conn = get_db()
    try:
        hashed_pw = hash_password(password)
        user = conn.execute(
            'SELECT id,name,phone,email,address,joined_on FROM users WHERE phone=? AND password=? AND is_active=1',
            (phone, hashed_pw)
        ).fetchone()

        if not user:
            return jsonify({'success': False, 'message': 'Invalid mobile number or password'}), 401

        user = dict(user)
        token = generate_token(user['id'], phone)
        conn.execute('INSERT OR REPLACE INTO sessions (token, user_id) VALUES (?,?)', (token, user['id']))
        conn.commit()

        # Get order count
        order_count = conn.execute('SELECT COUNT(*) as cnt FROM orders WHERE user_id=?', (user['id'],)).fetchone()['cnt']
        user['total_orders'] = order_count

        return jsonify({
            'success': True,
            'message': f"Welcome back, {user['name']}!",
            'token': token,
            'user': user
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        conn = get_db()
        conn.execute('DELETE FROM sessions WHERE token=?', (token,))
        conn.commit()
        conn.close()
    return jsonify({'success': True, 'message': 'Logged out successfully'})


@app.route('/api/me', methods=['GET'])
def get_me():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_from_token(token)
    if not user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    conn = get_db()
    order_count = conn.execute('SELECT COUNT(*) as cnt FROM orders WHERE user_id=?', (user['id'],)).fetchone()['cnt']
    addresses = conn.execute('SELECT * FROM addresses WHERE user_id=?', (user['id'],)).fetchall()
    conn.close()

    user['total_orders'] = order_count
    user.pop('password', None)
    return jsonify({
        'success': True,
        'user': user,
        'addresses': [dict(a) for a in addresses]
    })


# ─────────────────────────────────────────────
#  PROFILE ROUTES
# ─────────────────────────────────────────────

@app.route('/api/profile', methods=['PUT'])
def update_profile():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_from_token(token)
    if not user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    data = request.get_json()
    name    = (data.get('name') or user['name']).strip()
    email   = (data.get('email') or '').strip()
    address = (data.get('address') or '').strip()

    conn = get_db()
    try:
        conn.execute(
            'UPDATE users SET name=?, email=?, address=? WHERE id=?',
            (name, email, address, user['id'])
        )
        # Update default address
        if address:
            existing = conn.execute('SELECT id FROM addresses WHERE user_id=? AND is_default=1', (user['id'],)).fetchone()
            if existing:
                conn.execute('UPDATE addresses SET address=? WHERE id=?', (address, existing['id']))
            else:
                conn.execute('INSERT INTO addresses (user_id, label, address, is_default) VALUES (?,?,?,1)', (user['id'], 'Home', address))
        conn.commit()
        updated = conn.execute('SELECT id,name,phone,email,address,joined_on FROM users WHERE id=?', (user['id'],)).fetchone()
        return jsonify({'success': True, 'message': 'Profile updated!', 'user': dict(updated)})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/change-password', methods=['PUT'])
def change_password():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_from_token(token)
    if not user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    data = request.get_json()
    old_pass = (data.get('old_password') or '').strip()
    new_pass = (data.get('new_password') or '').strip()

    if len(new_pass) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters'}), 400

    conn = get_db()
    try:
        stored = conn.execute('SELECT password FROM users WHERE id=?', (user['id'],)).fetchone()
        if stored['password'] != hash_password(old_pass):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 401
        conn.execute('UPDATE users SET password=? WHERE id=?', (hash_password(new_pass), user['id']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Password changed successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  ORDER ROUTES
# ─────────────────────────────────────────────

@app.route('/api/orders', methods=['POST'])
def place_order():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_from_token(token)   # can be None (guest order)

    data = request.get_json()
    customer_name   = (data.get('customer_name') or '').strip()
    phone           = (data.get('phone') or '').strip()
    address         = (data.get('address') or '').strip()
    order_type      = (data.get('order_type') or 'delivery').strip()
    items           = data.get('items', [])    # list of {id, name, price, qty}
    payment_method  = (data.get('payment_method') or 'cod').strip()
    notes           = (data.get('notes') or '').strip()

    if not customer_name or not phone:
        return jsonify({'success': False, 'message': 'Name and phone required'}), 400
    if not items:
        return jsonify({'success': False, 'message': 'Cart is empty'}), 400

    subtotal = sum(int(str(i.get('price','0')).replace('₹','')) * i.get('qty',1) for i in items)
    delivery_fee = 20 if order_type == 'delivery' else 0
    total = subtotal + delivery_fee
    order_code = 'JAS-' + str(int(datetime.now().timestamp()))[-6:]

    conn = get_db()
    try:
        c = conn.execute(
            '''INSERT INTO orders
               (order_code, user_id, customer_name, phone, address, order_type,
                items, subtotal, delivery_fee, total, payment_method, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (order_code, user['id'] if user else None, customer_name, phone,
             address, order_type, json.dumps(items, ensure_ascii=False),
             subtotal, delivery_fee, total, payment_method, notes)
        )
        conn.commit()
        return jsonify({
            'success': True,
            'message': 'Order placed successfully!',
            'order': {
                'id': c.lastrowid,
                'order_code': order_code,
                'total': total,
                'status': 'placed'
            }
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/orders', methods=['GET'])
def get_orders():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_from_token(token)
    if not user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 20',
        (user['id'],)
    ).fetchall()
    conn.close()

    orders = []
    for r in rows:
        o = dict(r)
        try:
            o['items'] = json.loads(o['items'])
        except:
            pass
        orders.append(o)

    return jsonify({'success': True, 'orders': orders})


@app.route('/api/orders/<order_code>', methods=['GET'])
def get_order(order_code):
    conn = get_db()
    row = conn.execute('SELECT * FROM orders WHERE order_code=?', (order_code,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'success': False, 'message': 'Order not found'}), 404
    o = dict(row)
    try:
        o['items'] = json.loads(o['items'])
    except:
        pass
    return jsonify({'success': True, 'order': o})


# ─────────────────────────────────────────────
#  ADDRESS ROUTES
# ─────────────────────────────────────────────

@app.route('/api/addresses', methods=['GET'])
def get_addresses():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_from_token(token)
    if not user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    conn = get_db()
    rows = conn.execute('SELECT * FROM addresses WHERE user_id=?', (user['id'],)).fetchall()
    conn.close()
    return jsonify({'success': True, 'addresses': [dict(r) for r in rows]})


@app.route('/api/addresses', methods=['POST'])
def add_address():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_from_token(token)
    if not user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    data = request.get_json()
    label   = (data.get('label') or 'Home').strip()
    address = (data.get('address') or '').strip()
    is_def  = 1 if data.get('is_default') else 0

    if not address:
        return jsonify({'success': False, 'message': 'Address cannot be empty'}), 400

    conn = get_db()
    try:
        if is_def:
            conn.execute('UPDATE addresses SET is_default=0 WHERE user_id=?', (user['id'],))
        conn.execute(
            'INSERT INTO addresses (user_id, label, address, is_default) VALUES (?,?,?,?)',
            (user['id'], label, address, is_def)
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Address saved!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  ADMIN ROUTES (simple)
# ─────────────────────────────────────────────

@app.route('/api/admin/orders', methods=['GET'])
def admin_orders():
    # Simple admin — in production add proper admin auth
    secret = request.headers.get('X-Admin-Key', '')
    if secret != 'patil_admin_2024':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    conn = get_db()
    rows = conn.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 50').fetchall()
    conn.close()
    orders = []
    for r in rows:
        o = dict(r)
        try: o['items'] = json.loads(o['items'])
        except: pass
        orders.append(o)
    return jsonify({'success': True, 'orders': orders, 'count': len(orders)})


@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    secret = request.headers.get('X-Admin-Key', '')
    if secret != 'patil_admin_2024':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    conn = get_db()
    total_orders  = conn.execute('SELECT COUNT(*) as c FROM orders').fetchone()['c']
    total_revenue = conn.execute('SELECT SUM(total) as s FROM orders').fetchone()['s'] or 0
    total_users   = conn.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
    today_orders  = conn.execute("SELECT COUNT(*) as c FROM orders WHERE date(created_at)=date('now')").fetchone()['c']
    conn.close()

    return jsonify({
        'success': True,
        'stats': {
            'total_orders': total_orders,
            'total_revenue': round(total_revenue, 2),
            'total_users': total_users,
            'today_orders': today_orders
        }
    })


@app.route('/api/admin/update-order-status', methods=['PUT'])
def update_order_status():
    secret = request.headers.get('X-Admin-Key', '')
    if secret != 'Patil_admin_2024':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    order_code = data.get('order_code')
    status     = data.get('status')  # placed / preparing / out_for_delivery / delivered

    if not order_code or not status:
        return jsonify({'success': False, 'message': 'order_code and status required'}), 400

    conn = get_db()
    conn.execute('UPDATE orders SET status=? WHERE order_code=?', (status, order_code))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f'Order {order_code} status → {status}'})


# ─────────────────────────────────────────────
#  SERVE FRONTEND
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'Patil-and-sons.html')


# ─────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print("\n" + "="*50)
    print("     Patil & Sons - Restaurant Backend")
    print("="*50)
    print(f"     Website  : http://localhost:5000")
    print(f"     API Base : http://localhost:5000/api")
    print(f"      Database : {DB_PATH}")
    print(f"      API Docs :")
    print(f"      POST /api/signup")
    print(f"      POST /api/login")
    print(f"      GET  /api/me")
    print(f"      PUT  /api/profile")
    print(f"      POST /api/orders")
    print(f"      GET  /api/orders")
    print(f"      GET  /api/admin/stats  (X-Admin-Key: patil_admin_2024)")
    print("="*50 + "\n")
    app.run(debug=True, port=5000, host='0.0.0.0')
