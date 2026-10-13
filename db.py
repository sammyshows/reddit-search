import logging
import sqlite3
import threading

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_posts (
    id TEXT PRIMARY KEY,
    title TEXT,
    subreddit TEXT,
    score INTEGER,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, db_path: str = "radar_cache.db"):
        self._db_path = db_path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(_SCHEMA)
        self.conn.commit()

    def is_post_processed(self, post_id: str) -> bool:
        with self._lock:
            cur = self.conn.execute(
                "SELECT 1 FROM processed_posts WHERE id = ?", (post_id,)
            )
            return cur.fetchone() is not None

    def record_post(self, post_id: str, title: str, subreddit: str, score: int) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO processed_posts (id, title, subreddit, score) "
                "VALUES (?, ?, ?, ?)",
                (post_id, title, subreddit, score),
            )
            self.conn.commit()

    def prune_old_records(self, days: int = 30) -> int:
        with self._lock:
            cur = self.conn.execute(
                "DELETE FROM processed_posts "
                "WHERE processed_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            self.conn.commit()
            pruned = cur.rowcount
            log.info("Pruned %d record(s) older than %d day(s)", pruned, days)
            return pruned

    def close(self) -> None:
        with self._lock:
            self.conn.close()