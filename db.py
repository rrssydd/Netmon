"""SQLite data layer for the web suite. Plain sqlite3 (no ORM) — this is
a single-user local tool, so a lightweight layer keeps it easy to read
and modify. All timestamps stored as ISO strings (UTC-naive, local time
is fine for a single-machine tool).
"""
import json
import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "netmon.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    report_group TEXT NOT NULL,
    host TEXT,
    username TEXT,
    password TEXT,
    env_password TEXT,
    device_type TEXT DEFAULT 'cisco_ios',
    profile TEXT DEFAULT 'classic_ios',
    capture_hostname TEXT
);

CREATE TABLE IF NOT EXISTS wan_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    interface TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,            -- 'live' or 'capture'
    entity_type TEXT NOT NULL,       -- 'device' | 'wan' | 'ap'
    entity_label TEXT NOT NULL,
    cpu_max REAL,
    cpu_peak REAL,                   -- peak over last ~60 min, from device's own history buffer
    mem_pct REAL,
    port_down INTEGER,
    input_mbps REAL,
    output_mbps REAL
);
CREATE TABLE IF NOT EXISTS config_captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    device_name TEXT NOT NULL,
    host TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    output TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_label_ts ON metrics(entity_label, timestamp);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    # migration: older databases won't have this column since
    # CREATE TABLE IF NOT EXISTS doesn't alter an already-existing table
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(metrics)")}
    if "cpu_peak" not in existing_cols:
        conn.execute("ALTER TABLE metrics ADD COLUMN cpu_peak REAL")
    if "port_details" not in existing_cols:
        conn.execute("ALTER TABLE metrics ADD COLUMN port_details TEXT")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------
