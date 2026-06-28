# Provenance Guard: Architecture Narrative

## Overview

Provenance Guard is an API service that classifies text content as AI-generated or human-written, providing confidence scores and transparency labels for platforms and readers. The system uses a multi-signal detection pipeline to minimize false positives while maintaining fast response times.

## Current Implementation Status

**Module 4 (Complete):**
- ✅ Flask API with POST /submit endpoint
- ✅ Input validation (text length 10-10,000 chars, creator_id required)
- ✅ Signal 1 (Groq Semantic Analysis) - detects corporate jargon, false balance, vague phrases
- ✅ Signal 2 (Text Statistics) - detects personal markers, emotional language, formulaic phrases
- ✅ Confidence Scorer - weighted ensemble (70% Signal 1 + 30% Signal 2)
- ✅ Label Generator - three transparency variants based on thresholds
- ✅ Audit logging - captures both signal scores + combined confidence
- ✅ Database schema - SQLite with signal_1_score, signal_2_score, final_confidence, classification, label
- ✅ Rate limiting (10 req/min per IP)
- ✅ Error handling (400, 413, 429, 500)

**Module 5 (In Progress):**
- ⏳ POST /appeals endpoint
- ⏳ Appeals workflow with database updates
- ⏳ Human reviewer interface

## The Journey: Text Submission to User Label

A user's text submission goes through the following path:

```
1. User submits text via API
   ↓
2. Rate Limiter validates request frequency
   ↓
3. Input Validator checks content, validates creator_id, and generates tracking ID (content_id)
   ↓
4. Multi-Signal Detection Pipeline analyzes text
   ├─ Signal 1: Groq Semantic Analysis (70% weight) - LLM-based analysis
   └─ Signal 2: Text Statistics (30% weight) - statistical patterns
   ↓
5. Confidence Scorer combines signals into single confidence score (0.0-1.0)
   ↓
6. Label Generator creates transparency text based on confidence
   ↓
7. Audit Logger records decision, signals, and metadata
   ↓
8. API Response returned with classification, confidence, and label
```

## System Components

### 1. Flask API Server (`app.py`)
**Purpose:** HTTP entry point for the service.

**Responsibilities:**
- Receive POST requests at `/submit` endpoint
- Route requests through the detection pipeline
- Return structured JSON responses
- Handle errors and edge cases

**Interface:**
```json
POST /submit
Request:
{
  "text": "The quick brown fox jumps over the lazy dog...",
  "creator_id": "user-12345"
}

Response:
{
  "content_id": "uuid-1234",
  "creator_id": "user-12345",
  "classification": "human",
  "confidence": 0.92,
  "label": "This appears to be written by a human",
  "signals": {
    "text_statistics": 0.88,
    "semantic_analysis": 0.94
  }
}
```

### 2. Rate Limiter (`middleware/rate_limiter.py`)
**Purpose:** Protect the service from abuse and ensure fair usage.

**Specifications:**
- **Limit:** 10 requests per minute per IP address
- **Implementation:** Flask-Limiter middleware
- **Response:** 429 Too Many Requests when exceeded
- **Reasoning:** 10 req/min supports typical user workflows (a few classifications per minute) while preventing automated scraping or DoS attacks

**Database Impact:** Stores submission attempt records with timestamps and IP addresses in SQLite for audit purposes.

### 3. Input Validator (`models/schemas.py`)
**Purpose:** Ensure incoming data is valid and safe before processing.

**Validations:**
- Text length: minimum 10 characters, maximum 10,000 characters
- Text encoding: UTF-8 valid
- Non-empty content (not whitespace only)
- `creator_id` is required and non-empty
- Generates unique `content_id` (UUID) for tracking

**Error Responses:**
- 400 Bad Request for invalid input (missing creator_id, text too short, etc.)
- 413 Payload Too Large for oversized submissions

### 4. Multi-Signal Detection Pipeline

#### Signal 1: Semantic Analyzer (`detection/groq_analyzer.py`)
**Purpose:** Detect AI-generation patterns by identifying corporate/academic jargon, lack of authentic details, and formulaic reasoning.

**Weight:** 70% of final confidence score

**Process:**
1. Send text to Groq API (llama-3.3-70b-versatile) with structured analysis prompt
2. LLM analyzes for: corporate jargon, abstract noun chains, presence of specific anecdotes, authentic voice, genuine reasoning
3. Returns probability score 0.0-1.0

**Measurements:**
- Corporate/academic jargon: Detects vague phrases like "demonstrates potential", "enhances efficiency", "systematic optimization"
- Abstract noun chains: Flags "systems", "methodologies", "frameworks" appearing without concrete examples
- Specific details & anecdotes: Scores higher when text includes personal examples, concrete anecdotes, genuine perspective
- Authentic voice: Detects informal language, conversational tone, human quirks vs. "perfect" grammar
- Genuine reasoning: Looks for unexpected connections and novel insights rather than formulaic reasoning chains

**Why This Signal:**
- Catches AI patterns that pure statistics miss (specific linguistic tells of corporate AI output)
- Leverages language model's understanding of authenticity vs. formulaic writing
- Fast enough for real-time classification (single API call)

