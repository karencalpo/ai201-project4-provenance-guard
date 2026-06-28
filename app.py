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


app = Flask(__name__)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["10 per minute"]
)

# SQLite audit log database
DB_PATH = "audit_log.db"

def init_db():
    """Initialize SQLite database with audit_log table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            content_id TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            text_statistics_score REAL NOT NULL,
            llm_score REAL,
            attribution TEXT NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def log_to_audit(content_id, creator_id, text_statistics_score, attribution, confidence, status="classified"):
    """Write structured entry to SQLite audit log."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry_id = str(uuid.uuid4())

    cursor.execute('''
        INSERT INTO audit_log
        (id, content_id, creator_id, timestamp, text_statistics_score, llm_score, attribution, confidence, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (entry_id, content_id, creator_id, timestamp, text_statistics_score, None, attribution, confidence, status))

    conn.commit()
    conn.close()

def get_log(limit=10):
    """Retrieve most recent audit log entries as dictionaries."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, content_id, creator_id, timestamp, text_statistics_score, llm_score,
               attribution, confidence, status
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


def score_confidence(stat_score, semantic_score):
    """
    Confidence Scorer: Combine signals via weighted ensemble.

    Formula: final_confidence = (0.70 × semantic_score) + (0.30 × stat_score)

    Args:
        stat_score: Signal 1 output (0-1)
        semantic_score: Signal 2 output (0-1)

    Returns:
        float: Combined confidence score (0-1)
    """
    confidence = (0.70 * semantic_score) + (0.30 * stat_score)
    return round(min(1.0, max(0.0, confidence)), 2)


def generate_label(confidence):
    """
    Label Generator: Map confidence to transparency text (3 variants).

    Args:
        confidence: Score 0.0-1.0

    Returns:
        tuple: (classification, label_text)
    """
    if confidence < 0.20:
        return "ai", "This appears to be AI-generated content"
    elif confidence > 0.80:
        return "human", "This appears to be written by a human"
    else:
        return "uncertain", "We're uncertain about the origin of this content. It may be AI-generated or human-written."


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
            "attribution": 0.0-1.0,
            "confidence": 0.5,
            "label": "uncertain"
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

        # Signal 1: Text Statistics (fast, no external calls)
        text_statistics_score = calculate_text_statistics(text)

        # Derive attribution classification from text statistics score
        if text_statistics_score < 0.33:
            attribution = "likely_ai"
        elif text_statistics_score > 0.67:
            attribution = "likely_human"
        else:
            attribution = "uncertain"

        # Placeholder values for M3
        confidence = 0.5
        label = "uncertain"

        # Log to audit database
        log_to_audit(
            content_id=content_id,
            creator_id=creator_id,
            text_statistics_score=text_statistics_score,
            attribution=attribution,
            confidence=confidence,
            status="classified"
        )

        # Build response with Signal 1 attribution and placeholder confidence/label
        response = {
            "content_id": content_id,
            "creator_id": creator_id,
            "attribution": round(text_statistics_score, 2),
            "confidence": confidence,
            "label": label
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/log', methods=['GET'])
def log():
    """
    GET /log: Retrieve recent audit log entries.

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
                    "text_statistics_score": 0.90,
                    "llm_score": null,
                    "attribution": "likely_human",
                    "confidence": 0.5,
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


@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded."""
    return jsonify({"error": "Rate limit exceeded: 10 requests per minute per IP"}), 429


if __name__ == '__main__':
    app.run(debug=True, port=5000)
