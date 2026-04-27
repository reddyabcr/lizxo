# license_server.py - DEPLOY THIS ON YOUR SERVER
from flask import Flask, request, jsonify
import hmac
import hashlib
import secrets
import json
import sqlite3
import os
import sys

app = Flask(__name__)

# CHANGE THIS - your master secret (keep private, never in the EXE)
MASTER_SECRET = b"Lizxo-Master-Secret-2026-ChangeThisToSomethingRandom!"

# Store DB in a writable location - use /tmp on Render or current directory as fallback
if os.environ.get('RENDER'):
    DB_PATH = '/tmp/licenses.db'
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'licenses.db')

def init_db():
    """Initialize the database with error handling."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS licenses
                     (key_text TEXT PRIMARY KEY, buyer TEXT, hwid TEXT, 
                      activated INTEGER DEFAULT 0, created_at TEXT)''')
        conn.commit()
        conn.close()
        print(f"Database initialized at {DB_PATH}", file=sys.stderr)
    except Exception as e:
        print(f"Database init error: {e}", file=sys.stderr)
        raise

def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/', methods=['GET'])
def home():
    """Health check endpoint so Render knows the app is alive."""
    return jsonify({"status": "ok", "message": "License server running"})

@app.route('/activate', methods=['POST'])
def activate():
    try:
        data = request.json
        key = data.get('key', '').strip().upper() if data else ''
        hwid = data.get('hwid', '') if data else ''
        
        if not key or not hwid:
            return jsonify({"valid": False, "error": "Missing key or HWID"})
        
        db = get_db()
        lic = db.execute('SELECT * FROM licenses WHERE key_text = ?', (key,)).fetchone()
        
        if not lic:
            db.close()
            return jsonify({"valid": False, "error": "Invalid license key"})
        
        if lic['activated'] and lic['hwid'] != hwid:
            db.close()
            return jsonify({"valid": False, "error": "Key already activated on another machine"})
        
        db.execute('UPDATE licenses SET activated = 1, hwid = ? WHERE key_text = ?', (hwid, key))
        db.commit()
        db.close()
        
        return jsonify({"valid": True, "message": "License activated successfully"})
    except Exception as e:
        print(f"Activate error: {e}", file=sys.stderr)
        return jsonify({"valid": False, "error": "Internal server error"}), 500

@app.route('/verify', methods=['POST'])
def verify():
    try:
        data = request.json
        key = data.get('key', '').strip().upper() if data else ''
        hwid = data.get('hwid', '') if data else ''
        
        db = get_db()
        lic = db.execute('SELECT * FROM licenses WHERE key_text = ?', (key,)).fetchone()
        db.close()
        
        if not lic:
            return jsonify({"valid": False})
        if not lic['activated']:
            return jsonify({"valid": False, "error": "Not activated"})
        if lic['hwid'] != hwid:
            return jsonify({"valid": False, "error": "HWID mismatch"})
        
        return jsonify({"valid": True})
    except Exception as e:
        print(f"Verify error: {e}", file=sys.stderr)
        return jsonify({"valid": False, "error": "Internal server error"}), 500

@app.route('/admin/generate', methods=['GET'])
def generate_key():
    """Generate a new license key. Protect this endpoint with a secret."""
    try:
        admin_secret = request.args.get('secret', '')
        buyer = request.args.get('buyer', 'unknown')
        
        # Read from env variable - set this in Render dashboard
        ADMIN_SECRET = os.environ.get("ADMIN_SECRET")
        
        if not ADMIN_SECRET:
            print("ADMIN_SECRET not set in environment!", file=sys.stderr)
            return jsonify({"error": "Server misconfigured - no admin secret set"}), 500
        
        if admin_secret != ADMIN_SECRET:
            return jsonify({"error": "Unauthorized"}), 401
        
        key_id = secrets.token_hex(8).upper()
        payload = f"LIZXO:{buyer}:{key_id}"
        signature = hmac.new(MASTER_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:16].upper()
        license_key = f"LIZXO-{buyer.upper()}-{key_id}-{signature}"
        
        db = get_db()
        db.execute('INSERT INTO licenses (key_text, buyer, activated, created_at) VALUES (?, ?, 0, datetime("now"))',
                   (license_key, buyer))
        db.commit()
        db.close()
        
        return jsonify({"license_key": license_key, "buyer": buyer})
    except Exception as e:
        print(f"Generate error: {e}", file=sys.stderr)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

if __name__ == '__main__':
    print("Starting License Server...", file=sys.stderr)
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
