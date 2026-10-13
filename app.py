"""Netmon Workspace — local Cisco CPU, memory and uplink monitoring."""
import io
import secrets
import sqlite3
import threading
import time
from collections import deque
from datetime import timedelta
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for, send_file
import auth
from verification import LocalVerification
import db
import logic
from netmon import collector
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.update(SECRET_KEY=auth.secret_key(), SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax', PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
                  MAX_CONTENT_LENGTH=5 * 1024 * 1024)
db.init_db()
collection_lock = threading.Lock()
login_lock = threading.Lock()
login_attempts = deque()
local_verification = LocalVerification()


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_hex(32)
    return session['csrf']


@app.context_processor
def template_context():
    return {'csrf_token': csrf_token}


@app.before_request
def protect_routes():
    if request.endpoint == 'static':
        return
    if request.method == 'POST':
        expected = session.get('csrf', '')
        actual = request.form.get('csrf_token', '')
        if not expected or not secrets.compare_digest(expected, actual):
            abort(400, 'Sesi form berakhir. Muat ulang halaman lalu coba lagi.')
    user = auth.account()
    if request.endpoint in ('login', 'setup', 'forgot_password', 'register'):
        return
    if not user:
        session.pop('user', None)
        session.pop('revision', None)
        return redirect(url_for('setup'))
    user = auth.account(session.get('user')) if session.get('user') else None
    if not user or session.get('revision') != user['revision']:
        if request.path.startswith('/api/'):
            return jsonify(error='Silakan login kembali.'), 401
        return redirect(url_for('login'))


@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.endpoint != 'static':
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if auth.account():
        return redirect(url_for('login'))
    session.pop('user', None)
    session.pop('revision', None)
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not 3 <= len(username) <= 64 or len(password) < 10:
            flash('Username 3–64 karakter dan password minimal 10 karakter.', 'error')
        elif password != request.form.get('confirm'):
            flash('Konfirmasi password belum sama.', 'error')
        else:
            try:
                auth.create(username, password, first_only=True)
            except sqlite3.IntegrityError:
                return redirect(url_for('login'))
            session.clear()
            flash('Akun dibuat. Silakan masuk.', 'success')
            return redirect(url_for('login'))
    return render_template('auth.html', setup=True)


@app.route('/login', methods=['GET', 'POST'])
def login():
    current = auth.account()
    if not current:
        session.pop('user', None)
        return redirect(url_for('setup'))
    logged_user = auth.account(session.get('user')) if session.get('user') else None
    if logged_user and session.get('revision') == logged_user['revision']:
        return redirect(url_for('dashboard'))
    session.pop('user', None)
    session.pop('revision', None)
    if request.method == 'POST':
        now = time.monotonic()
        with login_lock:
            while login_attempts and login_attempts[0] < now - 300:
                login_attempts.popleft()
            blocked = len(login_attempts) >= 10
            if not blocked:
                login_attempts.append(now)
        if blocked:
            flash('Terlalu banyak percobaan. Coba kembali dalam 5 menit.', 'error')
            return render_template('auth.html', setup=False), 429
        user = auth.verify(request.form.get('username', '').strip(), request.form.get('password', ''))
        if user:
            with login_lock:
                login_attempts.clear()
            session.clear()
            session.update(user=user['username'], revision=user['revision'])
            session.permanent = True
            return redirect(url_for('dashboard'))
        flash('Username atau password salah.', 'error')
    return render_template('auth.html', setup=False)


def account_flow(purpose):
    if not auth.account():
        return redirect(url_for('setup'))
    session.pop('user', None)
    session.pop('revision', None)
    key = 'verification_' + purpose
    endpoint = 'register' if purpose == 'register' else 'forgot_password'
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'request_code':
            username = request.form.get('username', '').strip()
            if not 3 <= len(username) <= 64 or any(ord(ch) < 32 for ch in username):
                flash('Isi username 3–64 karakter.', 'error')
            elif purpose == 'register' and auth.account(username):
                flash('Username sudah digunakan. Pilih username lain atau gunakan Lupa password.', 'error')
            else:
                user = auth.account(username)
                try:
                    # A nonexistent username gets the same response, but no usable reset.
                    if purpose == 'register' or user:
                        challenge = local_verification.issue(purpose, username,
                            user['revision'] if user else None, session.get(key))
                    else:
                        challenge = secrets.token_urlsafe(24)
                    session[key] = challenge
                    session[key + '_username'] = username
                    flash('Periksa terminal tempat python app.py berjalan untuk kode verifikasi. Jika username pemulihan cocok, kode akan ditampilkan di sana.', 'info')
                except ValueError as exc:
                    flash(str(exc), 'error')
        elif action == 'complete':
            password = request.form.get('password', '')
            if len(password) < 10:
                flash('Password minimal 10 karakter.', 'error')
            elif password != request.form.get('confirm'):
                flash('Konfirmasi password belum sama.', 'error')
            else:
                proof = local_verification.consume(session.get(key), purpose, request.form.get('code', '').strip())
                if not proof:
                    flash('Kode salah, sudah digunakan, kedaluwarsa, atau batas 5 percobaan tercapai. Minta kode baru jika diperlukan.', 'error')
                else:
                    try:
                        if purpose == 'register':
                            auth.create(proof['username'], password)
                            success = True
                        else:
                            success = auth.reset_password(proof['username'], password, proof['revision'])
                    except sqlite3.IntegrityError:
                        success = False
                    if success:
                        session.clear()
                        with login_lock:
                            login_attempts.clear()
                        flash('User baru berhasil dibuat. Silakan login.' if purpose == 'register' else 'Password berhasil diubah. Silakan login dengan password baru.', 'success')
                        return redirect(url_for('login'))
                    flash('Akun sudah berubah atau username telah digunakan. Minta kode baru.', 'error')
                    session.pop(key, None)
        else:
            abort(400)
        return redirect(url_for(endpoint))
    return render_template('account_flow.html', purpose=purpose, pending=bool(session.get(key)),
                           recovery_username=session.get(key + '_username', ''))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    return account_flow('reset')


