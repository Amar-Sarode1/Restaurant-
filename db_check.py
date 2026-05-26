"""
Patil & Sons - Database Schema Viewer + Test Script
Run: python db_check.py
"""
import sqlite3
import json

DB = 'Patil_restaurant.db'

def show_schema():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    print("\n" + "="*60)
    print("  📊  DATABASE SCHEMA  —  Patil_restaurant.db")
    print("="*60)
    tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for (table,) in tables:
        print(f"\n  📋  TABLE: {table}")
        cols = c.execute(f"PRAGMA table_info({table})").fetchall()
        for col in cols:
            nullable = '' if col[3] else ' (optional)'
            pk = ' 🔑 PRIMARY KEY' if col[5] else ''
            print(f"      {col[1]:20s}  {col[2]}{nullable}{pk}")
        count = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"      ── {count} rows ──")
    conn.close()

def show_users():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    users = conn.execute("SELECT id,name,phone,email,joined_on FROM users").fetchall()
    print("\n  👥  USERS")
    print("  " + "-"*50)
    if not users:
        print("  No users registered yet.")
    for u in users:
        print(f"  [{u['id']}] {u['name']} | {u['phone']} | {u['email'] or 'no email'} | joined {u['joined_on']}")
    conn.close()

def show_orders():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 10").fetchall()
    print("\n  📦  RECENT ORDERS")
    print("  " + "-"*50)
    if not orders:
        print("  No orders yet.")
    for o in orders:
        items = json.loads(o['items']) if o['items'] else []
        items_str = ', '.join([f"{i['name']} x{i['qty']}" for i in items])
        print(f"  [{o['order_code']}] {o['customer_name']} | ₹{o['total']} | {o['status']} | {o['created_at'][:16]}")
        print(f"           Items: {items_str}")
    conn.close()

def show_stats():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    total_orders  = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = c.execute("SELECT SUM(total) FROM orders").fetchone()[0] or 0
    total_users   = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print("\n  📈  STATS")
    print("  " + "-"*30)
    print(f"  👥 Total Users   : {total_users}")
    print(f"  📦 Total Orders  : {total_orders}")
    print(f"  💰 Total Revenue : ₹{total_revenue:.2f}")
    conn.close()

if __name__ == '__main__':
    import os
    if not os.path.exists(DB):
        print(f"⚠️  Database not found. Run app.py first to create it.")
    else:
        show_schema()
        show_users()
        show_orders()
        show_stats()
        print("\n" + "="*60 + "\n")