**Blind Spots (What It Can't Capture):**
1. **AI trained to mimic authenticity** — If AI is fine-tuned to include anecdotes and conversational tone, Signal 1 won't detect it
2. **Humans writing formally without corporate jargon** — A formal letter or academic paper without jargon/anecdotes may score as AI
3. **Expert technical writing** — Domain experts naturally use "systems", "methodologies", abstract nouns; may be misclassified as AI
4. **Casual writing without anecdotes** — Someone sharing a simple thought without examples might score low (AI-like) despite being human
5. **Non-English or translated content** — Groq's training is English-heavy; translations may appear unnatural without being AI
6. **Very specific domains** — AI trained on specialized corpora (medical, legal) may have authentic-sounding domain language

**Output:** Probability score 0.0-1.0 (higher = more likely human-written)

#### Signal 2: Stylometric Analyzer (`detection/text_stats.py`)
**Purpose:** Measure vocabulary and structural diversity to catch repetitive patterns often found in AI writing.

**Weight:** 30% of final confidence score

**Measurements:**
- Type-Token Ratio (TTR): Vocabulary diversity = unique words / total words (normalized to 0-1)
  - High TTR (>0.6) = diverse vocabulary = human-like
  - Low TTR (<0.4) = repetitive vocabulary = AI-like
- Bigram Diversity: Phrase variation = unique bigrams / total bigrams
  - High diversity = varied phrases (human-like)
  - Low diversity = repeated word pairs (AI-like)
- Sentence Length Variance: Structural variety = coefficient of variation in sentence lengths (normalized to 0-1)
  - High variance = varied sentence structure (human-like)
  - Low variance = uniform sentence lengths (AI-like)

**Combined Formula:** 45% TTR + 45% Bigram Diversity + 10% Sentence Variance

**Why This Signal:**
- Fast to compute (no external API calls, pure Python)
- Deterministic and reproducible across runs
- Catches obvious repetition patterns ("the cat... the cat... the cat...")
- Complements semantic analysis (catches what Groq might miss)

**Blind Spots (What It Can't Capture):**
1. **Semantic meaning** — Can't tell if arguments are logical or circular; only measures word choice diversity
2. **Originality vs. plagiarism** — Plagiarized human text has high diversity but zero originality
3. **Intentional stylization** — Poetry, children's books, song lyrics intentionally use repetition but are human-written
4. **Domain-specific writing** — Technical/legal/medical documents naturally repeat specialized terms; high TTR ≠ authentic
5. **AI trained to vary vocabulary** — Modern AI can produce high TTR and diverse bigrams while remaining obviously formulaic semantically
6. **Short texts** — Insufficient tokens for reliable statistics; random variation can skew scores
7. **Non-English text** — TTR/bigram patterns differ across languages; metrics don't transfer
8. **Human stylistic choices** — Someone writing simply by choice (children, ESL speakers) may score low despite being human

**Output:** Probability score 0.0-1.0 (higher = more likely human-written)

#### Why Ensemble with These Two Signals?
- **Complementary:** Signal 1 (Groq) catches semantic/linguistic patterns; Signal 2 (Stylometric) catches structural patterns
- **Reliability difference:** Signal 1 (80%) is more discriminative for formal/semi-formal text; Signal 2 (20%) complements but has lower discriminative power
- **Robust:** Neither signal alone is perfect; 80/20 weighting gives semantic analysis dominance while allowing structural analysis to contribute
- **Interpretable:** Each signal has clear meaning; empirical testing showed Signal 2's vocabulary diversity metrics are less discriminative than Signal 1's semantic pattern detection

### 5. Confidence Scorer (`detection/scorer.py`)
**Purpose:** Combine multiple signals into a single confidence metric that reflects genuine uncertainty.

**Algorithm:**
```
final_confidence = (0.70 × signal_1_groq_score) + (0.30 × signal_2_stylometric_score)
```

**Output Range:** 0.0 to 1.0
- 0.0 = definitely AI-generated
- 0.5 = completely uncertain
- 1.0 = definitely human-written

**Uncertainty Representation:**
- Score of 0.51 produces "uncertain" label (different from 0.85)
- Score of 0.60 produces "genuinely uncertain, could go either way" label
- Score of 0.30 produces "likely AI but uncertain" label
- Score of 0.85 produces definitive "human-written" label

**Key Design:** The confidence score directly determines label text, ensuring that 0.51 and 0.95 are meaningfully different to end users, not just numerically different.

**Mapping Raw Signals to Calibrated Confidence:**

Example with confidence score of 0.605:
- Signal 1 (Groq semantic): scores 0.65 (sees mostly human reasoning but some oddities)
- Signal 2 (Stylometric): scores 0.50 (mixed patterns—some natural variation, some unusual)
- Calculation: `(0.70 × 0.65) + (0.30 × 0.50) = 0.455 + 0.15 = 0.605`
- Result: **0.6 means the system is conflicted**
  - Signal 1 sees genuine reasoning (pulling toward human)
  - Signal 2 sees unusual patterns (pulling toward AI)
  - Neither signal dominates; uncertainty is genuine
  - Label shown: "We're uncertain about the origin of this content..."

**Threshold Mapping:**
- **0.0-0.35:** High-confidence AI ("This appears to be AI-generated content")
- **0.35-0.70:** Uncertain ("We're uncertain about the origin...")
- **0.70-1.0:** High-confidence human ("This appears to be written by a human")

### 6. Label Generator (`labels/generator.py`)
**Purpose:** Convert confidence scores into plain-language transparency text for non-technical readers.

**Three Label Variants:**

**Variant 1: High-Confidence Human (Confidence > 0.70)**
```
"This appears to be written by a human"
```
Used when: Text has strong statistical and semantic markers of human authorship

**Variant 2: High-Confidence AI (Confidence < 0.35)**
```
"This appears to be AI-generated content"
```
Used when: Both signals indicate strong probability of AI generation

**Variant 3: Uncertain (Confidence 0.35-0.70)**
```
"We're uncertain about the origin of this content. It may be AI-generated or human-written."
```
Used when: Signals conflict or are inconclusive

**Design Principles:**
- Plain language, no technical jargon
- Acknowledges uncertainty explicitly (not pretending certainty where none exists)
- Appropriate confidence level in output (don't make strong claims with weak signals)
- Consistent framing: "appears to be" rather than definitive statements

### 7. Audit Logger (`middleware/audit_logger.py`)
**Purpose:** Create an immutable record of all classification decisions for compliance, debugging, and appeals.

**What Gets Logged:** Every classification decision records:
- `content_id`: Unique identifier for this submission
- `creator_id`: ID of the creator who submitted this content
- `timestamp`: When classification occurred
- `text_hash`: SHA-256 hash of submitted text (for privacy, not full text)
- `signal_1_score`: Text statistics analyzer output
- `signal_2_score`: Semantic analyzer output
- `final_confidence`: Combined confidence score
- `classification`: Final label ("human" or "ai")
- `transparency_label`: Exact text shown to user
- `source_ip`: IP address of request
- `groq_reasoning`: Explanation from Groq API (when available)

**Storage:** SQLite `audit_log` table, append-only (no modifications)

**Queries:**
- `GET /log` returns last 100 classification records in JSON format
- Includes at least 3 complete entries for verification

**Example Output:**
```json
[
  {
    "content_id": "550e8400-e29b-41d4-a716-446655440000",
    "creator_id": "user-alice-001",
    "timestamp": "2026-06-26T14:32:15Z",
    "text_hash": "d2d2d2...",
    "signal_1_score": 0.88,
    "signal_2_score": 0.94,
    "final_confidence": 0.92,
    "classification": "human",
    "transparency_label": "This appears to be written by a human",
    "source_ip": "192.168.1.1",
    "groq_reasoning": "Natural thought progression and genuine knowledge integration..."
  },
  {
    "content_id": "660e8400-e29b-41d4-a716-446655440001",
    "creator_id": "user-bob-002",
    "timestamp": "2026-06-26T14:31:45Z",
    "text_hash": "e3e3e3...",
    "signal_1_score": 0.15,
    "signal_2_score": 0.08,
    "final_confidence": 0.10,
    "classification": "ai",
    "transparency_label": "This appears to be AI-generated content",
    "source_ip": "192.168.1.2",
    "groq_reasoning": "Formulaic structure and pattern-matching without genuine reasoning..."
  },
  {
    "content_id": "770e8400-e29b-41d4-a716-446655440002",
    "creator_id": "user-carol-003",
    "timestamp": "2026-06-26T14:30:12Z",
    "text_hash": "f4f4f4...",
    "signal_1_score": 0.52,
    "signal_2_score": 0.48,
    "final_confidence": 0.50,
    "classification": "uncertain",
    "transparency_label": "We're uncertain about the origin of this content. It may be AI-generated or human-written.",
    "source_ip": "192.168.1.3",
    "groq_reasoning": "Conflicting signals; could be human with AI-like patterns or AI with human-like style..."
  }
]
```

### 8. Appeals Handler (`appeals/handler.py`)
**Purpose:** Allow creators to contest classifications they believe are incorrect.

**Workflow:**
1. Creator submits appeal with reasoning
2. System validates appeal format
3. Submission status changes to "under_review"
4. Appeal is logged alongside original decision
5. Human reviewer can later re-evaluate (automated re-classification not implemented)

**Endpoint:**
```json
POST /appeals
Request:
{
  "submission_id": "550e8400-e29b-41d4-a716-446655440000",
  "creator_reasoning": "This is my original poem, I wrote it myself..."
}

Response:
{
  "appeal_id": "appeal-uuid",
  "submission_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "under_review",
  "message": "Your appeal has been received and logged"
}
```

**What Gets Recorded:**
- `appeal_id`: Unique appeal identifier
- `submission_id`: Links to original classification
- `creator_reasoning`: Text of creator's explanation
- `timestamp`: When appeal was submitted
- `status`: "under_review" (awaiting human evaluation)

**Stored:** SQLite `appeals` table, linked to original submission in audit log

**Future Enhancement:** Automated re-classification could trigger on appeal, but currently this is a manual review process.

**Human Reviewer Interface:**

When a reviewer opens the appeal queue, they see a sortable table with these columns:

| Column | Example Value | Purpose |
|--------|---------------|---------|
| **Appeal ID** | appeal-uuid-001 | Unique identifier for tracking |
| **Submission Date** | 2026-06-26 14:32:15 | When original content was submitted |
| **Creator's Reasoning** | "This is my original poem..." | Why they dispute the classification |
| **Original Classification** | "AI-generated" | What the system decided |
| **Confidence Score** | 0.18 | How confident was the system? |
| **Signal Breakdown** | Stats: 0.15, Semantic: 0.20 | Where did signals disagree? |
| **Content Preview** | [First 200 characters] | Snippet of classified text |
| **Appeal Date** | 2026-06-26 14:35:22 | When appeal was submitted |
| **Status** | under_review | Current state of appeal |

**Reviewer Decision Options:**
1. **Agree with Classification** → Set status to "resolved", note: "Reviewed; classification stands"
2. **Overturn Classification** → Update original classification, set status to "resolved_overturned", note: "Classification was incorrect. Updated to: [new label]"
3. **Request More Information** → Set status to "requires_info", message back to creator asking for clarification

Every reviewer action is logged with timestamp and reviewer ID for accountability.

## False Positive Scenario: Human Writer Misclassified as AI

**Scenario:** A human poet submits experimental, stream-of-consciousness poetry with intentional:
- Short, fragmented sentences (15% length variance instead of typical 30-40%)
- Repetitive word patterns ("alone, alone, alone again" for emotional effect)
- Nonlinear structure jumping between ideas without explicit transitions
- Unusual capitalization and punctuation

**System Trace:**

1. **Signal 1: Text Statistics**
   - Sees high repetition and low sentence variance
   - Scores: 0.25 (likely AI, due to unusual patterns)
   - Problem: Doesn't understand intentional poetic style

2. **Signal 2: Groq Semantic Analysis**
   - Recognizes intentional artistry and emotional coherence
   - Scores: 0.82 (likely human, recognizes style choice)
   - Correct: Understands this is deliberate artistic choice

3. **Confidence Scorer**
   - Calculation: `(0.70 × 0.82) + (0.30 × 0.25) = 0.649`
   - Result: Genuine uncertainty, not false confidence

4. **Label Generator**
   - Confidence 0.649 falls in uncertain range (0.20-0.80)
   - Label shown: "We're uncertain about the origin of this content. It may be AI-generated or human-written."
   - Outcome: Reader is NOT misled by false certainty

5. **Creator Appeals**
   - Submits: `POST /appeals` with reasoning: "This is my original experimental poetry. I wrote it intentionally with fragmentation."
   - System updates status to `"under_review"`
   - Appeal logged with original decision for human reviewer

6. **Key Insight:**
   - The false positive was "contained" by proper uncertainty representation
   - Label didn't claim AI with confidence
   - Confidence score (0.649) honestly reflected disagreement between signals
   - Appeals mechanism available for creator to clarify intent
   - Human reviewer has full context to make final determination

### 9. Database Layer (`models/database.py`)
**Purpose:** Persistent storage for all decisions, signals, and appeals.

**Technology:** SQLite (file-based, no external dependencies)

**Schema:**

**Table: submissions**
- `id` (UUID): Primary key (content_id)
- `creator_id` (string): ID of content creator
- `text_hash` (SHA-256): Hash of original text
- `classification` (enum: human|ai|uncertain): Final decision
- `confidence` (float 0-1): Confidence score
- `label` (text): Transparency label shown to user
- `timestamp` (ISO-8601): When classified
- `source_ip` (string): Request IP
- `appeal_status` (enum: none|under_review|resolved): Appeal state

**Table: audit_log**
- `id` (UUID): Primary key
- `content_id` (UUID): Foreign key to submissions
- `creator_id` (string): Creator of the content
- `signal_1_score` (float): Text statistics result
- `signal_2_score` (float): Semantic analysis result
- `final_confidence` (float): Combined score
- `groq_reasoning` (text): LLM explanation
- `timestamp` (ISO-8601): When recorded

**Table: appeals**
- `id` (UUID): Primary key
- `content_id` (UUID): Foreign key to submissions
- `creator_id` (string): Creator ID of the content being appealed
- `creator_reasoning` (text): Appeal justification
- `status` (enum: under_review|resolved): Appeal state
- `timestamp` (ISO-8601): When submitted
- `reviewer_notes` (text nullable): Human reviewer feedback

## Architecture Flows with Labeled Data Passing

### Flow 1: Text Submission Flow (POST /submit)

```
┌──────────────┐
│ User/Client  │
└────┬─────────┘
     │ POST /submit
     │ {"text": "...", "creator_id": "..."}
     ↓
┌─────────────────┐
│  Flask API      │
│  Server         │
└────┬────────────┘
     │ (text, source_ip)
     ↓
┌─────────────────┐
│  Rate Limiter   │
│ (check IP limit)│
└────┬────────────┘
     │ (text, source_ip) [OR 429 error]
     ↓
┌─────────────────┐
│ Input Validator │
│ (validate, gen  │
│  content_id)    │
└────┬────────────┘
     │ (text, creator_id, content_id) [OR 400/413 error]
     ↓
    ┌─────────────────────────────┐
    │ Multi-Signal Pipeline       │
    │ (parallel execution)        │
    ├─────────────┬───────────────┤
    │             │               │
    ↓             ↓               
┌──────────────┐ ┌──────────────┐
│ Signal 1:    │ │ Signal 2:    │
│ Text Stats   │ │ Groq API     │
│ (fast)       │ │ (slower)     │
└──────┬───────┘ └──────┬───────┘
       │ (stat_score)   │ (semantic_score, reasoning)
       └────────┬────────┘
                │ (0.0-1.0 scores)
                ↓
        ┌──────────────────┐
        │ Confidence Scorer│
        │ (ensemble blend) │
        └────────┬─────────┘
                │ (final_confidence: 0.0-1.0)
                ↓
        ┌──────────────────┐
        │ Label Generator  │
        │ (3-variant text) │
        └────────┬─────────┘
                │ (label_text)
                ↓
        ┌──────────────────┐
        │ Audit Logger     │
        │ (record decision)│
        └────────┬─────────┘
                │ (all metadata → SQLite)
                ↓
        ┌──────────────────┐
        │ API Response     │
        │ (JSON)           │
        └────────┬─────────┘
                │ {"content_id", "creator_id", "classification", "confidence", "label", "signals"}
                ↓
        ┌──────────────────┐
        │ User/Client      │
        │ (receives label) │
        └──────────────────┘
```

**Data Legend:**
- `text`: Raw text content (10-10,000 chars)
- `creator_id`: ID of content creator
- `source_ip`: IP address of request
- `content_id`: UUID for tracking
- `stat_score`: Text statistics signal output (0-1)
- `semantic_score`: Groq semantic analysis output (0-1)
- `final_confidence`: Weighted ensemble (70% semantic, 30% stats)
- `label_text`: Plain language transparency label (one of 3 variants)

---

### Flow 2: Appeal Flow (POST /appeals)

```
┌──────────────┐
│ Creator      │
└────┬─────────┘
     │ POST /appeals
     │ {"submission_id": "...",
     │  "creator_reasoning": "..."}
     ↓
┌─────────────────┐
│  Flask API      │
│  Server         │
└────┬────────────┘
     │ (submission_id, reasoning)
     ↓
┌──────────────────────┐
│ Appeal Handler       │
│ (validate, generate  │
│  appeal_id)          │
└────┬─────────────────┘
     │ (appeal_id, submission_id, status)
     ↓
┌──────────────────────┐
│ Database Update      │
│ (SQLite: mark        │
│  submission as       │
│  "under_review")     │
└────┬─────────────────┘
     │ (appeal_id, appeal_record)
     ↓
┌──────────────────────┐
│ Audit Logger         │
│ (log appeal event)   │
└────┬─────────────────┘
     │ (audit_event → SQLite)
     ↓
┌──────────────────────┐
│ API Response (200)   │
└────┬─────────────────┘
     │ {"appeal_id", "status": "under_review", "message": "..."}
     ↓
┌──────────────────────┐
│ Creator receives     │
│ confirmation + ID    │
└──────────────────────┘

[Later, Asynchronous Review:]

┌──────────────────────┐
│ Human Reviewer       │
│ - Queries appeals    │
│ - Reads original     │
│   classification     │
│ - Reviews creator    │
│   reasoning          │
│ - Makes decision:    │
│   * Agree            │
│   * Overturn         │
│   * Request info     │
└──────────────────────┘
     │ (updates appeals.status)
     ↓
┌──────────────────────┐
│ Database Update      │
│ (SQLite: set status  │
│  to "resolved")      │
└──────────────────────┘
```

**Data Legend:**
- `submission_id`: Links to original classification
- `creator_reasoning`: Why creator disputes classification (20-2000 chars)
- `appeal_id`: Unique identifier for this appeal (UUID)
- `status`: Appeal state ("under_review", "resolved", "requires_info")

## API Surface Specification

### Endpoints Overview

| Endpoint | Method | Purpose | Rate Limit |
|----------|--------|---------|-----------|
| `/submit` | POST | Submit text for AI/human classification | 10 req/min per IP |
| `/appeals` | POST | Appeal a classification decision | 10 req/min per IP |
| `/log` | GET | Retrieve audit log of all classifications | 30 req/min per IP |

### Endpoint 1: POST `/submit`

**Purpose:** Submit text content for classification

**Request Body:**
```json
{
  "text": "The content to analyze...",
  "creator_id": "user-12345"
}
```

**Constraints:**
- `text`: Required, string, 10-10,000 characters, UTF-8 encoding required, non-whitespace only
- `creator_id`: Required, string, non-empty (identifier of the content creator)

**Success Response (200 OK) - Module 4:**
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

**Response Explanation:**
- `content_id`: Unique tracking ID (UUID)
- `creator_id`: Original creator ID from request
- `classification`: "ai" (confidence < 0.35), "uncertain" (0.35-0.70), or "human" (> 0.70)
- `confidence`: Rounded to 2 decimals: (0.70 × signal_1) + (0.30 × signal_2)
- `label`: Transparency text shown to user (one of three variants)
- `signals`: Individual scores from both analyzers

**Error Responses:**
- `400 Bad Request`: Invalid input (too short, non-UTF8, empty, etc.)
- `413 Payload Too Large`: Text exceeds 10,000 characters
- `429 Too Many Requests`: Rate limit exceeded (10 requests per minute per IP)
- `500 Internal Server Error`: Groq API call failed or database error

---

### Endpoint 2: POST `/appeals`

**Purpose:** Contest a classification decision

**Request Body:**
```json
{
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "creator_id": "user-12345",
  "creator_reasoning": "This is my original work. I wrote it myself without AI assistance..."
}
```

**Constraints:**
- `content_id`: Required, must exist in database (from prior POST /submit call as the response content_id)
- `creator_id`: Required, must match the creator_id from the original submission
- `creator_reasoning`: Required, string, 20-2,000 characters

**Success Response (200 OK):**
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
1. Validates content_id exists in database
2. Validates creator_id matches original submission's creator_id
3. Validates creator_reasoning is 20-2,000 characters
4. Creates appeal record in `appeals` table with status "under_review"
5. Updates original submission's `appeal_status` from "none" to "under_review"
6. Logs to audit_log
7. Returns appeal_id and confirmation message

**Error Responses:**
- `400 Bad Request`: Invalid content_id format, creator_id mismatch, reasoning too short/long, or missing fields
- `404 Not Found`: content_id doesn't exist in database
- `429 Too Many Requests`: Rate limit exceeded (10 requests per minute per IP)
- `500 Internal Server Error`: Database error

---

### Endpoint 3: GET `/log`

**Purpose:** Retrieve audit log of classifications and appeals

**Query Parameters:**
- `limit` (optional, default=100, max=500): Number of records to return
- `offset` (optional, default=0): Pagination offset for retrieving records

**Example Request:**
```
GET /log?limit=3&offset=0
```

**Success Response (200 OK):**
```json
{
  "total": 327,
  "limit": 3,
  "offset": 0,
  "records": [
    {
      "content_id": "550e8400-e29b-41d4-a716-446655440000",
      "creator_id": "user-alice-001",
      "timestamp": "2026-06-26T14:32:15Z",
      "text_hash": "d2d2d2d2...",
      "signal_1_score": 0.88,
      "signal_2_score": 0.94,
      "final_confidence": 0.92,
      "classification": "human",
      "label": "This appears to be written by a human",
      "source_ip": "192.168.1.1",
      "appeal_status": "none"
    },
    {
      "content_id": "660e8400-e29b-41d4-a716-446655440001",
      "creator_id": "user-bob-002",
      "timestamp": "2026-06-26T14:31:45Z",
      "text_hash": "e3e3e3e3...",
      "signal_1_score": 0.15,
      "signal_2_score": 0.08,
      "final_confidence": 0.10,
      "classification": "ai",
      "label": "This appears to be AI-generated content",
      "source_ip": "192.168.1.2",
      "appeal_status": "none"
    },
    {
      "content_id": "770e8400-e29b-41d4-a716-446655440002",
      "creator_id": "user-carol-003",
      "timestamp": "2026-06-26T14:30:12Z",
      "text_hash": "f4f4f4f4...",
      "signal_1_score": 0.52,
      "signal_2_score": 0.48,
      "final_confidence": 0.50,
      "classification": "uncertain",
      "label": "We're uncertain about the origin of this content. It may be AI-generated or human-written.",
      "source_ip": "192.168.1.3",
      "appeal_status": "none"
    }
  ]
}
```

**Error Responses:**
- `400 Bad Request`: Invalid query parameters (limit > 500, negative offset, etc.)
- `429 Too Many Requests`: Rate limit exceeded (30 requests per minute per IP)
- `500 Internal Server Error`: Database error

---

## Feature Coverage

### Content Submission Endpoint
- **Endpoint:** POST `/submit`
- **Input:** JSON with text field (10-10,000 characters) and creator_id
- **Output (M3):** JSON with content_id, creator_id, attribution (Signal 1 score), placeholder confidence (0.5), and placeholder label ("uncertain")
- **Output (M4+):** Will include actual ensemble confidence and label from both signals
- **Error Handling:** 400 for invalid input, 413 for oversized, 429 for rate limit

### Multi-Signal Detection Pipeline
- **Signal 1:** Groq Semantic Analysis (corporate jargon, false balance, lack of specificity, formulaic reasoning)
  - Weight: 70%
  - Why: Semantic understanding of text patterns and linguistic authenticity
- **Signal 2:** Text Statistics (personal markers, emotional language, formulaic phrases, vocabulary diversity)
  - Weight: 30%
  - Why: Fast, deterministic, detects AI patterns through stylometric analysis complementing semantic signals
- Both signals required; combined they catch patterns each misses alone

### Confidence Scoring with Uncertainty
- **Score Range:** 0.0 (AI) to 1.0 (human)
- **Thresholds:** Scores 0.51 and 0.95 produce different labels, reflecting genuine uncertainty
- **Implementation:** Weighted ensemble (70% Groq semantic + 30% Statistics)
- **Label Variation:** Confidence directly determines which of 3 labels is shown
  - >0.80: "appears to be human"
  - <0.20: "appears to be AI"
  - 0.20-0.80: "uncertain, may be either"

### Transparency Label
Exactly three variants, displayed to non-technical readers:

1. **High-Confidence Human** (confidence > 0.80)
   ```
   "This appears to be written by a human"
   ```

2. **High-Confidence AI** (confidence < 0.20)
   ```
   "This appears to be AI-generated content"
   ```

3. **Uncertain** (confidence 0.20-0.80)
   ```
   "We're uncertain about the origin of this content. It may be AI-generated or human-written."
   ```

### Appeals Workflow
- **Endpoint:** POST `/appeals`
- **Input:** content_id, creator_id, and creator_reasoning
- **Action:** Records appeal, updates submission status to "under_review"
- **Output:** appeal_id and confirmation message
- **Logging:** Appeal stored in `appeals` table, linked to original submission
- **Current Limitation:** Requires human review (automated re-classification not implemented)

### Rate Limiting
- **Limit:** 10 requests per minute per IP address
- **Implementation:** Flask-Limiter middleware
- **Response:** 429 Too Many Requests when exceeded
- **Reasoning:** Prevents abuse while allowing ~1 request per 6 seconds (adequate for user workflows)
- **Tracking:** All request attempts logged for compliance

### Audit Log
- **Access:** GET `/log` returns last 100 classification records
- **Contents:** content_id, creator_id, timestamp, signal scores, confidence, classification, label, IP, reasoning
- **Storage:** SQLite `audit_log` table
- **Immutable:** Append-only, no modifications
- **Example:** Returns at least 3 complete entries showing variety of classifications

## Implementation Files

```
provenance-guard/
├── app.py                          # Flask application entry point
├── models/
│   ├── database.py                 # SQLite schema and queries
│   └── schemas.py                  # Request/response validation
├── detection/
│   ├── text_stats.py               # Signal 1: Text statistics
│   ├── groq_analyzer.py            # Signal 2: Groq semantic analysis
│   └── scorer.py                   # Confidence scoring ensemble
├── labels/
│   └── generator.py                # Label text generation
├── appeals/
│   └── handler.py                  # Appeal workflow logic
├── middleware/
│   ├── rate_limiter.py             # Request rate limiting
│   └── audit_logger.py             # Decision logging
├── requirements.txt                # Python dependencies
├── .env                            # Environment variables (Groq API key)
└── database.db                     # SQLite database file
```

## Anticipated Edge Cases

### Edge Case 1: Stream-of-Consciousness Poetry with Heavy Repetition

**Specific Scenario:**
A human poet intentionally writes experimental poetry with:
- Repetitive words for emotional effect: "alone, alone, alone / in the dark, dark, dark"
- Short fragmented sentences (15% length variance vs. typical 30-40%)
- Nonlinear jumps between imagery without logical connectors
- Unusual capitalization: "The ALONE thing / standing in Everything"

**Why System Handles Poorly:**
- **Text Statistics Signal (0.30):** Detects high word repetition and low sentence variance → scores 0.20 (likely AI)
- **Semantic Signal (0.70):** May struggle with nonlinear, abstract imagery → might score 0.55 (uncertain)
- **Combined:** `(0.70 × 0.55) + (0.30 × 0.20) = 0.385 + 0.06 = 0.445` → "uncertain" label
- **Problem:** Creator sees "uncertain" label despite genuinely writing it themselves

**Mitigation:**
- Uncertainty label doesn't lie (doesn't say "AI")
- Creator can appeal with reasoning: "This is intentional poetic style"
- Reviewer can see the artistic intent in the text
- Ensemble weighting (70% semantic) gives semantic understanding more say

---

### Edge Case 2: AI-Generated Technical Documentation

**Specific Scenario:**
An AI model trained on technical documents generates a Standard Operating Procedure:
```
1. Open the configuration panel.
2. Select the "Network Settings" option from the menu.
3. Input the IPv4 address in the designated field.
4. Click "Save" to apply changes.
```

Characteristics:
- Perfect grammar with no errors
- Highly structured numbered lists
- Logical progression with clear cause-and-effect
- Formal, consistent tone throughout
- No stutters, corrections, or human hesitations

**Why System Handles Poorly:**
- **Text Statistics Signal (0.30):** Perfect uniformity actually looks "too clean" but might score 0.65 (human-like)
- **Semantic Signal (0.70):** Sees logical consistency and clear reasoning → might score 0.70 (human-like)
- **Combined:** `(0.70 × 0.70) + (0.30 × 0.65) = 0.49 + 0.195 = 0.685` → "uncertain" leaning human
- **Problem:** System might miss this is AI because formulaic writing doesn't trigger "AI" signals

**Mitigation:**
- Groq semantic analyzer should be trained to detect formulaic reasoning chains
- Ensemble design requires both signals to agree before high confidence
- Appeals mechanism allows human flagging of false negatives
- May require fine-tuning Groq prompt to detect "technically correct but AI-like reasoning"

---

### Edge Case 3: Translated Content (Bonus)

**Specific Scenario:**
A human translates a German article to English. Translation is accurate but:
- Awkward phrasing reflecting German structure: "It does him good" instead of "He likes it"
- Unusual word choices: "colorful-rich" instead of "vibrant"
- Preserved German punctuation or spacing

**Why System Handles Poorly:**
- **Text Statistics Signal (0.30):** Unusual patterns → scores 0.35 (AI-like)
- **Semantic Signal (0.70):** Semantic oddities → scores 0.40 (AI-like)
- **Combined:** `(0.70 × 0.40) + (0.30 × 0.35) = 0.28 + 0.105 = 0.385` → "uncertain" leaning AI
- **Problem:** System flags as AI despite being human-translated

**Mitigation:**
- No specific detection for translation in current system
- Appeals mechanism primary solution: translator explains origin
- Reviewer can recognize translation patterns
- Future enhancement: language detection or "translated content" flag

---

## AI Tool Plan

### Milestone 3: Submission Endpoint + First Signal

**Spec Sections to Provide:**
- Section 4.1: Signal 1 (Text Statistics Analyzer) - complete description with measurements and output format
- Flow 1 diagram: Submission flow with labeled data passing
- Section 1: Flask API Server - the /classify endpoint interface and expected response format

**What to Ask AI Tool to Generate:**
```
"Using the provided signal definitions and submission flow diagram, create:
1. A Flask application skeleton (app.py) with POST /submit endpoint
   - Accept JSON with 'text' and 'creator_id' fields
   - Return JSON with content_id, creator_id, classification, confidence, label, signals
   - For now, use dummy signal values (we'll replace with real logic next)
   
2. A signal_1 function in detection/text_stats.py that calculates:
   - Text entropy (token variation)
   - Perplexity (token surprise)
   - Sentence length variance
   - Returns a single score 0.0-1.0 (higher = more human)
   
Use the measurements and why-it-matters context from the spec to inform your implementation choices."
```

**How to Verify Output:**
1. Test the Flask endpoint directly with 3 sample texts via curl or Postman
2. Verify response structure matches spec (has all required fields including content_id and creator_id)
3. Test signal_1 function independently:
   - Pass a highly repetitive text → should score low (0.1-0.3)
   - Pass varied, natural text → should score high (0.7-0.9)
   - Verify score is between 0.0-1.0
4. Check that endpoint returns non-zero content_id for each request
5. Verify creator_id is preserved in response
6. Verify no errors before moving to M4

---

### Milestone 4: Second Signal + Confidence Scoring

**Spec Sections to Provide:**
- Section 4.2: Signal 2 (Semantic Analyzer) - process, measurements, limitations
- Section 5: Confidence Scorer - the algorithm with explicit formula
- Lines 162-190: Uncertainty Representation - thresholds and mapping explanation
- Flow 1 diagram: Full submission flow showing signal combination
- Groq API documentation (user provides their own or links to it)

**What to Ask AI Tool to Generate:**
```
"Using the provided detection signals and uncertainty representation:
1. A signal_2 function in detection/groq_analyzer.py that:
   - Takes text as input
   - Calls Groq API with a structured prompt asking for AI/human analysis
   - Parses response to return probability score 0.0-1.0
   - Includes error handling if API fails
   - Hint: See spec for what to measure (logical consistency, concept integration, etc.)
   
2. A confidence scorer in detection/scorer.py that:
   - Takes two signal scores (0.0-1.0 each)
   - Applies weighted ensemble: final = (0.70 × signal_2) + (0.30 × signal_1)
   - Returns confidence score 0.0-1.0
   - Include mapping examples from the spec (what 0.25, 0.50, 0.75, 0.95 mean)
   
3. Update the /submit endpoint to:
   - Call both signals in sequence (or in parallel)
   - Pass results to confidence scorer
   - Return actual confidence in response (not dummy value)"
```

**How to Verify Output:**
1. **Signal 2 Integration:**
   - Test that Groq API calls succeed with proper formatting
   - Verify response parsing returns 0.0-1.0 score
   - Test with 3 known AI texts → all should score low (0.1-0.3)
   - Test with 3 known human texts → all should score high (0.7-0.9)

2. **Confidence Scorer:**
   - Test with signal scores from step 1 (both signals on same texts)
   - Verify final confidence reflects both signals
   - Check that confidence scores differ meaningfully: AI text should be <0.4, human text should be >0.6
   - Verify threshold mapping: 0.51 (uncertain) vs 0.95 (high-confidence human) produce different results

3. **End-to-End:**
   - Submit same texts via /submit endpoint
   - Verify response includes both individual signal scores AND final confidence
   - Confirm scores match manual calculations from spec examples

---

### Milestone 5: Production Layer (Labels + Appeals)

**Spec Sections to Provide:**
- Section 6: Label Generator - the three label variants with exact text and thresholds
- Section 8: Appeals Handler - the workflow, endpoint, and what reviewer sees
- Flow 2 diagram: Appeal flow with labeled data
- API Surface Specification: POST /appeals endpoint details
- Database schema: submissions, appeals tables

**What to Ask AI Tool to Generate:**
```
"Using the provided label design and appeals workflow:
1. A label_generator function in labels/generator.py that:
   - Takes confidence score (0.0-1.0) as input
   - Returns the exact transparency label text based on thresholds:
     * <0.20: 'This appears to be AI-generated content'
     * 0.20-0.80: 'We're uncertain about the origin of this content. It may be AI-generated or human-written.'
     * >0.80: 'This appears to be written by a human'
   - Include comment explaining why these thresholds were chosen
   
2. POST /appeals endpoint in app.py that:
   - Accepts content_id, creator_id, and creator_reasoning
   - Validates inputs (reasoning 20-2000 chars, content_id exists, creator_id matches)
   - Creates appeal record in SQLite
   - Updates original submission status to 'under_review'
   - Logs to audit_log
   - Returns appeal_id and confirmation
   - Error responses: 400, 404, 429 (rate limited)
   
3. Database migration or initialization script that:
   - Creates/updates appeals table with fields from spec
   - Adds appeal_status column to submissions table if missing
   - Handles existing data gracefully"
```

**How to Verify Output:**
1. **Label Generator:**
   - Test all three thresholds independently:
     * Input 0.10 → must output AI label
     * Input 0.50 → must output uncertain label
     * Input 0.90 → must output human label
   - Test boundary values: 0.19 (AI), 0.20 (uncertain), 0.80 (uncertain), 0.81 (human)
   - Verify exact text matches spec (check for typos, punctuation)

2. **Appeals Endpoint:**
   - Submit valid appeal → check 200 response with appeal_id
   - Submit with invalid content_id → check 404 response
   - Submit with creator_id mismatch → check 400 response
   - Submit with reasoning too short (<20 chars) → check 400 response
   - Submit with reasoning too long (>2000 chars) → check 400 response
   - Verify appeal_id is unique and trackable

3. **Database State:**
   - After successful appeal: query submissions table, verify appeal_status changed to "under_review"
   - Query appeals table: verify record exists with correct fields and creator_id
   - Query audit_log: verify appeal event was logged
   - Verify original classification is unchanged (only status changed)

4. **Rate Limiting:**
   - Submit 11 appeals in 60 seconds from same IP → 11th should get 429 response
   - Verify this is per-IP (different IP should not be rate limited)

---

## Implementation Approach

**For Each Milestone:**
1. Provide AI tool with complete spec section (copy-paste from planning.md)
2. Include the relevant flow diagram(s) as ASCII art or description
3. Ask for implementation with specific function signatures and return types
4. Run verification tests before moving to next milestone
5. Do NOT wait for all three milestones—implement incrementally so each builds on verified previous work
6. Save verification test results as comments in code or in a test log

---

## Steps for Implementation

1. Implement Flask app structure with all endpoints
2. Build Signal 1 (text statistics) analyzer
3. Build Signal 2 (Groq API) semantic analyzer
4. Implement confidence scoring ensemble
5. Create SQLite database and schema
6. Add label generation logic
7. Integrate rate limiting middleware
8. Add audit logging functionality
9. Implement appeal workflow
10. Test with sample AI and human-written texts
11. **Test edge cases:** Submit stream-of-consciousness poetry, technical docs, translated content to verify appropriate classifications
12. Verify audit log contains required entries
13. Test rate limiting and error handling
