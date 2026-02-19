import sqlite3
from app.config import settings

def init_db():
    conn = sqlite3.connect(settings.sqlite_path)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        persona_config TEXT
    )
    ''')
    
    # Create conversations table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        message TEXT,
        role TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')

    # Create weekly summaries table (L1)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS weekly_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        week_start DATE,
        summary TEXT,
        key_events TEXT, -- JSON string
        emotional_trend TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')

    # Create monthly summaries table (L2)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS monthly_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        month_start DATE,
        summary TEXT,
        key_events TEXT, -- JSON string
        emotional_trend TEXT,
        relationship_milestone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')

    # Create yearly summaries table (L3)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS yearly_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        year_start DATE,
        summary TEXT,
        key_events TEXT, -- JSON string
        emotional_trend TEXT,
        relationship_milestone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')

    # Create memory timeline table for hybrid retrieval
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS memory_timeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        date_key DATE,
        memory_id TEXT,
        layer INTEGER,
        importance REAL DEFAULT 0.5,
        entities TEXT, -- JSON array of entities
        content_preview TEXT, -- Optional: for quick preview
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create system_state table to track shutdown/startup times
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_state (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn
