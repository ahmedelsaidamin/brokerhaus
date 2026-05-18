"""
Authentication helpers for Brokerhaus.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, g, redirect, url_for, jsonify, abort
from models import get_db


def hash_password(password, salt=None):
    """PBKDF2-SHA256 password hashing."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${h.hex()}"


def verify_password(password, stored):
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hash_password(password, salt) == stored


def create_session(user_id, days=30):
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(days=days)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires)
        )
    return token


def delete_session(token):
    if not token:
        return
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_current_user():
    """Lazily resolves the current user from the cookie."""
    if hasattr(g, "user"):
        return g.user
    token = request.cookies.get("bh_session")
    if not token:
        g.user = None
        return None
    with get_db() as conn:
        row = conn.execute("""
            SELECT u.* FROM users u
            JOIN sessions s ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > CURRENT_TIMESTAMP
        """, (token,)).fetchone()
    g.user = dict(row) if row else None
    return g.user


def login_required(role=None):
    """Decorator: require a logged-in user, optionally with a specific role."""
    def wrapper(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            user = get_current_user()
            if not user:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "auth_required"}), 401
                return redirect(url_for("login_page", next=request.path))
            if role and user["role"] != role:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "forbidden"}), 403
                abort(403)
            return fn(*args, **kwargs)
        return inner
    return wrapper
