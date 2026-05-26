# 🍛 Jadhav & Sons — Restaurant Backend

## Files
```
jadhav_backend/
├── app.py                 ← Flask backend (Python)
├── jadhav-and-sons.html   ← Frontend website
├── db_check.py            ← Database viewer
└── jadhav_restaurant.db   ← SQLite database (auto-created)
```

## Setup & Run

### 1. Install Flask
```bash
pip install flask
```

### 2. Start Server
```bash
python app.py
```

### 3. Open Website
```
http://localhost:5000
```

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | /api/signup | Register new user |
| POST | /api/login | Login |
| POST | /api/logout | Logout |
| GET | /api/me | Get my profile |
| PUT | /api/profile | Update profile |
| PUT | /api/change-password | Change password |
| POST | /api/orders | Place order |
| GET | /api/orders | My order history |
| GET | /api/orders/<code> | Single order |
| GET | /api/admin/stats | Admin stats |
| GET | /api/admin/orders | All orders |

## Database Tables (SQLite)
- **users** — Customer accounts
- **sessions** — Login tokens
- **orders** — All orders placed
- **addresses** — Saved delivery addresses
- **reviews** — Customer reviews

## Admin Access
Header: `X-Admin-Key: jadhav_admin_2024`
