"""
Database management for Dementia Chatbot
"""
import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from config import DATABASE_PATH, FERNET_CIPHER, DEFAULT_LANGUAGE


def _language_sql_filter(language: Optional[str]):
    """Exact match per language; default 'en' also includes legacy rows with NULL language."""
    if not language:
        return "", []
    if language == DEFAULT_LANGUAGE:
        return " AND (language IS NULL OR language = ?)", [DEFAULT_LANGUAGE]
    return " AND language = ?", [language]


class MemoryDatabase:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    full_name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trusted_contacts (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    relation TEXT,
                    contact TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create memories table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    text_encrypted BLOB NOT NULL,
                    timestamp DATETIME NOT NULL,
                    source TEXT NOT NULL,
                    tags_encrypted BLOB,
                    language TEXT DEFAULT 'en',
                    caregiver_confirmed BOOLEAN DEFAULT FALSE,
                    source_modality TEXT DEFAULT 'text',
                    importance REAL DEFAULT 0.5,
                    reinforcement_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add date_mentions column if it doesn't exist (migration)
            try:
                cursor.execute('ALTER TABLE memories ADD COLUMN date_mentions TEXT')
            except sqlite3.OperationalError:
                # Column already exists
                pass
            for migration in [
                "ALTER TABLE memories ADD COLUMN user_id TEXT",
                "ALTER TABLE memories ADD COLUMN source_modality TEXT DEFAULT 'text'",
                "ALTER TABLE memories ADD COLUMN importance REAL DEFAULT 0.5",
                "ALTER TABLE memories ADD COLUMN reinforcement_count INTEGER DEFAULT 0",
            ]:
                try:
                    cursor.execute(migration)
                except sqlite3.OperationalError:
                    pass
            
            # Create user_sessions table for tracking interactions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_start DATETIME NOT NULL,
                    session_end DATETIME,
                    language TEXT DEFAULT 'en',
                    interaction_count INTEGER DEFAULT 0
                )
            ''')
            
            # Create activity_log table for caregiver monitoring
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    memory_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    details TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS query_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    query_signature TEXT NOT NULL,
                    severity INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alert_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity INTEGER DEFAULT 1,
                    message TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    external_notify_at DATETIME
                )
            ''')
            for migration in [
                "ALTER TABLE alert_events ADD COLUMN external_notify_at DATETIME",
            ]:
                try:
                    cursor.execute(migration)
                except sqlite3.OperationalError:
                    pass
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trusted_inbound_messages (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    from_contact TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_read INTEGER DEFAULT 0
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS doctor_reports (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS one_time_codes (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    expires_at DATETIME NOT NULL,
                    consumed BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS face_profiles (
                    user_id TEXT PRIMARY KEY,
                    embedding_base64 TEXT NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def encrypt_text(self, text: str) -> bytes:
        """Encrypt text using Fernet"""
        return FERNET_CIPHER.encrypt(text.encode())
    
    def decrypt_text(self, encrypted_text: bytes) -> str:
        """Decrypt text using Fernet"""
        return FERNET_CIPHER.decrypt(encrypted_text).decode()
    
    def add_memory(self, text: str, source: str, tags: List[str] = None,
                   language: str = "en", user_id: str = None, source_modality: str = "text",
                   importance: float = 0.5) -> str:
        """Add a new memory to the database"""
        memory_id = str(uuid.uuid4())
        encrypted_text = self.encrypt_text(text)
        encrypted_tags = self.encrypt_text(json.dumps(tags or []))
        
        # Extract relative dates from text
        from date_utils import date_extractor
        date_result = date_extractor.extract_relative_dates(text)
        date_mentions = json.dumps({
            'found_dates': date_result['found_dates'],
            'converted_dates': date_result['converted_dates']
        }) if date_result['has_relative_dates'] else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO memories 
                (id, user_id, text_encrypted, timestamp, source, tags_encrypted, 
                 language, caregiver_confirmed, date_mentions, source_modality, importance, reinforcement_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (memory_id, user_id, encrypted_text, datetime.now(), source,
                  encrypted_tags, language, False, date_mentions, source_modality, importance, 0))
            conn.commit()
        
        return memory_id
    
    def get_memory(self, memory_id: str) -> Optional[Dict]:
        """Retrieve a memory by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM memories WHERE id = ?', (memory_id,))
            row = cursor.fetchone()
            
            if row:
                date_mentions = None
                if row['date_mentions']:
                    try:
                        date_mentions = json.loads(row['date_mentions'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                return {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'text': self.decrypt_text(row['text_encrypted']),
                    'timestamp': row['timestamp'],
                    'source': row['source'],
                    'tags': json.loads(self.decrypt_text(row['tags_encrypted'])),
                    'language': row['language'],
                    'caregiver_confirmed': bool(row['caregiver_confirmed']),
                    'source_modality': row['source_modality'],
                    'importance': float(row['importance'] or 0.5),
                    'reinforcement_count': int(row['reinforcement_count'] or 0),
                    'created_at': row['created_at'],
                    'date_mentions': date_mentions
                }
            return None
    
    def get_all_memories(self, language: str = None, user_id: str = None) -> List[Dict]:
        """Get all memories with optional filters"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM memories WHERE 1=1'
            params = []
            
            lang_clause, lang_params = _language_sql_filter(language)
            query += lang_clause
            params.extend(lang_params)
            if user_id:
                query += ' AND user_id = ?'
                params.append(user_id)
            
            
            query += ' ORDER BY created_at DESC'
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            memories = []
            for row in rows:
                date_mentions = None
                if row['date_mentions']:
                    try:
                        date_mentions = json.loads(row['date_mentions'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                memories.append({
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'text': self.decrypt_text(row['text_encrypted']),
                    'timestamp': row['timestamp'],
                    'source': row['source'],
                    'tags': json.loads(self.decrypt_text(row['tags_encrypted'])),
                    'language': row['language'],
                    'caregiver_confirmed': bool(row['caregiver_confirmed']),
                    'source_modality': row['source_modality'],
                    'importance': float(row['importance'] or 0.5),
                    'reinforcement_count': int(row['reinforcement_count'] or 0),
                    'created_at': row['created_at'],
                    'date_mentions': date_mentions
                })
            
            return memories
    
    def search_memories_by_date(self, target_date: str, language: str = None, user_id: str = None) -> List[Dict]:
        """Search memories that mention a specific date (including relative dates)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM memories 
                WHERE date_mentions IS NOT NULL
            '''
            params = []
            
            lang_clause, lang_params = _language_sql_filter(language)
            query += lang_clause
            params.extend(lang_params)
            if user_id:
                query += ' AND user_id = ?'
                params.append(user_id)
            
            query += ' ORDER BY created_at DESC'
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            matching_memories = []
            for row in rows:
                try:
                    date_mentions = json.loads(row['date_mentions'])
                    # Check if the target date is in the converted dates
                    if target_date in date_mentions.get('converted_dates', []):
                        date_mentions_data = date_mentions
                    else:
                        date_mentions_data = None
                    
                    if date_mentions_data:
                        matching_memories.append({
                            'id': row['id'],
                            'user_id': row['user_id'],
                            'text': self.decrypt_text(row['text_encrypted']),
                            'timestamp': row['timestamp'],
                            'source': row['source'],
                            'tags': json.loads(self.decrypt_text(row['tags_encrypted'])),
                            'language': row['language'],
                            'caregiver_confirmed': bool(row['caregiver_confirmed']),
                            'source_modality': row['source_modality'],
                            'importance': float(row['importance'] or 0.5),
                            'reinforcement_count': int(row['reinforcement_count'] or 0),
                            'created_at': row['created_at'],
                            'date_mentions': date_mentions_data
                        })
                except (json.JSONDecodeError, TypeError):
                    continue
            
            return matching_memories
    
    def update_memory_caregiver_confirmed(self, memory_id: str, 
                                         caregiver_confirmed: bool = True):
        """Update memory caregiver confirmation"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE memories 
                SET caregiver_confirmed = ?
                WHERE id = ?
            ''', (caregiver_confirmed, memory_id))
            conn.commit()
    
    def delete_memory(self, memory_id: str):
        """Delete a memory by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM memories WHERE id = ?', (memory_id,))
            conn.commit()

    def delete_memories_for_user(self, user_id: str) -> int:
        """Delete all memories belonging to one user. Returns rows deleted."""
        if not user_id:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM memories WHERE user_id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount

    def increment_memory_reinforcement(self, memory_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE memories SET reinforcement_count = COALESCE(reinforcement_count, 0) + 1 WHERE id = ?",
                (memory_id,),
            )
            conn.commit()
    
    def log_activity(self, user_id: str, action: str, memory_id: str = None, 
                    details: str = None):
        """Log user activity for caregiver monitoring"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO activity_log (user_id, action, memory_id, details)
                VALUES (?, ?, ?, ?)
            ''', (user_id, action, memory_id, details))
            conn.commit()
    
    def get_activity_log(self, user_id: str = None, limit: int = 100) -> List[Dict]:
        """Get activity log entries"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute('''
                    SELECT * FROM activity_log 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (user_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM activity_log 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def create_user(self, username: str, password_hash: str, role: str, full_name: str) -> str:
        user_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (id, username, password_hash, role, full_name) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, password_hash, role, full_name),
            )
            conn.commit()
        return user_id

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def upsert_trusted_contact(self, user_id: str, name: str, relation: str, contact: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trusted_contacts WHERE user_id = ?", (user_id,))
            cursor.execute(
                "INSERT INTO trusted_contacts (id, user_id, name, relation, contact) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, name, relation, contact),
            )
            conn.commit()

    def get_trusted_contact(self, user_id: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trusted_contacts WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def store_one_time_code(self, user_id: str, code: str, purpose: str, valid_minutes: int = 10):
        expires_at = datetime.now() + timedelta(minutes=valid_minutes)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO one_time_codes (id, user_id, code, purpose, expires_at, consumed) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, code, purpose, expires_at.isoformat(), False),
            )
            conn.commit()

    def verify_one_time_code(self, user_id: str, code: str, purpose: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM one_time_codes
                WHERE user_id = ? AND code = ? AND purpose = ? AND consumed = 0
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, code, purpose),
            )
            row = cursor.fetchone()
            if not row:
                return False
            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                return False
            cursor.execute("UPDATE one_time_codes SET consumed = 1 WHERE id = ?", (row["id"],))
            conn.commit()
            return True

    def store_face_embedding(self, user_id: str, embedding_base64: str, embedding_dim: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO face_profiles (user_id, embedding_base64, embedding_dim, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    embedding_base64=excluded.embedding_base64,
                    embedding_dim=excluded.embedding_dim,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (user_id, embedding_base64, embedding_dim),
            )
            conn.commit()

    def get_face_embedding(self, user_id: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM face_profiles WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def log_query_event(self, user_id: str, query_text: str, query_signature: str, severity: int = 1):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO query_events (id, user_id, query_text, query_signature, severity) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, query_text, query_signature, severity),
            )
            conn.commit()

    def get_recent_query_events(self, user_id: str, since_hours: int = 24) -> List[Dict]:
        cutoff = datetime.now() - timedelta(hours=since_hours)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM query_events WHERE user_id = ? AND created_at >= ? ORDER BY created_at DESC",
                (user_id, cutoff.isoformat()),
            )
            return [dict(r) for r in cursor.fetchall()]

    def create_alert(self, user_id: str, alert_type: str, message: str, severity: int = 1) -> str:
        alert_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO alert_events (id, user_id, alert_type, severity, message) VALUES (?, ?, ?, ?, ?)",
                (alert_id, user_id, alert_type, severity, message),
            )
            conn.commit()
        return alert_id

    def has_open_alert(self, user_id: str, alert_type: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM alert_events
                WHERE user_id = ? AND alert_type = ? AND status = 'open' LIMIT 1
                """,
                (user_id, alert_type),
            )
            return cursor.fetchone() is not None

    def has_recent_alert(
        self, user_id: str, alert_type: str, hours: float = 12, status: str = None
    ) -> bool:
        cutoff = datetime.now() - timedelta(hours=hours)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    """
                    SELECT created_at FROM alert_events
                    WHERE user_id = ? AND alert_type = ? AND status = ?
                    ORDER BY created_at DESC LIMIT 8
                    """,
                    (user_id, alert_type, status),
                )
            else:
                cursor.execute(
                    """
                    SELECT created_at FROM alert_events
                    WHERE user_id = ? AND alert_type = ?
                    ORDER BY created_at DESC LIMIT 8
                    """,
                    (user_id, alert_type),
                )
            for row in cursor.fetchall():
                raw = row["created_at"]
                if not raw:
                    continue
                try:
                    dt = datetime.fromisoformat(str(raw).replace(" ", "T", 1))
                except ValueError:
                    continue
                if dt >= cutoff:
                    return True
            return False

    def mark_alert_external_notified(self, alert_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE alert_events SET external_notify_at = ? WHERE id = ?",
                (datetime.now().isoformat(), alert_id),
            )
            conn.commit()

    def get_open_unnotified_alert(self, user_id: str, alert_type: str) -> Optional[Dict]:
        """Oldest open alert of this type that never had a successful external notify (retry path)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM alert_events
                WHERE user_id = ? AND alert_type = ? AND status = 'open'
                  AND (external_notify_at IS NULL OR TRIM(COALESCE(external_notify_at, '')) = '')
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (user_id, alert_type),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_trusted_inbound_message(self, user_id: str, body: str, from_contact: str = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO trusted_inbound_messages (id, user_id, body, from_contact)
                VALUES (?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), user_id, body, from_contact),
            )
            conn.commit()

    def get_trusted_inbound_messages(self, user_id: str, unread_only: bool = False, limit: int = 20) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if unread_only:
                cursor.execute(
                    """
                    SELECT * FROM trusted_inbound_messages
                    WHERE user_id = ? AND is_read = 0
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (user_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM trusted_inbound_messages
                    WHERE user_id = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (user_id, limit),
                )
            return [dict(r) for r in cursor.fetchall()]

    def mark_trusted_inbound_read(self, user_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE trusted_inbound_messages SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                (user_id,),
            )
            conn.commit()

    def find_user_ids_by_trusted_phone(self, phone_digits: str) -> List[str]:
        """Match trusted_contacts.contact using normalized last-10-digit heuristic."""
        target = "".join(c for c in (phone_digits or "") if c.isdigit())
        if len(target) >= 10:
            target = target[-10:]
        if len(target) < 10:
            return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, contact FROM trusted_contacts")
            matched = []
            for row in cursor.fetchall():
                c = "".join(ch for ch in (row["contact"] or "") if ch.isdigit())
                if len(c) >= 10 and c[-10:] == target:
                    matched.append(row["user_id"])
            return matched

    def get_alerts(self, user_id: str = None, status: str = "open") -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT * FROM alert_events WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                    (user_id, status),
                )
            else:
                cursor.execute(
                    "SELECT * FROM alert_events WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
            return [dict(r) for r in cursor.fetchall()]

    def mark_alert_resolved(self, alert_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE alert_events SET status = 'resolved' WHERE id = ?", (alert_id,))
            conn.commit()

    def get_last_activity(self, user_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT timestamp FROM activity_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
                (user_id,),
            )
            row = cursor.fetchone()
            return row["timestamp"] if row else None

    def save_doctor_report(self, user_id: str, report_date: str, summary: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO doctor_reports (id, user_id, report_date, summary) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, report_date, summary),
            )
            conn.commit()

    def get_latest_doctor_report(self, user_id: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM doctor_reports WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
