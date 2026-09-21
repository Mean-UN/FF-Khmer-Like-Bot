"""Authenticated purchase queue shared by Flask and the Telegram worker."""
import hmac
import json
import os
import re
import time
import uuid
import threading
from weakref import WeakValueDictionary
from datetime import datetime
from datetime import timedelta

from flask import jsonify, request, after_this_request
from reseller_pricing import package_price_cents
from reseller_store import SellerError


_UID_LOCKS = WeakValueDictionary()
_UID_LOCKS_GUARD = threading.Lock()

def uid_lock(uid):
    key = str(int(uid))
    with _UID_LOCKS_GUARD:
        lock = _UID_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _UID_LOCKS[key] = lock
        return lock

def worker_count():
    try:
        return max(1, min(16, int(os.environ.get("RESELLER_API_WORKERS", "4"))))
    except ValueError:
        return 4

def schema(db):
    db.execute("CREATE TABLE IF NOT EXISTS reseller_api_jobs (event_id TEXT PRIMARY KEY, seller TEXT NOT NULL, uid TEXT NOT NULL, total INTEGER NOT NULL, state TEXT NOT NULL, result TEXT)")

    columns = {row[1] for row in db.execute("PRAGMA table_info(reseller_api_jobs)")}
    for name, definition in (("created_at", "TEXT"), ("started_at", "TEXT"), ("finished_at", "TEXT"), ("active", "INTEGER NOT NULL DEFAULT 0")):
        if name not in columns:
            db.execute(f"ALTER TABLE reseller_api_jobs ADD COLUMN {name} {definition}")
    db.execute("UPDATE reseller_api_jobs SET created_at=(SELECT created_at FROM seller_events WHERE seller_events.event_id=reseller_api_jobs.event_id) WHERE created_at IS NULL")
    db.execute("CREATE INDEX IF NOT EXISTS reseller_queue_state ON reseller_api_jobs(state,uid,active)")
    db.execute("CREATE TABLE IF NOT EXISTS reseller_worker_health (id INTEGER PRIMARY KEY, heartbeat TEXT, workers INTEGER)")


def heartbeat(store, workers):
    with store.db() as db:
        schema(db)
        db.execute("INSERT OR REPLACE INTO reseller_worker_health VALUES (1,?,?)", (store.now().isoformat(), workers))


def queue_info(store, job):
    with store.db() as db:
        schema(db)
        health = db.execute("SELECT * FROM reseller_worker_health WHERE id=1").fetchone()
        queued = db.execute("SELECT COUNT(*) FROM reseller_api_jobs WHERE seller=? AND state='queued'", (job['seller'],)).fetchone()[0]
    now = store.now()
    def seconds(value):
        return max(0, int((now - datetime.fromisoformat(value)).total_seconds())) if value else None
    age = seconds(job.get('created_at'))
    if job.get('started_at') and job.get('created_at'):
        age = max(0, int((datetime.fromisoformat(job['started_at']) - datetime.fromisoformat(job['created_at'])).total_seconds()))
    last_seen = health['heartbeat'] if health else None
    return dict(queued_seconds=age, created_at=job.get('created_at'), started_at=job.get('started_at'),
                finished_at=job.get('finished_at'), seller_queued=queued,
                worker_online=last_seen is not None and seconds(last_seen) < 30,
                last_worker_seen=last_seen, worker_count=health['workers'] if health else 0)


def enqueue(store, seller, uid, total, request_id):
    cents = package_price_cents(total)
    key = f"api:{seller}:{request_id}"
    with store.db() as db:
        schema(db)
        existing = db.execute("SELECT * FROM reseller_api_jobs WHERE event_id=?", (key,)).fetchone()
        if existing:
            if existing['uid'] != uid or existing['total'] != total:
                raise SellerError('Request ID already used for a different purchase')
            return dict(existing)
        account = db.execute("SELECT * FROM sellers WHERE user_id=? AND active=1", (seller,)).fetchone()
        if not account:
            raise SellerError('Reseller access is disabled')
        used = db.execute("SELECT COALESCE(SUM(request_units),0) FROM seller_events WHERE user_id=? AND state IN ('pending','charged')", (seller,)).fetchone()[0]
        if used >= account['granted_requests']:
            raise SellerError('No reseller requests available; ask the owner to add requests')
        db.execute("INSERT INTO seller_events (event_id,user_id,name,day,created_at,kind,uid,package,cents,state) VALUES (?,?,?,?,?,'autolikeff',?,?,?,'pending')",
                   (key, seller, account['name'], store.day(), store.now().isoformat(), uid, total, cents))
        db.execute("INSERT INTO reseller_api_jobs (event_id,seller,uid,total,state,result,created_at) VALUES (?,?,?,?,'queued',NULL,?)", (key, seller, uid, total, store.now().isoformat()))
        return dict(db.execute("SELECT * FROM reseller_api_jobs WHERE event_id=?", (key,)).fetchone())


