"""
Database module for Provenance Guard

Handles SQLite initialization, schema creation, and audit logging.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DATABASE_PATH = Path(__file__).parent.parent / "database.db"


def init_database():
    """Initialize SQLite database with audit log table."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Create audit_log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            content_id TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            text_hash TEXT,
            signal_1_score REAL NOT NULL,
            signal_2_score REAL NOT NULL,
            final_confidence REAL NOT NULL,
            classification TEXT NOT NULL,
            label TEXT NOT NULL,
            source_ip TEXT,
            appeal_status TEXT DEFAULT 'none'
        )
    """)

    conn.commit()
    conn.close()


def log_classification(
    content_id: str,
    creator_id: str,
    signal_1_score: float,
    signal_2_score: float,
    final_confidence: float,
    classification: str,
    label: str,
    source_ip: str = None,
    text_hash: str = None,
) -> dict:
    """
    Log a classification decision to the audit log.

    Args:
        content_id: Unique identifier for this submission
        creator_id: ID of the content creator
        signal_1_score: Groq semantic analyzer output (0.0-1.0)
        signal_2_score: Text statistics analyzer output (0.0-1.0)
        final_confidence: Combined confidence score (0.0-1.0)
        classification: Final classification ("ai", "human", "uncertain")
        label: Transparency label shown to user
        source_ip: IP address of requester
        text_hash: SHA-256 hash of text (for privacy)

    Returns:
        dict: The logged record
    """
    import uuid

    log_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    record = {
        "id": log_id,
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": timestamp,
        "text_hash": text_hash,
        "signal_1_score": round(signal_1_score, 2),
        "signal_2_score": round(signal_2_score, 2),
        "final_confidence": round(final_confidence, 2),
        "classification": classification,
        "label": label,
        "source_ip": source_ip,
        "appeal_status": "none",
    }

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO audit_log
        (id, content_id, creator_id, timestamp, text_hash, signal_1_score,
         signal_2_score, final_confidence, classification, label, source_ip, appeal_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log_id,
        record["content_id"],
        record["creator_id"],
        record["timestamp"],
        record["text_hash"],
        record["signal_1_score"],
        record["signal_2_score"],
        record["final_confidence"],
        record["classification"],
        record["label"],
        record["source_ip"],
        record["appeal_status"],
    ))

    conn.commit()
    conn.close()

    return record


def get_audit_log(limit: int = 100, offset: int = 0) -> dict:
    """
    Retrieve audit log records.

    Args:
        limit: Number of records to return (max 500)
        offset: Pagination offset

    Returns:
        dict: {"total": count, "limit": limit, "offset": offset, "records": [...]}
    """
    limit = min(limit, 500)
    offset = max(offset, 0)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get total count
    cursor.execute("SELECT COUNT(*) as count FROM audit_log")
    total = cursor.fetchone()["count"]

    # Get records
    cursor.execute("""
        SELECT * FROM audit_log
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))

    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": records,
    }
