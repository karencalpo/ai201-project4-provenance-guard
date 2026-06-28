# Provenance Guard: AI Content Detection Service

An API service that classifies text content as AI-generated or human-written, providing confidence scores and transparency labels for platforms and readers.

## System Overview

Provenance Guard uses a **multi-signal detection pipeline** with weighted ensemble scoring:
- **Signal 1 (Groq Semantic):** 70% weight - Detects corporate jargon, false balance, vague phrases, formulaic reasoning
- **Signal 2 (Text Statistics):** 30% weight - Detects personal markers, emotional language, repetitive patterns
- **Confidence Score:** Combined via weighted ensemble: `(0.70 × signal_1) + (0.30 × signal_2)`
- **Classification:** Maps confidence to three transparency labels (AI-generated, Uncertain, Human-written)

## Installation & Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Load environment variables from .env file
# The .env file should contain: GROQ_API_KEY=<your-api-key>
source .env

# Run the Flask server
python3 app.py
```

The server will start on `http://localhost:5000`.

## Rate Limiting

### Configuration

The service implements **rate limiting** on all POST endpoints to protect against abuse while supporting realistic user workflows:

```python
Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["10 per minute"],
    storage_uri="memory://"
)
```

### Limits

- **Endpoints:** POST /submit, POST /appeals
- **Limit:** 10 requests per minute per IP address
- **Response Code:** 429 Too Many Requests when exceeded

### Reasoning for 10 Requests/Minute

**Why this limit is defensible:**
- **Writer submission:** A typical writer submitting their own work = 1-2 submissions per minute (well within limit)
- **Editorial workflow:** An editor reviewing content might submit 5-10 pieces per hour (sustainable, ~0.08-0.17 req/sec)
- **API fairness:** One request every 6 seconds allows human-paced workflows
- **Abuse prevention:** Blocks automated scrapers/bots (which typically attempt 100s-1000s req/min)
- **Industry standard:** Comparable to rate limits on GPT API (3 req/min for free tier), Perspective API (1 req/sec), and other content classification services

**Who this blocks:**
- Automated scrapers: ❌ Would need 10,000+ minutes to check 100,000 texts
- Malicious clients: ❌ Cannot flood system with high-volume requests
- Legitimate users: ✅ Can classify multiple documents per minute as needed

### Testing Rate Limiting

Run this command in a terminal while the Flask server is running. It sends 12 rapid requests (exceeding the 10/minute limit):

```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
```

**Expected Output:**
```
200
200
200
200
200
200
200
200
200
200
429
429
```

The first 10 requests return **200 OK**, and requests 11-12 return **429 Too Many Requests**, confirming rate limiting is working correctly.

---

## API Endpoints

### POST /submit
Submit text for AI/human classification.

**Request:**
```json
{
  "text": "The content to analyze...",
  "creator_id": "user-12345"
}
```

**Response (200 OK):**
```json
{
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "creator_id": "user-12345",
  "classification": "human",
  "confidence": 0.86,
  "label": "This appears to be written by a human",
  "signals": {
    "signal_1": 0.90,
    "signal_2": 0.78
  }
}
```

**Constraints:**
- `text`: 10-10,000 characters, UTF-8 encoded
- `creator_id`: non-empty string

**Thresholds:**
- confidence < 0.35 → classification: "ai"
- confidence 0.35-0.70 → classification: "uncertain"
- confidence > 0.70 → classification: "human"

**Rate Limit:** 10 per minute per IP
**Errors:** 
- 400 Bad Request (invalid input)
- 413 Payload Too Large (text > 10k chars)
- 429 Too Many Requests (rate limited)
- 500 Server Error

---

### POST /appeals
Appeal a classification decision.

**Request:**
```json
{
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "creator_id": "user-12345",
  "creator_reasoning": "This is my original work and I wrote it myself without AI assistance."
}
```

**Response (200 OK):**
```json
{
  "appeal_id": "appeal-uuid-001",
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "creator_id": "user-12345",
  "status": "under_review",
  "message": "Your appeal has been received and logged. A human reviewer will examine your case."
}
```

**Behavior:**
- Updates original submission status to "under_review"
- Logs appeal with creator reasoning
- Returns appeal_id for tracking

**Constraints:**
- `content_id`: must exist in database (from prior /submit call)
- `creator_id`: must match original submission's creator_id
- `creator_reasoning`: 20-2,000 characters