@app.route('/register', methods=['GET', 'POST'])
def register():
    return account_flow('register')


@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.get('/')
def dashboard():
    return render_template('dashboard.html', data=logic.build_dashboard_data(),
                           thresholds=logic.load_thresholds(), active='dashboard')


@app.get('/api/daily-traffic/<path:label>')
def api_daily_traffic(label):
    if not any(link['label'] == label for link in db.list_wan_links()):
        abort(404)
    try:
        series = logic.daily_traffic_series(label, request.args.get('end_at'))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(series)


@app.post('/collect')
def collect_now():
    if not collection_lock.acquire(blocking=False):
        flash('Collect masih berjalan. Tunggu sampai proses selesai.', 'info')
        return redirect(url_for('dashboard'))
    try:
        log = logic.run_live_collection()
        ok = sum(line.startswith('OK') for line in log)
        errors = sum(line.startswith('[!]') for line in log)
        flash(f'Collect selesai · {ok} berhasil · {errors} gagal', 'success' if not errors else 'error')
        session['collection_log'] = log
    except Exception:
        app.logger.exception('Collection failed')
        flash('Collect terhenti. Periksa terminal aplikasi untuk detail; data yang berhasil terkumpul tetap tersimpan.', 'error')
    finally:
        collection_lock.release()
    return redirect(url_for('dashboard'))


@app.get('/devices')
def devices():
    edit = db.get_device(request.args.get('edit', type=int)) if request.args.get('edit') else None
    return render_template('devices.html', devices=db.list_devices(), wan_links=db.list_wan_links(), edit=edit, active='devices')


def device_form(existing=None):
    f = request.form
    label = f.get('report_group', '').strip()
    if not label or len(label) > 100:
        raise ValueError('Isi nama perangkat, maksimal 100 karakter.')
    if any(d['report_group'] == label and (not existing or d['id'] != existing['id']) for d in db.list_devices()) or any(w['label'] == label for w in db.list_wan_links()):
        raise ValueError('Nama perangkat atau link sudah digunakan.')
    profile = f.get('profile', 'classic_ios')
    driver = f.get('device_type', 'cisco_ios')
    if profile not in ('classic_ios', 'platform_xe') or driver not in ('cisco_ios', 'cisco_xe'):
        raise ValueError('Profile perangkat tidak valid.')
    return dict(name=label, report_group=label, host=f.get('host', '').strip(),
                username=f.get('username', '').strip(), password=f.get('password') or (existing or {}).get('password', ''),
                env_password=f.get('env_password', '').strip(), device_type=driver, profile=profile,
                capture_hostname=f.get('capture_hostname', '').strip())


@app.post('/devices/save')
def save_device():
    device_id = request.form.get('device_id', type=int)
    existing = db.get_device(device_id) if device_id else None
    if device_id and not existing:
        abort(404)
    try:
        data = device_form(existing)
        # Labels identify historical metrics: preserve the history when renamed.
        if existing:
            with db.get_conn() as c:
                c.execute("UPDATE metrics SET entity_label=? WHERE entity_type='device' AND entity_label=?", (data['report_group'], existing['report_group']))
            db.update_device(device_id, data)
        else:
            db.add_device(data)
        flash('Perangkat disimpan.', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('devices'))


@app.post('/devices/<int:device_id>/delete')
def delete_device(device_id):
    db.delete_device(device_id)
    flash('Perangkat dan mapping uplink dihapus. History tetap tersimpan.', 'info')
    return redirect(url_for('devices'))


