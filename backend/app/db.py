from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import GenerationStatus, MessageRole


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    generation_id TEXT REFERENCES generations(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    prompt TEXT NOT NULL,
    assistant_summary TEXT,
    script_path TEXT,
    step_path TEXT,
    glb_path TEXT,
    stl_path TEXT,
    native_path TEXT,
    log_path TEXT,
    error TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
    ON messages(conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_generations_conversation_created
    ON generations(conversation_id, created_at);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


class SQLiteRepository:
    def __init__(self, database_path: Path | str):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            _ensure_column(conn, "generations", "stl_path", "TEXT")
            _ensure_column(conn, "generations", "native_path", "TEXT")

    def create_conversation(self, title: str | None = None) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": new_id("conv"),
            "title": title or "Untitled design",
            "created_at": now,
            "updated_at": now,
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at)
                VALUES (:id, :title, :created_at, :updated_at)
                """,
                row,
            )
        return row

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        return row_to_dict(row)

    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, utc_now(), conversation_id),
            )

    def touch_conversation(self, conversation_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (utc_now(), conversation_id),
            )

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        generation_id: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": new_id("msg"),
            "conversation_id": conversation_id,
            "role": role.value,
            "content": content,
            "generation_id": generation_id,
            "created_at": utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, role, content, generation_id, created_at
                )
                VALUES (
                    :id, :conversation_id, :role, :content, :generation_id, :created_at
                )
                """,
                row,
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (row["created_at"], conversation_id),
            )
        return row

    def create_generation(self, conversation_id: str, prompt: str) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": new_id("gen"),
            "conversation_id": conversation_id,
            "status": GenerationStatus.queued.value,
            "prompt": prompt,
            "assistant_summary": None,
            "script_path": None,
            "step_path": None,
            "glb_path": None,
            "stl_path": None,
            "native_path": None,
            "log_path": None,
            "error": None,
            "attempt_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO generations (
                    id, conversation_id, status, prompt, assistant_summary,
                    script_path, step_path, glb_path, stl_path, native_path,
                    log_path, error,
                    attempt_count, created_at, updated_at
                )
                VALUES (
                    :id, :conversation_id, :status, :prompt, :assistant_summary,
                    :script_path, :step_path, :glb_path, :stl_path, :native_path,
                    :log_path, :error,
                    :attempt_count, :created_at, :updated_at
                )
                """,
                row,
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        return row

    def get_generation(self, generation_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM generations WHERE id = ?",
                (generation_id,),
            ).fetchone()
        return row_to_dict(row)

    def list_generations(self, conversation_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM generations
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_generation(self, generation_id: str, **fields: Any) -> dict[str, Any]:
        allowed = {
            "status",
            "assistant_summary",
            "script_path",
            "step_path",
            "glb_path",
            "stl_path",
            "native_path",
            "log_path",
            "error",
            "attempt_count",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = :{key}" for key in updates)
        params = {**updates, "id": generation_id}
        with self.connect() as conn:
            conn.execute(
                f"UPDATE generations SET {assignments} WHERE id = :id",
                params,
            )
        generation = self.get_generation(generation_id)
        if generation is None:
            raise KeyError(f"Generation not found: {generation_id}")
        return generation


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
