"""
Database management for Dementia Chatbot
"""
import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from config import DATABASE_PATH, FERNET_CIPHER

class MemoryDatabase:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create memories table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    text_encrypted BLOB NOT NULL,
                    timestamp DATETIME NOT NULL,
                    source TEXT NOT NULL,
                    tags_encrypted BLOB,
                    language TEXT DEFAULT 'en',
                    caregiver_confirmed BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add date_mentions column if it doesn't exist (migration)
            try:
                cursor.execute('ALTER TABLE memories ADD COLUMN date_mentions TEXT')
            except sqlite3.OperationalError:
                # Column already exists
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
            
            conn.commit()
    
    def encrypt_text(self, text: str) -> bytes:
        """Encrypt text using Fernet"""
        return FERNET_CIPHER.encrypt(text.encode())
    
    def decrypt_text(self, encrypted_text: bytes) -> str:
        """Decrypt text using Fernet"""
        return FERNET_CIPHER.decrypt(encrypted_text).decode()
    
    def add_memory(self, text: str, source: str, tags: List[str] = None, 
                   language: str = "en") -> str:
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
                (id, text_encrypted, timestamp, source, tags_encrypted, 
                 language, caregiver_confirmed, date_mentions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (memory_id, encrypted_text, datetime.now(), source, 
                  encrypted_tags, language, False, date_mentions))
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
                    'text': self.decrypt_text(row['text_encrypted']),
                    'timestamp': row['timestamp'],
                    'source': row['source'],
                    'tags': json.loads(self.decrypt_text(row['tags_encrypted'])),
                    'language': row['language'],
                    'caregiver_confirmed': bool(row['caregiver_confirmed']),
                    'created_at': row['created_at'],
                    'date_mentions': date_mentions
                }
            return None
    
    def get_all_memories(self, language: str = None) -> List[Dict]:
        """Get all memories with optional filters"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM memories WHERE 1=1'
            params = []
            
            if language:
                query += ' AND language = ?'
                params.append(language)
            
            
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
                    'text': self.decrypt_text(row['text_encrypted']),
                    'timestamp': row['timestamp'],
                    'source': row['source'],
                    'tags': json.loads(self.decrypt_text(row['tags_encrypted'])),
                    'language': row['language'],
                    'caregiver_confirmed': bool(row['caregiver_confirmed']),
                    'created_at': row['created_at'],
                    'date_mentions': date_mentions
                })
            
            return memories
    
    def search_memories_by_date(self, target_date: str, language: str = None) -> List[Dict]:
        """Search memories that mention a specific date (including relative dates)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM memories 
                WHERE date_mentions IS NOT NULL
            '''
            params = []
            
            if language:
                query += ' AND language = ?'
                params.append(language)
            
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
                            'text': self.decrypt_text(row['text_encrypted']),
                            'timestamp': row['timestamp'],
                            'source': row['source'],
                            'tags': json.loads(self.decrypt_text(row['tags_encrypted'])),
                            'language': row['language'],
                            'caregiver_confirmed': bool(row['caregiver_confirmed']),
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
