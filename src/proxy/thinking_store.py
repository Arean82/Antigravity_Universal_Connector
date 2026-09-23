import json
import gzip
import sqlite3
import os
from typing import Optional, Dict, Any

THOUGHT_RAW_MAGIC = b"RAW1"
THOUGHT_GZIP_MAGIC = b"AGZ1"
MIN_GZIP_THOUGHT = 384

class ThinkingStore:
    """
    Stores and retrieves model reasoning / thinking blocks across multi-turn tool calling.
    Ported directly from src-tauri/src/proxy/thinking_store.rs and proxy_db.rs.
    """
    def __init__(self, db_path: str = "thinking_store.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS thinking_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_key TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            thought BLOB NOT NULL,
            signature TEXT,
            tool_ids TEXT NOT NULL,
            tool_names TEXT NOT NULL,
            visible TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            last_accessed INTEGER,
            primary_tool_id TEXT
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_seq ON thinking_records (session_key, id ASC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_tool ON thinking_records (session_key, primary_tool_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_sig ON thinking_records (session_key, signature)")
        conn.commit()
        conn.close()

    @staticmethod
    def pack_thought(s: str) -> bytes:
        data = s.encode('utf-8')
        if len(data) >= MIN_GZIP_THOUGHT:
            compressed = gzip.compress(data)
            if len(compressed) + len(THOUGHT_GZIP_MAGIC) < len(data):
                return THOUGHT_GZIP_MAGIC + compressed
        return THOUGHT_RAW_MAGIC + data

    @staticmethod
    def unpack_thought(packed: bytes) -> str:
        if packed.startswith(THOUGHT_GZIP_MAGIC):
            return gzip.decompress(packed[len(THOUGHT_GZIP_MAGIC):]).decode('utf-8', errors='ignore')
        if packed.startswith(THOUGHT_RAW_MAGIC):
            return packed[len(THOUGHT_RAW_MAGIC):].decode('utf-8', errors='ignore')
        return packed.decode('utf-8', errors='ignore')

    def store_thought(self, session_key: str, fingerprint: str, thought: str,
                      signature: Optional[str] = None, tool_ids: list = None,
                      tool_names: list = None, visible: str = "") -> int:
        packed = self.pack_thought(thought)
        primary_tool = tool_ids[0] if tool_ids else None
        now = int(os.times().system)

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO thinking_records 
        (session_key, fingerprint, thought, signature, tool_ids, tool_names, visible, created_at, last_accessed, primary_tool_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_key, fingerprint, packed, signature, json.dumps(tool_ids or []),
              json.dumps(tool_names or []), visible, now, now, primary_tool))
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def get_thought_by_tool_id(self, session_key: str, tool_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        SELECT thought, signature FROM thinking_records
        WHERE session_key = ? AND primary_tool_id = ?
        ORDER BY id DESC LIMIT 1
        """, (session_key, tool_id))
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "thought": self.unpack_thought(row[0]),
                "signature": row[1]
            }
        return None
