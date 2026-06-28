"""
Provenance Guard: AI Content Classification Service

Architecture Flow (Flow 1: Text Submission):
  User/Client
      ↓ POST /submit {"text": "...", "creator_id": "..."}
  Flask API Server
      ↓ (text, creator_id, source_ip)
  Rate Limiter (10 req/min per IP)
      ├─ On limit exceeded → 429 error
      └─ On pass → continue
      ↓ (text, creator_id, source_ip)
  Input Validator
      ├─ Check length (10-10k chars)
      ├─ Validate UTF-8
      ├─ Validate creator_id (non-empty)
      └─ Generate content_id (UUID)
      ├─ On invalid → 400/413 error
      └─ On valid → continue
      ↓ (text, creator_id, content_id)
  Multi-Signal Pipeline (parallel)
      ├─ Signal 1: Text Statistics → stat_score (0-1)
      └─ Signal 2: Groq API → semantic_score (0-1)
      ↓ (0.0-1.0 scores)
  Confidence Scorer (ensemble)
      ↓ final_confidence = (0.70 × semantic) + (0.30 × stat)
  Label Generator
      ├─ <0.20 → "AI-generated content"
      ├─ 0.20-0.80 → "uncertain"
      └─ >0.80 → "written by a human"
      ↓ (label_text)
  API Response
      └─ JSON: {content_id, creator_id, classification, confidence, label, signals}
"""

import json
import uuid
import sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from detection.text_stats import calculate_text_statistics
from detection.groq_analyzer import analyze_semantic
from detection.scorer import score_confidence
from labels.generator import generate_label


app = Flask(__name__)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["10 per minute"],
    storage_uri="memory://"
)

# SQLite audit log database
DB_PATH = "audit_log.db"