def install_reseller_api(app, store):
    def authenticate():
        seller = str(request.values.get('seller', ''))
        keys = json.loads(os.environ.get('RESELLER_API_KEYS', '{}'))
        expected = keys.get(seller) if isinstance(keys, dict) else None
        supplied = request.headers.get('Authorization', '').removeprefix('Bearer ')
        if not isinstance(expected, str) or not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
            raise PermissionError('Invalid reseller API key')
        return seller

    def view(status_only=False):
        @after_this_request
        def no_cache(response):
            response.headers['Cache-Control'] = 'no-store'
            return response
        try:
            seller = authenticate()
            request_id = request.values.get('request_id', '')
            if not request_id and not status_only:
                request_id = uuid.uuid4().hex
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', request_id):
                raise SellerError('request_id must contain 1–80 letters, digits, underscores or hyphens')
            if status_only:
                with store.db() as db:
                    schema(db)
                    row = db.execute("SELECT * FROM reseller_api_jobs WHERE event_id=? AND seller=?", (f'api:{seller}:{request_id}', seller)).fetchone()
                if not row:
                    return jsonify(success=False, error='Purchase not found'), 404
                job = dict(row)
            else:
                uid, raw_total = request.values.get('uid', ''), request.values.get('total', '')
                if not re.fullmatch(r'[0-9]{1,19}', uid) or not 0 < int(uid) <= 9223372036854775807:
                    raise SellerError('uid must be a positive 64-bit number')
                if not re.fullmatch(r'[0-9]{1,6}', raw_total):
                    raise SellerError('total must be a listed like package')
                job = enqueue(store, seller, str(int(uid)), int(raw_total), request_id)
            result = json.loads(job['result']) if job['result'] else None
            return jsonify(success=job['state'] not in ('failed', 'unknown'), request_id=request_id,
                           state=job['state'], uid=job['uid'], total=job['total'], result=result, **queue_info(store, job)), (202 if job['state'] in ('queued', 'processing') else 200)
        except PermissionError as exc:
            return jsonify(success=False, error=str(exc)), 401
        except (ValueError, TypeError) as exc:
            return jsonify(success=False, error=str(exc)), 400

    app.add_url_rule('/autolikeff', 'reseller_autolikeff', view, methods=['GET', 'POST'])
    app.add_url_rule('/autolikeff/status', 'reseller_autolikeff_status', lambda: view(True), methods=['GET'])


def finish(store, job, state, result, order=None, kind='autolikeff'):
    with store.db() as db:
        db.execute("UPDATE reseller_api_jobs SET state=?,result=?,finished_at=? WHERE event_id=?",
                   (state, json.dumps(result), store.now().isoformat(), job['event_id']))
        # Unknown external outcomes retain the request hold for owner review.
        event_state = 'charged' if state == 'completed' else 'void' if state == 'failed' else 'pending'
        if state == 'completed' and result.get('delivery') is not None and result.get('delivered') == 0:
            db.execute("UPDATE seller_events SET request_units=0 WHERE event_id=?", (job['event_id'],))
        db.execute("UPDATE seller_events SET state=?,kind=?,likes=?,detail=?,order_json=?,exported=? WHERE event_id=?",
                   (event_state, kind, result.get('delivered', 0), result.get('error', state),
                    json.dumps(order) if order else None, 0 if order else 1, job['event_id']))
        if state == 'completed' and order is None:
            db.execute("INSERT OR IGNORE INTO seller_owner_alerts (event_id) VALUES (?)", (job['event_id'],))


