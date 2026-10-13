"""Local user accounts. Migrate the legacy single account without changing its hash."""
import os
import secrets
import sqlite3
from pathlib import Path
from werkzeug.security import check_password_hash, generate_password_hash
BASE = Path(__file__).resolve().parent
AUTH_PATH = BASE / 'auth.db'


def connect():
    c = sqlite3.connect(AUTH_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        c.execute('BEGIN IMMEDIATE')
        c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, revision TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS auth_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        if not c.execute("SELECT 1 FROM auth_meta WHERE key='multi_user_migration'").fetchone():
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='account'").fetchone():
                c.execute('INSERT OR IGNORE INTO users (username,password_hash,revision) SELECT username,password_hash,revision FROM account')
            c.execute("INSERT INTO auth_meta VALUES ('multi_user_migration','done')")
        c.commit()
        return c
    except Exception:
        c.rollback(); c.close(); raise


def account(username=None):
    c=connect()
    try:
        row=c.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone() if username is not None else c.execute('SELECT * FROM users ORDER BY id LIMIT 1').fetchone()
        return dict(row) if row else None
    finally:
        c.close()


def create(username, password, first_only=False):
    password_hash=generate_password_hash(password)
    c=connect()
    try:
        with c:
            c.execute('BEGIN IMMEDIATE')
            if first_only and c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                raise sqlite3.IntegrityError('Initial account already exists')
            c.execute('INSERT INTO users (username,password_hash,revision) VALUES (?,?,?)',
                      (username,password_hash,secrets.token_hex(16)))
    finally:
        c.close()


def verify(username,password):
    user=account(username)
    return user if user and check_password_hash(user['password_hash'],password) else None


def reset_password(username,password,expected_revision):
    password_hash=generate_password_hash(password)
    c=connect()
    try:
        with c:
            result=c.execute('UPDATE users SET password_hash=?,revision=? WHERE username=? AND revision=?',
                             (password_hash,secrets.token_hex(16),username,expected_revision))
            return result.rowcount==1
    finally:
        c.close()


def secret_key():
    path=BASE/'.session_key'
    try:
        fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        return path.read_text().strip()
    value=secrets.token_hex(32)
    with os.fdopen(fd,'w') as f:f.write(value)
    return value
