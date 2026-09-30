"""Durable latest snapshots plus per-partition idempotency checkpoints."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


class SnapshotStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots (
                kind TEXT, trajectory TEXT, body TEXT NOT NULL,
                received_at TEXT NOT NULL, updated INTEGER NOT NULL,
                PRIMARY KEY(kind, trajectory));
            CREATE TABLE IF NOT EXISTS checkpoints (
                topic TEXT, partition INTEGER, offset INTEGER,
                PRIMARY KEY(topic, partition));
        """)

    def put(self, kind, topic, partition, offset, payload):
        # Commit SQLite before the Kafka offset. A crash between them is safely
        # replayed, without changing the receipt timestamp of a duplicate.
        with self.lock, self.db:
            previous = self.db.execute(
                "SELECT offset FROM checkpoints WHERE topic=? AND partition=?", (topic, partition)
            ).fetchone()
            if previous and offset <= previous[0]:
                return False
            now = datetime.now(timezone.utc).isoformat()
            update = self.db.execute("SELECT COALESCE(MAX(updated),0)+1 FROM snapshots").fetchone()[0]
            self.db.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?)", (
                kind, payload['trajectory_key'], json.dumps(payload, allow_nan=False), now, update,
            ))
            self.db.execute("INSERT OR REPLACE INTO checkpoints VALUES (?,?,?)", (topic, partition, offset))
            return True

    def latest(self, kind, trajectory=None):
        with self.lock:
            query = "SELECT body, received_at FROM snapshots WHERE kind=?"
            params = [kind]
            if trajectory:
                query += " AND trajectory=?"
                params.append(trajectory)
            row = self.db.execute(query + " ORDER BY updated DESC LIMIT 1", params).fetchone()
            return (json.loads(row[0]), row[1]) if row else None

    def predictions(self):
        with self.lock:
            return [dict(prediction=json.loads(body), received_at=at) for body, at in self.db.execute(
                "SELECT body, received_at FROM snapshots WHERE kind='prediction' ORDER BY trajectory"
            )]

    def close(self):
        with self.lock:
            self.db.close()