@app.post('/wan/add')
def add_wan():
    label = request.form.get('label', '').strip()
    device_id = request.form.get('device_id', type=int)
    interface = request.form.get('interface', '').strip()
    if not label or not interface or not db.get_device(device_id):
        flash('Isi label, perangkat, dan interface uplink.', 'error')
    elif any(w['label'] == label for w in db.list_wan_links()) or any(d['report_group'] == label for d in db.list_devices()):
        flash('Nama perangkat atau link sudah digunakan.', 'error')
    else:
        db.add_wan_link(label, device_id, interface)
        flash('Uplink ditambahkan.', 'success')
    return redirect(url_for('devices'))


@app.post('/wan/<int:link_id>/delete')
def delete_wan(link_id):
    db.delete_wan_link(link_id)
    flash('Mapping uplink dihapus. History tetap tersimpan.', 'info')
    return redirect(url_for('devices'))


@app.route('/import', methods=['GET', 'POST'])
def import_capture():
    result = None
    if request.method == 'POST':
        file = request.files.get('capture_file')
        if not file or not file.filename.lower().endswith('.txt'):
            flash('Pilih file capture .txt.', 'error')
        else:
            result = logic.run_capture_import(file.read().decode('utf-8', errors='replace'))
            flash(f"Import selesai · {len(result['imported'])} label diperbarui", 'success' if result['imported'] else 'error')
    return render_template('import.html', result=result, active='import')


@app.route('/capture-device', methods=['GET', 'POST'])
def capture_device():
    selected_id = request.form.get('device_id', type=int) if request.method == 'POST' else request.args.get('device_id', type=int)
    if request.method == 'POST':
        device = db.get_device(selected_id)
        if not device:
            flash('Pilih perangkat yang terdaftar di Devices & Uplinks.', 'error')
            return redirect(url_for('capture_device'))
        if not collection_lock.acquire(blocking=False):
            flash('Proses SSH lain masih berjalan. Tunggu sampai selesai.', 'info')
            return redirect(url_for('capture_device', device_id=selected_id))
        try:
            result = collector.collect_running_config(device)
            if 'error' in result:
                flash(result['error'], 'error')
                return redirect(url_for('capture_device', device_id=selected_id))
            capture_id = db.save_config_capture(device, result['raw'])
        except Exception:
            app.logger.exception('Config capture failed')
            flash('Capture belum berhasil disimpan. Coba kembali dan periksa terminal aplikasi.', 'error')
            return redirect(url_for('capture_device', device_id=selected_id))
        finally:
            collection_lock.release()
        flash('Show run selesai. Backup tersimpan dan siap diunduh.', 'success')
        return redirect(url_for('capture_device', device_id=selected_id, capture_id=capture_id))
    capture_id = request.args.get('capture_id', type=int)
    capture = db.get_config_capture(capture_id) if capture_id is not None else None
    if capture_id is not None and not capture:
        abort(404)
    if capture:
        selected_id = capture['device_id']
    return render_template('capture_device.html', devices=db.list_devices(), selected_id=selected_id,
                           capture=capture, backups=db.list_config_captures(), active='capture_device')


@app.get('/capture-device/<int:capture_id>/download')
def download_config(capture_id):
    capture = db.get_config_capture(capture_id)
    if not capture:
        abort(404)
    name = secure_filename(capture['device_name']) or 'device'
    stamp = capture['captured_at'].replace(':', '').replace('-', '')
    return send_file(io.BytesIO(capture['output'].encode('utf-8')), mimetype='text/plain; charset=utf-8',
                     as_attachment=True, download_name=f'{name}_show-run_{stamp}_{capture_id}.txt')


@app.get('/api/local-status')
def local_status():
    return jsonify(status='online', mode='local')


@app.get('/history')
def history():
    thresholds = logic.load_thresholds()
    daily = thresholds.get('daily_report', {})
    wan_limit = daily.get('mbps_limit', thresholds.get('wan_link', {}).get('mbps_warning', 300))
    entities = db.history_entities()
    return render_template('history.html', entities=entities,
                           selected_label=request.args.get('label'), active='history',
                           wan_limit=wan_limit,
                           device_count=sum(e['entity_type'] == 'device' for e in entities),
                           wan_count=sum(e['entity_type'] == 'wan' for e in entities))


@app.get('/api/history-summary')
def api_history_summary():
    try:
        days = int(request.args.get('days', '7'))
    except ValueError:
        return jsonify(error='Rentang waktu tidak valid.'), 400
    if days not in (1, 7, 14, 30):
        return jsonify(error='Rentang waktu tidak valid.'), 400
    return jsonify(logic.build_history_summaries(days))


@app.get('/api/history/<path:label>')
def api_history(label):
    try:
        days = int(request.args.get('days', '14'))
    except ValueError:
        return jsonify(error='Rentang waktu tidak valid.'), 400
    if days not in (1, 7, 14, 30):
        return jsonify(error='Rentang waktu tidak valid.'), 400
    return jsonify(db.history_for(label, days=days))


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(413)
def handled_error(error):
    return render_template('error.html', message=error.description, code=error.code), error.code


if __name__ == '__main__':
    print('Netmon Workspace: http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False)
