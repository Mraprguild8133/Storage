import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path="files.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE,
                file_name TEXT,
                file_size INTEGER,
                wasabi_key TEXT,
                telegram_file_id TEXT,
                mime_type TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_file(self, file_data):
        """Add file record to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO files 
                (file_id, file_name, file_size, wasabi_key, telegram_file_id, mime_type, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_data['file_id'],
                file_data['file_name'],
                file_data['file_size'],
                file_data.get('wasabi_key'),
                file_data.get('telegram_file_id'),
                file_data.get('mime_type'),
                file_data.get('user_id')
            ))
            
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"File ID {file_data['file_id']} already exists")
            return False
        finally:
            conn.close()
    
    def get_file(self, file_id):
        """Get file record by file_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM files WHERE file_id = ?
        ''', (file_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'file_id': result[1],
                'file_name': result[2],
                'file_size': result[3],
                'wasabi_key': result[4],
                'telegram_file_id': result[5],
                'mime_type': result[6],
                'upload_date': result[7],
                'user_id': result[8]
            }
        return None
    
    def list_files(self, user_id=None, limit=50):
        """List files with optional user filter"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT * FROM files WHERE user_id = ? ORDER BY upload_date DESC LIMIT ?
            ''', (user_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM files ORDER BY upload_date DESC LIMIT ?
            ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        files = []
        for result in results:
            files.append({
                'id': result[0],
                'file_id': result[1],
                'file_name': result[2],
                'file_size': result[3],
                'wasabi_key': result[4],
                'telegram_file_id': result[5],
                'mime_type': result[6],
                'upload_date': result[7],
                'user_id': result[8]
            })
        
        return files
    
    def delete_file(self, file_id):
        """Delete file record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM files WHERE file_id = ?', (file_id,))
        conn.commit()
        conn.close()
        
        return cursor.rowcount > 0

# Global instance
db = Database()
