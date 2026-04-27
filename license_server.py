# license_server.py - DEPLOY THIS ON YOUR SERVER
from flask import Flask, request, jsonify
import hmac
import hashlib
import secrets
import json
import sqlite3
import os

app = Flask(__name__)

# CHANGE THIS - your master secret (keep private, never in the EXE)
MASTER_SECRET = b"Lizxo-Master-Secret-2026-ChangeThisToSomethingRandom!"

def init_db():
    conn = sqlite3.connect('licenses.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS licenses
                 (key_text TEXT PRIMARY KEY, buyer TEXT, hwid TEXT, activated INTEGER, created_at TEXT)''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect('licenses.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/activate', methods=['POST'])
def activate():
    data = request.json
    key = data.get('key', '').strip().upper()
    hwid = data.get('hwid', '')
    
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

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    key = data.get('key', '').strip().upper()
    hwid = data.get('hwid', '')
    
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

@app.route('/admin/generate', methods=['GET'])
def generate_key():
    """Generate a new license key. Protect this endpoint with a secret."""
    admin_secret = request.args.get('secret', '')
    buyer = request.args.get('buyer', 'unknown')
    
    if admin_secret != "YOUR_ADMIN_SECRET_HERE":
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

if __name__ == '__main__':
    init_db()
    # In production, use a real HTTPS server (nginx + gunicorn + letsencrypt)
    app.run(host='0.0.0.0', port=5000)