import sqlite3
import os

def init_db():
    db_path = "youtube_pipeline.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Schema 1: Channel trends and keywords
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE,
            channel_data TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Schema 2: Project State Machine
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL,
            -- States: 'TREND_FOUND', 'ASSETS_DOWNLOADING', 'EDITING', 'METADATA_GENERATION', 'UPLOADED', 'TRASHED'
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Schema 3: Verification Log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            step TEXT NOT NULL,
            status TEXT NOT NULL, -- 'GOOD' or 'BAD'
            score REAL,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES project_states (project_id)
        )
    """)

    conn.commit()
    conn.close()
    return db_path

def get_connection():
    return sqlite3.connect("youtube_pipeline.db")

def update_project_state(project_id: str, new_state: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO project_states (project_id, state)
        VALUES (?, ?)
        ON CONFLICT(project_id) DO UPDATE SET state=excluded.state, last_updated=CURRENT_TIMESTAMP
    """, (project_id, new_state))
    conn.commit()
    conn.close()

def log_verification(project_id: str, step: str, status: str, score: float = 0.0, details: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO verification_logs (project_id, step, status, score, details)
        VALUES (?, ?, ?, ?, ?)
    """, (project_id, step, status, score, details))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
