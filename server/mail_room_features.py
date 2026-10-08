"""Private operator preferences and inbox organization, separate from source mail."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from urllib.parse import quote


class MailRoomFeatures:
    def __init__(self, store, source_path=None, identities=None):
        self.store = store
        self.source_path = Path(source_path) if source_path else None
        self.identities = identities or {}
        with store.connect() as db:
            db.executescript('''
CREATE TABLE IF NOT EXISTS message_trash (message_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS message_flags (message_id TEXT PRIMARY KEY, is_read INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0, tags TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS signatures (address TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS preparations (draft_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attachment_checks (message_hash TEXT PRIMARY KEY, archive_hash TEXT NOT NULL, payload TEXT NOT NULL, checked REAL NOT NULL);
''')

    def options(self):
        from server.mail_identity_registry import sender_options
        items = [i for i in sender_options(self.identities) if i['address'] != self.identities['sender_selection']['system_sender']]
        with self.store.connect() as db:
            saved = {r[0]: json.loads(r[1]) for r in db.execute('SELECT address,payload FROM signatures')}
        for item in items:
            item['signature'] = saved.get(item['address'], {'signer_name': 'John Kaminski', 'signer_title': 'Authorized Representative', 'mailing_address': ''})
            item['domain'] = item['address'].rsplit('@', 1)[1]
            item['readiness'] = 'enabled' if item['live_enabled'] else 'draft_only'
        return {'senders': items, 'domains': sorted(self.identities['domains']), 'default_sender': self.identities['sender_selection']['default_sender'], 'recipient_to_sender': self.identities['sender_selection']['recipient_to_sender'], 'catch_all_domains': self.identities.get('catch_all_domains', {})}

    def signature(self, data):
        if not isinstance(data, dict) or set(data) != {'address', 'signature'}:
            raise ValueError('Invalid signature')
        if data['address'] not in {i['address'] for i in self.options()['senders']}:
            raise ValueError('Unknown sender')
        signature = data['signature']
        limits = {'signer_name': 160, 'signer_title': 160, 'mailing_address': 500}
        if not isinstance(signature, dict) or set(signature) != set(limits):
            raise ValueError('Invalid signature fields')
        for key, limit in limits.items():
            if not isinstance(signature[key], str) or not signature[key].strip() or len(signature[key]) > limit:
                raise ValueError('Invalid signature field')
        with self.store.connect() as db:
            db.execute('INSERT INTO signatures VALUES (?,?) ON CONFLICT(address) DO UPDATE SET payload=excluded.payload', (data['address'], json.dumps(signature)))
        return {'saved': True}

    def flags(self, data):
        if not isinstance(data, dict) or set(data) - {'message_id', 'is_read', 'archived', 'tags', 'deleted'} or not isinstance(data.get('message_id'), str) or len(data['message_id']) > 998:
            raise ValueError('Invalid message flags')
        for key in ['is_read', 'archived', 'deleted']:
            if key in data and type(data[key]) is not bool:
                raise ValueError('Invalid flag')
        if 'tags' in data and (not isinstance(data['tags'], list) or len(data['tags']) > 12 or any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 40 or any(ord(c) < 32 for c in t) for t in data['tags'])):
            raise ValueError('Invalid tags')
        with self.store.connect() as db:
            old = db.execute('SELECT is_read,archived,tags FROM message_flags WHERE message_id=?', (data['message_id'],)).fetchone() or (0, 0, '[]')
            values = (data['message_id'], int(data.get('is_read', bool(old[0]))), int(data.get('archived', bool(old[1]))), json.dumps(data.get('tags', json.loads(old[2]))))
            db.execute('INSERT INTO message_flags VALUES (?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET is_read=excluded.is_read,archived=excluded.archived,tags=excluded.tags', values)
            if 'deleted' in data:
                if data['deleted']: db.execute('INSERT OR IGNORE INTO message_trash VALUES (?)', (data['message_id'],))
                else: db.execute('DELETE FROM message_trash WHERE message_id=?', (data['message_id'],))
        return {'saved': True}

    def messages(self, q):
        allowed = {'q', 'recipient', 'offset', 'domain', 'folder', 'room', 'tag'}
        if set(q) - allowed or any(len(v) != 1 for v in q.values()):
            raise ValueError('Invalid filters')
        get = lambda k, default='': q.get(k, [default])[0]
        query, recipient, domain, folder, room, tag = [get(k, default) for k, default in [('q', ''), ('recipient', ''), ('domain', ''), ('folder', 'inbox'), ('room', 'all'), ('tag', '')]]
        offset = int(get('offset', '0'))
        if len(query) > 200 or any(ord(c) < 32 for c in query) or len(recipient) > 320 or (recipient and '@' not in recipient) or not 0 <= offset <= 10000 or len(tag) > 40 or domain not in ['', *self.identities.get('domains', {})] or folder not in {'inbox','archive','unread','all','quarantine','junk','pending','trash'} or room not in {'all','private','shared'}:
            raise ValueError('Invalid filters')
        if not self.source_path or not self.source_path.is_file():
            raise RuntimeError('Mail source unavailable')
        # Only persisted native authoritative rows are readable. No body leaves listing.
        private = self.identities.get('rules', {}).get('private_john_addresses', [])
        if not private:
            private = [p['address'] for p in self.identities.get('sender_profiles', {}).values() if p['address_class'] == 'private_john']
        private_json = json.dumps(private)
        where = ["m.source_authoritative=1", "m.source_scope IN ('local_native','production_native')"]
        values = []
        where.append(("" if folder == "trash" else "NOT ") + "EXISTS (SELECT 1 FROM message_trash t WHERE t.message_id=m.message_id)")
        if query:
            where.append('(instr(lower(m.subject),lower(?))>0 OR instr(lower(m.sender),lower(?))>0)'); values += [query, query]
        if recipient:
            where.append('EXISTS (SELECT 1 FROM json_each(m.recipients_json) WHERE lower(value)=lower(?))'); values.append(recipient)
        if domain:
            where.append("EXISTS (SELECT 1 FROM json_each(m.recipients_json) WHERE lower(substr(value,instr(value,'@')+1))=?)"); values.append(domain)
        if folder in {'inbox','unread'}: where.append('coalesce(f.archived,0)=0')
        if folder == 'archive': where.append('coalesce(f.archived,0)=1')
        from server.mail_room_security import required, attach, release_clause
        secured = required()
        if secured:
            if folder in {'junk','quarantine','pending'}:
                state = "coalesce((SELECT state FROM mail_security.decisions s WHERE s.message_hash=mail_hash(m.message_id)),'pending')"
                where.append(state + '=?'); values.append(folder)
            elif folder != 'trash':
                where.append(release_clause('m'))
        elif folder == 'quarantine': where.append("json_extract(a.payload,'$.quarantined')=1")
        if folder == 'unread': where.append('coalesce(f.is_read,0)=0')
        if tag:
            where.append("EXISTS (SELECT 1 FROM json_each(coalesce(f.tags,'[]')) WHERE value=?)"); values.append(tag)
        is_private = 'EXISTS (SELECT 1 FROM json_each(m.recipients_json) WHERE lower(value) IN (SELECT lower(value) FROM json_each(?)))'
        if room != 'all':
            where.append(('' if room == 'private' else 'NOT ') + is_private); values.append(private_json)
        with self.store.connect() as db:
            db.row_factory = sqlite3.Row
            if secured: attach(db)
            import hashlib
            db.create_function('message_hash', 1, lambda v: hashlib.sha256(v.encode()).hexdigest())
            uri = 'file:' + quote(str(self.source_path), safe='/') + '?mode=ro'
            db.execute('ATTACH DATABASE ? AS mail_source', (uri,))
            steps = 0
            def budget():
                nonlocal steps
                steps += 1
                return int(steps > 2000)
            db.set_progress_handler(budget, 1000)
            rows = db.execute('SELECT m.message_id,m.thread_id,m.sender,m.recipients_json,m.subject,m.occurred_at,m.direction,m.source,m.source_scope,coalesce(f.is_read,0) AS is_read,coalesce(f.archived,0) AS archived,coalesce(f.tags,\'[]\') AS tags FROM mail_source.correspondence m LEFT JOIN message_flags f ON m.message_id=f.message_id LEFT JOIN attachment_checks a ON a.message_hash=message_hash(m.message_id) WHERE ' + ' AND '.join(where) + ' ORDER BY julianday(m.occurred_at) DESC,m.message_id DESC LIMIT 26 OFFSET ?', (*values, offset)).fetchall()
        messages = []
        for r in rows[:25]:
            d = dict(r); d['deleted'] = folder == 'trash'; d['recipients'] = json.loads(d.pop('recipients_json')); d['tags'] = json.loads(d['tags']); d['is_read'] = bool(d['is_read']); d['archived'] = bool(d['archived']); d['provenance'] = {'source': d.pop('source'), 'scope': d.pop('source_scope'), 'authoritative': True}; messages.append(d)
        return {'messages': messages, 'has_more': len(rows)>25, 'offset': offset, 'content_is_untrusted': True, 'send_authorized': False}

    def record_preparation(self, draft_id, result, updated):
        safe = {'from_address': result['request']['from_address'], 'subject': result['request']['subject'], 'state': 'prepared_not_sent'}
        with self.store.connect() as db:
            db.execute('INSERT INTO preparations VALUES (?,?,?) ON CONFLICT(draft_id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated', (draft_id, json.dumps(safe), updated))

    def activity(self):
        with self.store.connect() as db:
            rows = db.execute('SELECT p.draft_id,p.payload,p.updated FROM preparations p JOIN drafts d ON p.draft_id=d.id ORDER BY p.updated DESC LIMIT 100').fetchall()
        return {'events': [{'draft_id': r[0], **json.loads(r[1]), 'updated': r[2]} for r in rows], 'send_enabled': False, 'provider_receipts_available': False}