def list_devices():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM devices ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_device(device_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_device(data: dict):
    conn = get_conn()
    conn.execute(
        """INSERT INTO devices (name, report_group, host, username, password,
           env_password, device_type, profile, capture_hostname)
           VALUES (:name,:report_group,:host,:username,:password,
           :env_password,:device_type,:profile,:capture_hostname)""",
        data,
    )
    conn.commit()
    conn.close()


def update_device(device_id, data: dict):
    data = {**data, "id": device_id}
    conn = get_conn()
    conn.execute(
        """UPDATE devices SET name=:name, report_group=:report_group, host=:host,
           username=:username, password=:password, env_password=:env_password,
           device_type=:device_type, profile=:profile, capture_hostname=:capture_hostname
           WHERE id=:id""",
        data,
    )
    conn.commit()
    conn.close()


def delete_device(device_id):
    conn = get_conn()
    conn.execute("DELETE FROM devices WHERE id=?", (device_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# WAN links
# ---------------------------------------------------------------------------
def list_wan_links():
    conn = get_conn()
    rows = conn.execute(
        """SELECT wan_links.*, devices.name AS device_name, devices.host AS device_host
           FROM wan_links JOIN devices ON devices.id = wan_links.device_id
           ORDER BY wan_links.id"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_wan_link(label, device_id, interface):
    conn = get_conn()
    conn.execute(
        "INSERT INTO wan_links (label, device_id, interface) VALUES (?,?,?)",
        (label, device_id, interface),
    )
    conn.commit()
    conn.close()


def delete_wan_link(link_id):
    conn = get_conn()
    conn.execute("DELETE FROM wan_links WHERE id=?", (link_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Metrics (history)
# ---------------------------------------------------------------------------
def insert_metric(entity_type, entity_label, source, **fields):
    conn = get_conn()
    conn.execute(
        """INSERT INTO metrics (timestamp, source, entity_type, entity_label,
           cpu_max, cpu_peak, mem_pct, port_down, input_mbps, output_mbps, port_details)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            source,
            entity_type,
            entity_label,
            fields.get("cpu_max"),
            fields.get("cpu_peak"),
            fields.get("mem_pct"),
            1 if fields.get("port_down") else 0,
            fields.get("input_mbps"),
            fields.get("output_mbps"),
            json.dumps(fields["port_details"]) if fields.get("port_details") is not None else None,
        ),
    )
    conn.commit()
    conn.close()


def latest_metrics():
    """One row per entity_label — the most recent metric recorded for each."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT m.* FROM metrics m
           INNER JOIN (
               SELECT entity_label, MAX(timestamp) AS max_ts
               FROM metrics GROUP BY entity_label
           ) latest ON m.entity_label = latest.entity_label AND m.timestamp = latest.max_ts
           ORDER BY m.entity_type, m.entity_label"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def wan_metrics_between(start_timestamp, end_timestamp):
    """Return live SSH WAN samples inside a local-time reporting window."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT timestamp, entity_label, input_mbps, output_mbps
           FROM metrics
           WHERE entity_type='wan' AND source='live' AND timestamp >= ? AND timestamp <= ?
           ORDER BY timestamp, id""",
        (start_timestamp, end_timestamp),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def live_wan_metrics_for_label_between(entity_label, start_timestamp, end_timestamp):
    """Return live SSH samples for one WAN link inside a local-time window."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT timestamp, entity_label, input_mbps, output_mbps
           FROM metrics
           WHERE entity_type='wan' AND source='live' AND entity_label=?
             AND timestamp >= ? AND timestamp <= ?
           ORDER BY timestamp, id""",
        (entity_label, start_timestamp, end_timestamp),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def history_for(entity_label, days=14):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM metrics WHERE entity_label=?
           AND timestamp >= ?
           ORDER BY timestamp""",
        (entity_label, cutoff),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def history_samples_since(cutoff_timestamp):
    """Return metric rows used to build the compact History & Trend summary."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT timestamp, entity_type, entity_label, cpu_max, mem_pct,
                  input_mbps, output_mbps
           FROM metrics
           WHERE entity_type IN ('device','wan') AND timestamp >= ?
           ORDER BY entity_type, entity_label, timestamp, id""",
        (cutoff_timestamp,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def peak_value(entity_label, field, hours=5):
    """Max of `field` (e.g. 'cpu_max') for an entity within the last N
    hours — used for the Dashboard's 'peak' readout. Cutoff is computed
    in Python (not SQLite's datetime('now'), which is UTC) since stored
    timestamps are local time — mixing the two would silently skew the
    window by your UTC offset."""
    if field not in ("cpu_max", "mem_pct", "input_mbps", "output_mbps"):
        raise ValueError(f"unsupported field: {field}")
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    conn = get_conn()
    row = conn.execute(
        f"SELECT MAX({field}) AS peak FROM metrics WHERE entity_label=? AND timestamp >= ?",
        (entity_label, cutoff),
    ).fetchone()
    conn.close()
    return row["peak"] if row else None


def all_entity_labels():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT entity_label, entity_type FROM metrics WHERE entity_type IN ('device','wan') ORDER BY entity_type, entity_label"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def history_entities():
    """Current inventory, including uncollected devices, plus retained history."""
    entries = {(x['entity_label'], x['entity_type']): x for x in all_entity_labels()}
    for d in list_devices():
        entries[(d['report_group'], 'device')] = dict(entity_label=d['report_group'], entity_type='device')
    for w in list_wan_links():
        entries[(w['label'], 'wan')] = dict(entity_label=w['label'], entity_type='wan')
    return sorted(entries.values(), key=lambda x: (x['entity_type'], x['entity_label'].lower()))


def save_config_capture(device, output):
    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(
                'INSERT INTO config_captures (device_id, device_name, host, captured_at, output) VALUES (?,?,?,?,?)',
                (device['id'], device['report_group'], device['host'], datetime.now().isoformat(timespec='seconds'), output))
            return cursor.lastrowid
    finally:
        conn.close()


def get_config_capture(capture_id):
    conn = get_conn()
    try:
        row = conn.execute('SELECT * FROM config_captures WHERE id=?', (capture_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_config_captures(device_id=None):
    conn = get_conn()
    try:
        query = 'SELECT id, device_id, device_name, host, captured_at, length(output) AS characters FROM config_captures'
        args = ()
        if device_id is not None:
            query += ' WHERE device_id=?'
            args = (device_id,)
        rows = conn.execute(query + ' ORDER BY id DESC', args).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