def init_db():
    """Initialize SQLite database with audit_log and appeals tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            content_id TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            signal_1_score REAL NOT NULL,
            signal_2_score REAL NOT NULL,
            final_confidence REAL NOT NULL,
            classification TEXT NOT NULL,
            label TEXT NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appeals (
            id TEXT PRIMARY KEY,
            content_id TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            creator_reasoning TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def log_to_audit(content_id, creator_id, signal_1_score, signal_2_score, final_confidence, classification, label, status="classified"):
    """Write structured entry to SQLite audit log with both signals."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry_id = str(uuid.uuid4())

    cursor.execute('''
        INSERT INTO audit_log
        (id, content_id, creator_id, timestamp, signal_1_score, signal_2_score, final_confidence, classification, label, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (entry_id, content_id, creator_id, timestamp, signal_1_score, signal_2_score, final_confidence, classification, label, status))

    conn.commit()
    conn.close()

def get_log(limit=10):
    """Retrieve most recent audit log entries as dictionaries."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, content_id, creator_id, timestamp, signal_1_score, signal_2_score,
               final_confidence, classification, label, status
        FROM audit_log
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    # Convert rows to list of dictionaries
    entries = [dict(row) for row in rows]
    return entries

# Initialize database on startup
init_db()


def validate_and_prepare(data):
    """
    Input Validator: Validate text and creator_id, generate content_id.

    Args:
        data: Request JSON data

    Returns:
        tuple: (text, creator_id, content_id) if valid
        tuple: (None, None, None, error_dict) if invalid
    """
    if not data or 'text' not in data:
        return None, None, None, {"error": "Missing 'text' field", "code": 400}

    if not data or 'creator_id' not in data:
        return None, None, None, {"error": "Missing 'creator_id' field", "code": 400}

    text = data['text']
    creator_id = data['creator_id']

    # Validate text type
    if not isinstance(text, str):
        return None, None, None, {"error": "Text must be a string", "code": 400}

    # Validate creator_id type
    if not isinstance(creator_id, str) or not creator_id.strip():
        return None, None, None, {"error": "Creator_id must be a non-empty string", "code": 400}

    # Validate text length
    if len(text) < 10:
        return None, None, None, {"error": "Text must be at least 10 characters", "code": 400}
    if len(text) > 10000:
        return None, None, None, {"error": "Text must not exceed 10,000 characters", "code": 413}

    # Validate content (not just whitespace)
    if not text.strip():
        return None, None, None, {"error": "Text cannot be only whitespace", "code": 400}

    # Generate content ID
    content_id = str(uuid.uuid4())

    return text, creator_id, content_id, None




@app.route('/submit', methods=['POST'])
@limiter.limit("10 per minute")
def submit():
    """
    POST /submit: Submit text for AI/human classification.

    Request:
        POST /submit
        {"text": "...", "creator_id": "user-123"}

    Response (200 OK):
        {
            "content_id": "uuid",
            "creator_id": "user-123",
            "classification": "human|ai|uncertain",
            "confidence": 0.0-1.0,
            "label": "transparency text",
            "signals": {
                "signal_1": 0.0-1.0,
                "signal_2": 0.0-1.0
            }
        }

    Errors:
        400: Invalid input (missing fields, text too short, non-string, whitespace-only)
        413: Text exceeds 10,000 characters
        429: Rate limit exceeded (10 per minute per IP)
        500: Server error
    """
    try:
        # Get request data
        data = request.get_json()

        # Input Validator: Validate and prepare
        text, creator_id, content_id, error = validate_and_prepare(data)
        if error:
            return jsonify({"error": error["error"]}), error["code"]

        # Signal 1: Groq Semantic Analysis (70% weight)
        signal_1_score = analyze_semantic(text)

        # Signal 2: Text Statistics (30% weight)
        signal_2_score = calculate_text_statistics(text)

        # Confidence Scorer: Combine signals via weighted ensemble
        final_confidence = score_confidence(signal_1_score, signal_2_score)

        # Label Generator: Map confidence to transparency text
        label_result = generate_label(final_confidence)
        classification = label_result["classification"]
        label = label_result["label"]

        # Log to audit database with both signals
        log_to_audit(
            content_id=content_id,
            creator_id=creator_id,
            signal_1_score=signal_1_score,
            signal_2_score=signal_2_score,
            final_confidence=final_confidence,
            classification=classification,
            label=label,
            status="classified"
        )

        # Build response with both signal scores and final confidence
        response = {
            "content_id": content_id,
            "creator_id": creator_id,
            "classification": classification,
            "confidence": round(final_confidence, 2),
            "label": label,
            "signals": {
                "signal_1": round(signal_1_score, 2),
                "signal_2": round(signal_2_score, 2)
            }
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/log', methods=['GET'])
def log():
    """
    GET /log: Retrieve recent audit log entries with both signal scores.

    Query Parameters:
        limit (optional, default=10, max=100): Number of entries to return

    Response (200 OK):
        {
            "entries": [
                {
                    "id": "uuid",
                    "content_id": "uuid",
                    "creator_id": "user-123",
                    "timestamp": "2026-06-27T22:03:36.000636Z",
                    "signal_1_score": 0.90,
                    "signal_2_score": 0.85,
                    "final_confidence": 0.88,
                    "classification": "human",
                    "label": "This appears to be written by a human",
                    "status": "classified"
                },
                ...
            ]
        }
    """
    try:
        # Get limit from query parameters (default 10, max 100)
        limit = request.args.get('limit', default=10, type=int)
        limit = min(limit, 100)  # Cap at 100 for safety
        limit = max(limit, 1)    # Minimum 1

        entries = get_log(limit=limit)
        return jsonify({"entries": entries}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/appeals', methods=['POST'])
@limiter.limit("10 per minute")
def appeal():
    """
    POST /appeals: Submit an appeal for a classification decision.

    Request:
        POST /appeals
        {
            "content_id": "uuid",
            "creator_id": "user-123",
            "creator_reasoning": "This is my original work..."
        }

    Response (200 OK):
        {
            "appeal_id": "uuid",
            "content_id": "uuid",
            "creator_id": "user-123",
            "status": "under_review",
            "message": "Your appeal has been received and logged..."
        }

    Errors:
        400: Invalid input (missing fields, reasoning too short/long, creator_id mismatch)
        404: content_id doesn't exist in database
        429: Rate limit exceeded
        500: Server error
    """
    try:
        data = request.get_json()

        # Validate required fields
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        content_id = data.get('content_id')
        creator_id = data.get('creator_id')
        creator_reasoning = data.get('creator_reasoning')

        # Validate content_id
        if not content_id or not isinstance(content_id, str):
            return jsonify({"error": "Missing or invalid 'content_id' field"}), 400

        # Validate creator_id
        if not creator_id or not isinstance(creator_id, str):
            return jsonify({"error": "Missing or invalid 'creator_id' field"}), 400

        # Validate creator_reasoning
        if not creator_reasoning or not isinstance(creator_reasoning, str):
            return jsonify({"error": "Missing 'creator_reasoning' field"}), 400

        creator_reasoning = creator_reasoning.strip()
        if len(creator_reasoning) < 20:
            return jsonify({"error": "creator_reasoning must be at least 20 characters"}), 400
        if len(creator_reasoning) > 2000:
            return jsonify({"error": "creator_reasoning must not exceed 2,000 characters"}), 400

        # Query database to verify content_id exists and creator_id matches
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT creator_id, status FROM audit_log WHERE content_id = ?
        ''', (content_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "content_id not found in database"}), 404

        # Verify creator_id matches
        original_creator_id = row['creator_id']
        if original_creator_id != creator_id:
            conn.close()
            return jsonify({"error": "creator_id does not match original submission"}), 400

        # Update the status of the original audit_log entry to "under_review"
        cursor.execute('''
            UPDATE audit_log SET status = ? WHERE content_id = ?
        ''', ("under_review", content_id))

        # Create appeal record
        appeal_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        cursor.execute('''
            INSERT INTO appeals
            (id, content_id, creator_id, creator_reasoning, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (appeal_id, content_id, creator_id, creator_reasoning, timestamp, "under_review"))

        conn.commit()
        conn.close()

        # Return success response
        response = {
            "appeal_id": appeal_id,
            "content_id": content_id,
            "creator_id": creator_id,
            "status": "under_review",
            "message": "Your appeal has been received and logged. A human reviewer will examine your case."
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded."""
    return jsonify({"error": "Rate limit exceeded: 10 requests per minute per IP"}), 429


if __name__ == '__main__':
    app.run(debug=True, port=5000)