**Rate Limit:** 10 per minute per IP
**Errors:**
- 400 Bad Request (invalid input, reasoning too short/long, creator_id mismatch)
- 404 Not Found (content_id doesn't exist)
- 429 Too Many Requests (rate limited)
- 500 Server Error

---

### GET /log
Retrieve audit log of classifications and appeals.

**Query Parameters:**
- `limit` (optional, default=100, max=500): Number of records to return
- `offset` (optional, default=0): Pagination offset

**Response (200 OK):**
```json
{
  "entries": [
    {
      "id": "log-entry-uuid",
      "content_id": "550e8400-e29b-41d4-a716-446655440000",
      "creator_id": "user-123",
      "timestamp": "2026-06-28T03:31:11.945205Z",
      "signal_1_score": 0.90,
      "signal_2_score": 0.78,
      "final_confidence": 0.8625,
      "classification": "human",
      "label": "This appears to be written by a human",
      "status": "classified"
    }
  ]
}
```

**Rate Limit:** 30 per minute per IP (more relaxed for read-only operations)

---

## Database

SQLite database (`audit_log.db`) stores:
- **audit_log:** Classification decisions with both signal scores, timestamps, and appeal status
- **appeals:** Appeal records linked to original submissions by content_id

Schema is created automatically on startup via `init_db()`.

### Audit Log Fields

Each audit log entry captures:
- `id` - Unique identifier for the log entry
- `content_id` - Unique content submission ID (UUID)
- `creator_id` - Creator identifier
- `timestamp` - ISO-8601 format (UTC)
- `signal_1_score` - Groq semantic analyzer result (0.0-1.0)
- `signal_2_score` - Text statistics analyzer result (0.0-1.0)
- `final_confidence` - Combined weighted confidence (0.0-1.0)
- `classification` - Attribution result: "ai", "human", or "uncertain"
- `label` - Transparency text shown to user
- `status` - "classified" or "under_review" (if appeal filed)

### Example Audit Log Entries

**Entry 1: Human-Written Content (No Appeal)**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "content_id": "a40831e5-138e-405e-8656-96350b37bb62",
  "creator_id": "user-author-001",
  "timestamp": "2026-06-28T12:15:34.892103Z",
  "signal_1_score": 0.90,
  "signal_2_score": 0.78,
  "final_confidence": 0.8625,
  "classification": "human",
  "label": "This appears to be written by a human",
  "status": "classified"
}
```
**Why this scores as human:** Specific personal details ("ramen place downtown"), emotional reaction ("underwhelming"), conversational tone, authentic critique with examples.

---

**Entry 2: AI-Generated Content (No Appeal)**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "content_id": "f5ad0ef0-2028-44d8-82fc-46d7c2a6511b",
  "creator_id": "user-bot-002",
  "timestamp": "2026-06-28T12:14:52.456789Z",
  "signal_1_score": 0.0,
  "signal_2_score": 0.32,
  "final_confidence": 0.096,
  "classification": "ai",
  "label": "This appears to be AI-generated content",
  "status": "classified"
}
```
**Why this scores as AI:** Corporate jargon ("demonstrates potential", "synergistic methodologies"), abstract noun chains ("enterprise stakeholder ecosystems"), no personal voice, formulaic structure.

---

**Entry 3: Uncertain Content (With Appeal)**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "content_id": "712ecbb6-c4a9-4dba-b111-fdc299dc2334",
  "creator_id": "user-author-001",
  "timestamp": "2026-06-28T12:14:15.123456Z",
  "signal_1_score": 0.50,
  "signal_2_score": 0.55,
  "final_confidence": 0.5155,
  "classification": "uncertain",
  "label": "We're uncertain about the origin of this content. It may be AI-generated or human-written.",
  "status": "under_review"
}
```
**Why this scores as uncertain:** Mixed signals - has personal markers ("I attended", "yesterday") but also formal corporate language ("strategic partnerships", "brand visibility"), creating genuine ambiguity. Status changed to "under_review" after creator appealed with: "This is my original work written from personal experience at a restaurant I visited."

---

**Summary of 3 Entries:**
1. **Human (0.86)** - Confident human: specific details + emotion
2. **AI (0.10)** - Confident AI: corporate jargon + no personal voice
3. **Uncertain (0.52)** - Mixed signals: personal + formal language → appeal filed

---

## Testing

### Test 1: Human-Written Content
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text":"ok so i finally tried that ramen place downtown and honestly underwhelming.", "creator_id":"user-123"}'
```
Expected: `"classification": "human"`, confidence ~0.85+, label about being "written by a human"

### Test 2: AI-Generated Content
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text":"The implementation of comprehensive digital transformation strategies demonstrates potential to leverage synergistic methodologies across stakeholder ecosystems.", "creator_id":"user-ai"}'
```
Expected: `"classification": "ai"`, confidence ~0.10, label about being "AI-generated content"

### Test 3: Uncertain Content
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text":"I attended a meeting yesterday about marketing initiatives. We discussed approaches to enhance brand visibility and improve customer engagement through partnerships.", "creator_id":"user-uncertain"}'
```
Expected: `"classification": "uncertain"`, confidence ~0.50, label about being "uncertain"

### Test 4: Appeal a Classification
```bash
# Submit content first
CONTENT_ID=$(curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text":"This is my original work.", "creator_id":"user-123"}' | jq -r '.content_id')

# Appeal it
curl -X POST http://localhost:5000/appeals \
  -H "Content-Type: application/json" \
  -d "{\"content_id\":\"$CONTENT_ID\", \"creator_id\":\"user-123\", \"creator_reasoning\":\"This is my original work and I wrote it myself.\"}"
```
Expected: `"status": "under_review"`, returns unique appeal_id

### Test 5: Verify Appeal in Log
```bash
curl http://localhost:5000/log?limit=5 | jq '.entries[0]'
```
Expected: The most recent entry shows `"status": "under_review"`

### Test 6: Rate Limiting (see section above)
```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission.", "creator_id": "test"}'
done
```
Expected: 10 × 200, then 2 × 429

---

## Architecture

For detailed architecture documentation including:
- Multi-signal detection pipeline specifics
- Confidence scoring methodology
- Label generation thresholds and design
- Appeals workflow details
- Edge case handling
- Database schema

See `specs/planning.md`.
