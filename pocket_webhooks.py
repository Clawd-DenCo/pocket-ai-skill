"""Offline webhook verification and metadata-only reconciliation inbox.

No HTTP listener, automatic data downloads, or task writes. Events invalidate a
recording; consumers re-fetch authoritative state instead of applying stale payloads.
"""
import hashlib
import hmac
import json
import re
import sqlite3
import time

from pocket_api import ConfigurationError, ResponseError


def verify_event(raw_body, signature, timestamp_ms, secret, *, now=None, tolerance=300):
    if not isinstance(raw_body,bytes) or len(raw_body) > 2_000_000:
        raise ResponseError('Invalid or oversized webhook body')
    if not isinstance(secret,str) or not secret:
        raise ConfigurationError('Webhook signing secret required')
    if not isinstance(signature,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',signature):
        raise ResponseError('Invalid webhook signature')
    if not isinstance(timestamp_ms,str) or not re.fullmatch(r'\d{13}',timestamp_ms):
        raise ResponseError('Invalid webhook timestamp')
    if type(tolerance) not in (int,float) or not 0 < tolerance <= 600:
        raise ConfigurationError('Webhook tolerance must be 1–600 seconds')
    current = time.time() if now is None else now
    if abs(current - int(timestamp_ms)/1000) > tolerance:
        raise ResponseError('Webhook timestamp outside freshness window')
    expected = hmac.new(secret.encode(),timestamp_ms.encode()+b'.'+raw_body,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,signature.lower()):
        raise ResponseError('Webhook signature mismatch')
    try:
        event = json.loads(raw_body)
    except (ValueError,UnicodeDecodeError):
        raise ResponseError('Invalid webhook JSON') from None
    if not isinstance(event,dict) or not isinstance(event.get('event'),str):
        raise ResponseError('Invalid webhook event')
    return event


class ReconciliationInbox:
    """Single-account metadata queue; caller provisions a private database path.

    acknowledge uses a generation guard so a concurrent event cannot be lost.
    A deletion event also queues a read; only authoritative 404 may establish deletion.
    """
    def __init__(self, path, *, user_id, organization_id=None):
        if not isinstance(user_id,str) or not user_id:
            raise ConfigurationError('Expected webhook user ID required')
        self.user_id, self.organization_id = user_id, organization_id
        self.db = sqlite3.connect(path, timeout=5)
        try:
            with self.db:
                self.db.execute('CREATE TABLE IF NOT EXISTS identity (slot INTEGER PRIMARY KEY CHECK(slot=1), user_id TEXT NOT NULL, org_id TEXT)')
                row = self.db.execute('SELECT user_id,org_id FROM identity WHERE slot=1').fetchone()
                if row is None:
                    self.db.execute('INSERT INTO identity VALUES (1,?,?)',(user_id,organization_id))
                elif row != (user_id,organization_id):
                    raise ConfigurationError('Inbox belongs to another account or organization')
                self.db.execute('CREATE TABLE IF NOT EXISTS seen (digest TEXT PRIMARY KEY, received REAL NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS counter (slot INTEGER PRIMARY KEY CHECK(slot=1), generation INTEGER NOT NULL)')
                self.db.execute('INSERT OR IGNORE INTO counter VALUES (1,0)')
                self.db.execute('CREATE TABLE IF NOT EXISTS dirty (recording_id TEXT PRIMARY KEY, generation INTEGER NOT NULL)')
        except Exception:
            self.db.close()
            raise

    def receive(self, raw_body, signature, timestamp_ms, secret, *, now=None):
        current = time.time() if now is None else now
        event = verify_event(raw_body,signature,timestamp_ms,secret,now=current)
        user, org, recording = event.get('user'), event.get('organization'), event.get('recording')
        if not isinstance(user,dict) or user.get('id') != self.user_id:
            raise ResponseError('Webhook account mismatch')
        if (org.get('id') if isinstance(org,dict) else None) != self.organization_id:
            raise ResponseError('Webhook organization mismatch')
        rid = recording.get('id') if isinstance(recording,dict) else None
        if not isinstance(rid,str) or not rid or len(rid) > 256:
            raise ResponseError('Webhook recording ID missing')
        # Deduplicate identical deliveries only; never suppress a later identical state.
        # A changed delivery timestamp may cause a harmless extra reconciliation.
        digest = hashlib.sha256(raw_body).hexdigest()
        with self.db:
            self.db.execute('DELETE FROM seen WHERE received < ?', (current - 86400,))
            inserted = self.db.execute('INSERT OR IGNORE INTO seen VALUES (?,?)',(digest,current)).rowcount
            if inserted:
                self.db.execute('UPDATE counter SET generation=generation+1 WHERE slot=1')
                generation = self.db.execute('SELECT generation FROM counter WHERE slot=1').fetchone()[0]
                self.db.execute('INSERT INTO dirty VALUES (?,?) ON CONFLICT(recording_id) DO UPDATE SET generation=excluded.generation',(rid,generation))
        return bool(inserted)

    def pending(self):
        return self.db.execute('SELECT recording_id,generation FROM dirty ORDER BY recording_id').fetchall()

    def acknowledge(self, recording_id, generation):
        """Call only after successfully persisting authoritative current state."""
        with self.db:
            return bool(self.db.execute('DELETE FROM dirty WHERE recording_id=? AND generation=?',(recording_id,generation)).rowcount)

    def close(self):
        self.db.close()
