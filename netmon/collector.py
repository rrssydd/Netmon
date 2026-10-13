"""SSH collection layer — connects to each device and runs the command set
for its profile. Kept separate from parsing so parsing can be unit-tested
offline (see tests/test_parsers.py) without a live device.
"""
import os
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException

COMMANDS = {
    "platform_xe": [
        "show plat soft stat contr br",
        "show processes cpu | include utilization",
        "show processes cpu history",
        "show interfaces status",
    ],
    "classic_ios": [
        "show processes cpu | include utilization",
        "show processes cpu history",
        "show memory statistics",
        "show interfaces status",
    ],
}


def resolve_password(device: dict) -> str:
    """Use the saved SSH password, then its configured environment variable."""
    if device.get("password"):
        return device["password"]
    env_key = device.get("env_password")
    if env_key and os.environ.get(env_key):
        return os.environ[env_key]
    raise ValueError("Password belum diisi atau environment variable belum tersedia.")


def collect_device(device: dict) -> dict:
    """Connect to one device, run its profile's commands, return raw text
    keyed by command. Returns {'error': ...} instead of raising, so one
    unreachable device doesn't stop the whole run."""
    try:
        password = resolve_password(device)
    except ValueError as exc:
        return {"error": f"{device['name']}: {exc}"}
    profile = device["profile"]
    conn_params = {
        "device_type": device["device_type"],
        "host": device["host"],
        "username": device["username"],
        "password": password,
        "timeout": 15,
    }
    outputs = {}
    try:
        with ConnectHandler(**conn_params) as conn:
            for cmd in COMMANDS.get(profile, []):
                outputs[cmd] = conn.send_command(cmd)
    except NetmikoAuthenticationException:
        return {"error": f"Auth gagal ke {device['name']} ({device['host']})"}
    except NetmikoTimeoutException:
        return {"error": f"Timeout / unreachable: {device['name']} ({device['host']})"}
    except Exception as exc:  # noqa: BLE001 — surface any driver error, keep going
        return {"error": f"Gagal konek {device['name']}: {exc}"}
    return {"raw": outputs}


def collect_interface(device: dict, interface: str) -> dict:
    """Reuses a device's login to pull one interface's 'show interfaces'."""
    try:
        password = resolve_password(device)
    except ValueError as exc:
        return {"error": f"{device['name']}: {exc}"}
    conn_params = {
        "device_type": device["device_type"],
        "host": device["host"],
        "username": device["username"],
        "password": password,
        "timeout": 15,
    }
    try:
        with ConnectHandler(**conn_params) as conn:
            raw = conn.send_command(f"show interfaces {interface}")
        return {"raw": raw}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Gagal ambil {interface} di {device['name']}: {exc}"}



def collect_running_config(device: dict) -> dict:
    """Read the selected device's running config; never enter configuration mode."""
    import re
    try:
        password = resolve_password(device)
        if not device.get('host') or not device.get('username'):
            return {'error': 'Host dan username SSH perangkat belum lengkap.'}
        with ConnectHandler(device_type=device['device_type'], host=device['host'],
                            username=device['username'], password=password, timeout=15) as conn:
            output = conn.send_command('show run', read_timeout=120)
        if not output.strip():
            return {'error': 'Perangkat mengembalikan output kosong; backup tidak disimpan.'}
        if re.search(r'^\s*%\s*(?:Invalid|Incomplete|Ambiguous|Authorization|Access denied|Error|Permission)', output, re.I | re.M):
            return {'error': 'Command show run ditolak perangkat. Periksa hak akses akun SSH; backup tidak disimpan.'}
        # Avoid labelling a banner, denied command, or paginated fragment as a backup.
        if '--More--' in output or not re.search(r'^end\s*$', output, re.M):
            return {'error': 'Output show run belum lengkap (penanda end tidak ditemukan atau masih terpotong). Periksa hak akses SSH dan coba kembali; backup tidak disimpan.'}
        return {'raw': output}
    except NetmikoAuthenticationException:
        return {'error': 'Login SSH gagal. Periksa username/password perangkat.'}
    except NetmikoTimeoutException:
        return {'error': 'Perangkat tidak terjangkau atau koneksi SSH timeout.'}
    except ValueError as exc:
        return {'error': str(exc)}
    except Exception:
        return {'error': 'Gagal mengambil konfigurasi lengkap. Periksa koneksi dan hak akses show run, kemudian coba kembali.'}