def process_one(features):
    store, core = features.store, features.core
    with store.db() as db:
        schema(db)
        row = db.execute("SELECT j.* FROM reseller_api_jobs j WHERE j.state='queued' AND NOT EXISTS (SELECT 1 FROM reseller_api_jobs busy WHERE busy.uid=j.uid AND busy.active=1) ORDER BY j.rowid LIMIT 1").fetchone()
        if row is None:
            return False
        job = dict(row)
        db.execute("UPDATE reseller_api_jobs SET state='processing',active=1,started_at=? WHERE event_id=?", (store.now().isoformat(), job['event_id']))
    try:
        with uid_lock(job['uid']):
            with core.autolike_lock:
                orders = core.load_autolike_orders('likeff')
                target = next((o for o in orders if str(o.get('uid')) == job['uid'] and o.get('status') != 'cancelled'), None)
                if target and (str(target.get('created_by')) != job['seller'] or not target.get('seller_event_id')):
                    finish(store, job, 'failed', {'error': 'UID has an order owned by another user'})
                    return True
                seller = store.seller(job['seller'])
                if not seller or not seller['active']:
                    finish(store, job, 'failed', {'error': 'Reseller access is disabled'})
                    return True
            delivered, queued = 0, job['total']
            delivery = None
            if job['total'] == 220:
                data = core.call_api('likeff', {'uid': job['uid']}, timeout=240)
                count = data.get('LikesGivenByAPI') if isinstance(data, dict) else None
                if not isinstance(data, dict) or data.get('error') or not data.get('success') or type(count) is not int or count < 0:
                    finish(store, job, 'unknown', {'error': 'Delivery was not confirmed; request held for owner review'})
                    return True
                delivered = count
                delivery = {key: data.get(key) for key in ('PlayerNickname', 'Region', 'LikesbeforeCommand', 'LikesafterCommand')}
            with core.autolike_lock:
                orders = core.load_autolike_orders('likeff')
                target = next((o for o in orders if str(o.get('uid')) == job['uid'] and o.get('status') != 'cancelled'), None)
                if target and (str(target.get('created_by')) != job['seller'] or not target.get('seller_event_id')):
                    finish(store, job, 'unknown' if delivery is not None else 'failed', {'error': 'Order ownership changed during processing; owner review required'})
                    return True
                queued = ((220 if target else 200) if delivered <= 100 else 0) if job['total'] == 220 else job['total']
                order, kind = None, 'autolikeff'
                if queued:
                    now = store.now()
                    if target:
                        kind = 'autolikeff_extend'
                        order = {**target, '_seller_extension': {'likes': queued, 'created_at': now.strftime('%d %b %Y %H:%M:%S')}}
                        order['_seller_extension']['initial_likes'] = delivered
                        if job['total'] == 220:
                            order['_seller_extension'].update(
                                next_run_date=(now + timedelta(days=1)).date().isoformat(),
                                last_attempt_period=now.date().isoformat())
                    else:
                        order = {'order_id': core.next_autolike_order_id(orders), 'kind': 'likeff', 'uid': job['uid'],
                                 'total_likes': queued, 'sent_likes': 0, 'telegram_user_id': job['seller'],
                                 'telegram_user_name': seller['name'], 'telegram_username': seller['username'],
                                 'group_id': None, 'created_by': job['seller'], 'created_at': now.strftime('%d %b %Y %H:%M:%S'),
                                 'status': 'active', 'last_period': '', 'last_error': '',
                                 'next_run_date': (now + timedelta(days=1)).date().isoformat() if job['total'] == 220 else core.next_autolike_run_date(kind='likeff'),
                                 'seller_event_id': job['event_id'], 'notification_bot_id': core.bot.token.split(':')[0]}
                        order['seller_initial_likes'] = delivered
                        order['immediate_first_delivery'] = job['total'] != 220
                        if job['total'] == 220:
                            order['last_attempt_period'] = now.date().isoformat()
                snapshot = dict(order) if order else None
                if snapshot and target:
                    snapshot.pop('_seller_extension', None)
                    snapshot['total_likes'] = int(target['total_likes']) + queued
                    snapshot['status'] = 'active'
                    snapshot['next_run_date'] = order['_seller_extension'].get('next_run_date') or target.get('next_run_date') or core.next_autolike_run_date(kind='likeff')
                finish(store, job, 'completed', {'delivered': delivered, 'queued_likes': queued,
                                               'delivery': delivery, 'order': snapshot,
                                               'action': 'extended' if target and queued else 'created' if queued else 'delivered',
                                               'charge_cents': package_price_cents(job['total'])}, order, kind)
                if order:
                    features.reconcile_orders(orders)
                features.owner_alert_wakeup.set()
            if order and not target and job['total'] != 220:
                # Leave the order lock before invoking the existing delivery claim.
                # That claim prevents races with the scheduled worker.
                features.send_owner_alerts()
                core.deliver_autolike_order_now(order['order_id'], 'likeff', expected_order=dict(order))
    except Exception:
        # Do not repeat a request after a crash/timeout: it may have sent likes.
        with store.db() as db:
            db.execute("UPDATE reseller_api_jobs SET state='unknown',result=? WHERE event_id=? AND state='processing'",
                       (json.dumps({'error': 'Processing interrupted; owner review required'}), job['event_id']))
        core.logger.exception('Reseller API purchase interrupted')
    finally:
        with store.db() as db:
            db.execute("UPDATE reseller_api_jobs SET active=0 WHERE event_id=?", (job['event_id'],))
    return True


def run_worker(features):
    # A previous process may have stopped after sending likes but before saving.
    with features.store.db() as db:
        schema(db)
        db.execute("UPDATE reseller_api_jobs SET state='unknown',result=? WHERE state='processing'",
                   (json.dumps({'error': 'Worker restarted during delivery; owner review required'}),))
        db.execute("UPDATE reseller_api_jobs SET active=0")
    count = worker_count()
    def worker():
        while True:
            try:
                if process_one(features):
                    continue
            except Exception:
                features.core.logger.exception('Reseller API worker failed')
            time.sleep(0.5)
    for index in range(count):
        threading.Thread(target=worker, name=f'reseller-api-{index + 1}', daemon=True).start()
    while True:
        try:
            heartbeat(features.store, count)
        except Exception:
            features.core.logger.exception('Reseller worker heartbeat failed')
        time.sleep(5)
