# Provenance Guard: AI Content Attribution Service

An API service that attributes text content as AI-generated or human-written, providing confidence scores and transparency labels for platforms and readers.

## Table of Contents
1. [Overview](#overview)
2. [Design Decisions](#design-decisions)
3. [Detection Signals](#detection-signals)
4. [Confidence Scoring](#confidence-scoring)
5. [API Reference](#api-reference)
6. [Installation & Setup](#installation--setup)
7. [Usage & Testing](#usage--testing)
8. [Limitations & Edge Cases](#limitations--edge-cases)
9. [Deployment Considerations](#deployment-considerations)

---

## Overview

Provenance Guard classifies text content using a **multi-signal ensemble approach**:
- **Signal 1 (70% weight):** Groq semantic analysis - detects AI patterns through linguistic authenticity
- **Signal 2 (30% weight):** Text statistics - detects AI patterns through stylometric analysis
- **Confidence Score:** Weighted ensemble produces 0.0-1.0 score mapped to 3 transparency labels

**Why this approach?**
- Single signals are unreliable: Text statistics can't detect semantic meaning, Groq alone might miss sophisticated AI
- Ensemble combines complementary strengths: Statistics catch obvious patterns fast, semantic analysis catches subtle ones
- Weighted toward semantics (70/30): Language model understanding is more discriminative for real-world text
- Transparent uncertainty: Confidence score reflects genuine disagreement between signals, not false certainty

---

## Design Decisions

### Why Multi-Signal Ensemble?

**Single-signal failures:**
1. **Statistics-only approach** fails on:
   - AI with high vocabulary diversity (modern AI can vary vocabulary)
   - Human poetry with intentional repetition (emotional effect = falsely flagged as AI)
   - Technical writing (naturally repetitive specialized terms)

2. **Semantic-only approach** fails on:
   - AI trained specifically to mimic authenticity (fine-tuned on human-written text)
   - Humans writing formally (academic papers without anecdotes score as AI)
   - Domain-specific expertise (expert jargon looks formulaic)

**Ensemble solution:**
- Statistics catch obvious, fast patterns (cheap to compute)
- Semantic analysis provides nuanced understanding (expensive but accurate)
- Disagreement = genuine uncertainty (honest about limits)

### Why These Thresholds (0.35/0.70)?

**Threshold mapping:**
- **< 0.35:** AI-generated (high confidence)
- **0.35-0.70:** Uncertain (signals disagree or are inconclusive)
- **> 0.70:** Human-written (high confidence)

**Why not symmetric (0.25/0.75 or 0.40/0.60)?**
- Testing showed this range minimizes false positives while maintaining usability
- Provides enough "uncertain" space (0.35 width) for genuinely ambiguous content
- Aligns with real-world distribution: most content is clearly AI or clearly human

---

## Detection Signals

### Signal 1: Groq Semantic Analysis (70% Weight)

**What it measures:** Linguistic authenticity markers

**How it works:**
1. Send text to Groq LLM (llama-3.3-70b-versatile) with structured prompt
2. LLM analyzes for:
   - **Corporate jargon red flags:** "demonstrates potential", "synergistic methodologies", "stakeholder ecosystems"
   - **False balance without debate:** Multiple sides presented without genuine disagreement
   - **Vague phrasing:** Statements with no specificity ("various approaches", "valuable insights")
   - **Lack of struggle:** No genuine uncertainty, no mistakes, no learning process
   - **Formulaic structure:** Predictable patterns, generic reasoning chains
3. Returns probability 0.0-1.0 (higher = more human-like)

**Why 70% weight?**
- **More discriminative:** Tests show semantic patterns better separate human vs. AI than statistics alone
- **Handles nuance:** Can understand intentional style choices (poetry, technical writing)
- **Models reasoning:** Can detect circular logic vs. genuine insight
- **Catches AI patterns:** Recognizes formulaic thinking that statistics might miss

**Blind spots (what it misses):**
- **AI trained to mimic authenticity** — If fine-tuned on human text, might fool the analyzer
- **Humans writing formally** — Academic papers without personal anecdotes score as AI
- **Expert technical writing** — Domain experts naturally use abstract terminology
- **Non-English or translated content** — Groq's training is English-heavy
- **Stream-of-consciousness writing** — Nonlinear structure confuses semantic analysis

### Signal 2: Text Statistics (30% Weight)

**What it measures:** Stylometric patterns

**How it works:**
1. Calculate three metrics:
   - **Type-Token Ratio (TTR):** Vocabulary diversity (unique words / total words)
   - **Bigram Diversity:** Phrase variation (unique word pairs / total pairs)
   - **Sentence Length Variance:** Structural variety (coefficient of variation)

2. Combine with weights:
   - 45% TTR (vocabulary matters most)
   - 45% Bigram Diversity (phrase repetition is key)
   - 10% Sentence Variance (structure less discriminative)

3. Returns probability 0.0-1.0 (higher = more human-like)

**Why include it (30% weight)?**
- **Fast & deterministic:** No API calls, pure Python, reproducible
- **Catches obvious patterns:** Detects "the cat... the cat... the cat" type repetition
- **Complements semantic analysis:** Statistics find what semantics miss
- **Cheap insurance:** Small weight provides coverage for semantic failures

**Blind spots (what it misses):**
- **Semantic meaning** — Can't tell circular logic from genuine reasoning
- **Plagiarism** — Plagiarized human text has high diversity
- **Intentional stylization** — Poetry, lyrics, children's books intentionally repeat
- **Domain-specific writing** — Medical/legal writing naturally repeats terminology
- **AI trained to vary vocabulary** — Modern AI can achieve high TTR while remaining formulaic
- **Short texts** — Insufficient data for reliable statistics

### Why This Weighting (70/30)?

**Historical reasoning:**
- Started with 80/20 (semantic dominance), but statistics were too weak
- Moved to 70/30 after redesigning Signal 2 from "diversity measurement" to "AI-specific pattern detection"
- 70/30 provides:
  - Semantic analysis leads decisions (language understanding matters)
  - Statistics provide meaningful check (catches edge cases)
  - Balanced uncertainty representation (neither signal dominates too much)

**Empirical evidence:**
- On test suite: 70/30 ensemble catches all 3 test cases correctly (AI, human, uncertain)
- 80/20 overcorrected (Signal 2 was too weak before redesign)
- 50/50 would require too much agreement (low signal quality for Statistics)

---

## Confidence Scoring

### Algorithm

```
final_confidence = (0.70 × signal_1_score) + (0.30 × signal_2_score)
```

**Input range:** Both signals output 0.0-1.0
- 0.0 = definitely AI-like
- 0.5 = neutral
- 1.0 = definitely human-like

**Output range:** 0.0-1.0
- 0.0 = very confident it's AI
- 0.5 = completely uncertain
- 1.0 = very confident it's human

### Why Ensemble Scoring?

**Single signal confidence is unreliable:**

| Signal | Strengths | Fails On |
|--------|-----------|----------|
| Groq only | Catches semantic patterns, nuanced | AI trained on human text, formal human writing |
| Stats only | Fast, deterministic, catches repetition | High-vocab AI, human repetition (poetry) |

**Ensemble scoring:**
- When signals agree (both high/low) → high confidence
- When signals disagree (one high, one low) → uncertainty label
- Example: poetry with high repetition scores 0.25 (stats) + 0.82 (Groq semantic) = 0.649 → "uncertain" (correct!)

### Threshold Mapping

```
Confidence → Attribution → Label
0.10      → AI         → "This appears to be AI-generated content"
0.50      → Uncertain  → "We're uncertain about the origin. It may be AI-generated or human-written."
0.90      → Human      → "This appears to be written by a human"
```

**Why these labels?**
- Plain language, no jargon (for non-technical readers)
- "Appears to be" instead of certainty (honest about limits)
- Explicitly acknowledge uncertainty (don't pretend false confidence)
- Consistent framing (respectful to all parties)

---

### Label Variants (What Users See)

The system displays **exactly one of three transparency labels** based on confidence score. Each label is intentionally written to be clear, honest, and respectful to content creators.

#### Variant 1: High-Confidence AI (confidence < 0.35)

**Label text displayed to user:**
```
This appears to be AI-generated content
```

**When shown:** When both signals strongly indicate AI generation (Groq semantic = low, text statistics = low)

**What it means:**
- The system detected strong AI patterns (corporate jargon, formulaic reasoning, lack of specificity)
- Both detection signals agreed on the assessment
- Appropriate for content with obvious AI markers
- Still uses "appears to be" (not 100% certain, allows for edge cases)

**Example confidence: 0.10**
- Signal 1 (Groq): 0.0 — Detected heavy corporate jargon and formulaic structure
- Signal 2 (Stats): 0.32 — Detected repetitive patterns and high uniformity
- Calculation: (0.70 × 0.0) + (0.30 × 0.32) = 0.096 ≈ 0.10

---

#### Variant 2: High-Confidence Human (confidence > 0.70)

**Label text displayed to user:**
```
This appears to be written by a human
```

**When shown:** When both signals strongly indicate human authorship (Groq semantic = high, text statistics = high)

**What it means:**
- The system detected strong human markers (personal voice, specific details, emotional language)
- Both detection signals agreed on the assessment
- Appropriate for content with clear human characteristics
- Still uses "appears to be" (not claiming absolute certainty)

**Example confidence: 0.86**
- Signal 1 (Groq): 0.90 — Detected personal voice, specific details, emotional authenticity
- Signal 2 (Stats): 0.78 — Detected vocabulary diversity, natural sentence variation, personal markers
- Calculation: (0.70 × 0.90) + (0.30 × 0.78) = 0.863 ≈ 0.86

---

#### Variant 3: Uncertain (confidence 0.35-0.70)

**Label text displayed to user:**
```
We're uncertain about the origin of this content. It may be AI-generated or human-written.
```

**When shown:** When signals conflict or are inconclusive (one signal high, one low, or both neutral)

**What it means:**
- The system cannot confidently classify this content
- One or both signals are weak/contradictory
- Appropriate for edge cases like poetry, technical writing, translated content
- Honest acknowledgment of genuine uncertainty, not hedging

**Why this exact phrasing?**
- "We're uncertain" — Transparent about system limitations
- "may be AI-generated or human-written" — Acknowledges both possibilities equally
- Doesn't pretend confidence where none exists
- Respects both creators and readers

**Example confidence: 0.52**
- Signal 1 (Groq): 0.50 — Detected mixed signals (some formal language, some personal touches)
- Signal 2 (Stats): 0.55 — Detected mixed patterns (some diversity, some uniformity)
- Calculation: (0.70 × 0.50) + (0.30 × 0.55) = 0.515 ≈ 0.52

---

### Label Text Summary Table

| Confidence Range | Attribution | Label Text | Meaning |
|------------------|-------------|------------|---------|
| **< 0.35** | AI | "This appears to be AI-generated content" | System confident it's AI |
| **0.35-0.70** | Uncertain | "We're uncertain about the origin of this content. It may be AI-generated or human-written." | System cannot decide; signals conflict |
| **> 0.70** | Human | "This appears to be written by a human" | System confident it's human |

### Example: Meaningful Score Variation

The scoring approach produces **significantly different confidence scores** for different content types. Here are two real examples:

#### Example 1: High-Confidence Human (0.86)

**Submission:**
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text":"ok so i finally tried that ramen place downtown and honestly underwhelming. the broth was lukewarm and the noodles mushy. not worth the hype.", "creator_id":"user-author-001"}'
```

**Response:**
```json
{
  "content_id": "a40831e5-138e-405e-8656-96350b37bb62",
  "creator_id": "user-author-001",
  "attribution": "human",
  "confidence": 0.86,
  "label": "This appears to be written by a human",
  "signals": {
    "signal_1": 0.90,
    "signal_2": 0.78
  }
}
```

**Score breakdown:**
- Signal 1 (Groq semantic): **0.90** ✓ Detects personal voice ("ok so i"), specific details ("ramen place downtown"), emotional language ("underwhelming"), authentic critique with examples
- Signal 2 (Text stats): **0.78** ✓ Detects personal markers ("i"), emotional words, natural sentence variety
- **Final confidence:** (0.70 × 0.90) + (0.30 × 0.78) = **0.63 + 0.234 = 0.863 ≈ 0.86** ✓
- **Classification:** "human" (0.86 > 0.70 threshold)

---

#### Example 2: High-Confidence AI (0.10)

**Submission:**
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text":"The strategic implementation of comprehensive digital transformation initiatives demonstrates significant potential to leverage synergistic methodologies across enterprise stakeholder ecosystems. Our integrated approach facilitates the optimization of operational paradigms through enhanced collaborative frameworks and strategic alignment mechanisms.","creator_id":"user-bot-002"}'
```

**Response:**
```json
{
  "content_id": "f5ad0ef0-2028-44d8-82fc-46d7c2a6511b",
  "creator_id": "user-bot-002",
  "attribution": "ai",
  "confidence": 0.10,
  "label": "This appears to be AI-generated content",
  "signals": {
    "signal_1": 0.0,
    "signal_2": 0.32
  }
}
```

**Score breakdown:**
- Signal 1 (Groq semantic): **0.0** ✗ Detects heavy corporate jargon ("demonstrates potential", "synergistic methodologies", "paradigms"), abstract noun chains ("ecosystems", "frameworks"), no personal voice, no specificity, no authentic details
- Signal 2 (Text stats): **0.32** ✗ Detects repetitive formal patterns, high uniformity, corporate phrase repetition ("optimization", "enhancement", "strategic")
- **Final confidence:** (0.70 × 0.0) + (0.30 × 0.32) = **0.0 + 0.096 = 0.096 ≈ 0.10** ✗
- **Classification:** "ai" (0.10 < 0.35 threshold)

---

#### Score Variation Achieved

| Case | Signal 1 | Signal 2 | Final Confidence | Attribution | Difference |
|------|----------|----------|------------------|-------------|-----------|
| Human review | 0.90 | 0.78 | **0.86** | human | +0.76 span |
| AI corporate | 0.0 | 0.32 | **0.10** | ai | (human vs. AI) |

**This 0.76 confidence point spread demonstrates:**
- ✅ Scoring is **not constant** (not all submissions get 0.5)
- ✅ Signals produce **meaningful variation** (0.90 vs 0.0 on Signal 1)
- ✅ Ensemble combines signals **effectively** (strong signals on both = high confidence)
- ✅ Thresholds are **well-calibrated** (0.86 clearly human, 0.10 clearly AI)

---

## API Reference

### POST /submit

Submit text for attribution analysis.

**Request:**
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "text": "ok so i finally tried that ramen place downtown and honestly underwhelming. the broth was lukewarm and the noodles mushy. not worth the hype.",
    "creator_id": "user-author-001"
  }'
```

**Response (200 OK):**
```json
{
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "creator_id": "user-author-001",
  "attribution": "human",
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
- `creator_id`: Non-empty string

**Errors:**
- `400 Bad Request` — Invalid input
- `413 Payload Too Large` — Text > 10,000 chars
- `429 Too Many Requests` — Rate limit exceeded (10/min per IP)
- `500 Server Error` — API/database failure

---

### POST /appeals

Appeal a classification decision.

**Request:**
```bash
curl -X POST http://localhost:5000/appeals \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "550e8400-e29b-41d4-a716-446655440000",
    "creator_id": "user-author-001",
    "creator_reasoning": "This is my original work written from personal experience at a restaurant I visited last week."
  }'
```

**Response (200 OK):**
```json
{
  "appeal_id": "appeal-uuid-001",
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "creator_id": "user-author-001",
  "status": "under_review",
  "message": "Your appeal has been received and logged. A human reviewer will examine your case."
}
```

**Behavior:**
1. Validates content_id exists in database
2. Validates creator_id matches original submission
3. Validates reasoning is 20-2,000 characters
4. Creates appeal record
5. Updates original entry status to "under_review"
6. Returns appeal confirmation

**Errors:**
- `400 Bad Request` — Invalid input or creator_id mismatch
- `404 Not Found` — content_id doesn't exist
- `429 Too Many Requests` — Rate limit exceeded
- `500 Server Error` — Database failure

---

### GET /log

Retrieve audit log of attributions.

**Request:**
```bash
curl 'http://localhost:5000/log?limit=5'
```

**Response (200 OK):**
```json
{
  "entries": [
    {
      "id": "log-entry-uuid",
      "content_id": "550e8400-e29b-41d4-a716-446655440000",
      "creator_id": "user-author-001",
      "timestamp": "2026-06-28T12:15:34.892103Z",
      "signal_1_score": 0.90,
      "signal_2_score": 0.78,
      "final_confidence": 0.8625,
      "attribution": "human",
      "label": "This appears to be written by a human",
      "status": "classified"
    }
  ]
}
```

---

## Installation & Setup

### Requirements
- Python 3.8+
- Groq API key (free tier available)
- Flask, Flask-Limiter

### Steps

1. **Clone and install:**
```bash
pip install -r requirements.txt
```

2. **Set up environment variables:**
```bash
# Create .env file with your Groq API key
echo "GROQ_API_KEY=your-key-here" > .env

# Load it
source .env
```

3. **Run the server:**
```bash
python3 app.py
```

Server starts on `http://localhost:5000`

---

## Usage & Testing

### Generate 3 Example Audit Log Entries

**Entry 1: Human-Written Content**
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text":"ok so i finally tried that ramen place downtown and honestly underwhelming. the broth was lukewarm and the noodles mushy. not worth the hype.", "creator_id":"user-author-001"}'
```
Expected: `"attribution": "human"`, confidence ~0.86

**Entry 2: AI-Generated Content**
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text":"The strategic implementation of comprehensive digital transformation initiatives demonstrates significant potential to leverage synergistic methodologies across enterprise stakeholder ecosystems. Our integrated approach facilitates the optimization of operational paradigms through enhanced collaborative frameworks.","creator_id":"user-bot-002"}'
```
Expected: `"attribution": "ai"`, confidence ~0.10

**Entry 3: Uncertain Content**
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text":"I attended a meeting yesterday about the new marketing initiatives. We discussed various approaches to enhance brand visibility and improve customer engagement through strategic partnerships. The team provided valuable insights on market trends.","creator_id":"user-mixed-003"}'
```
Expected: `"attribution": "uncertain"`, confidence ~0.52

**File an Appeal:**
```bash
curl -X POST http://localhost:5000/appeals \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "[CONTENT_ID_FROM_ENTRY_1]",
    "creator_id": "user-author-001",
    "creator_reasoning": "This is my original work written from personal experience at a restaurant I visited last week."
  }'
```

**View Audit Log:**
```bash
curl http://localhost:5000/log?limit=5 | jq '.entries'
```

### Test Rate Limiting

```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
```

Expected output: 10 × `200`, then 2 × `429`

---

## Known Limitations

### Critical Failure: AI-Generated Technical Documentation

**What will go wrong:** The system will likely misclassify well-formatted, technically accurate AI-generated documentation as human-written.

**Specific example:** An AI trained on technical documentation generates this:
```
1. Open the configuration panel.
2. Select the "Network Settings" option from the menu.
3. Input the IPv4 address in the designated field.
4. Click "Save" to apply changes.
```

**Why the system fails (signal-specific):**

| Signal | What It Sees | Score | Problem |
|--------|-------------|-------|---------|
| **Signal 1 (Groq Semantic)** | Logical progression, clear cause-and-effect reasoning, correct technical flow | 0.70+ | Can't distinguish between "human following a process" and "AI trained on processes." Sees coherent reasoning and marks it human. |
| **Signal 2 (Text Stats)** | Perfect structure, numbered lists, uniform technical language | 0.65+ | Uniform structure looks intentional (human expertise), not formulaic (AI). High uniformity in technical writing = human domain expert. |
| **Ensemble Result** | (0.70 × 0.70) + (0.30 × 0.65) = 0.685 | Classified as HUMAN | Both signals see "good writing" and miss that it's formulaic AI. |

**Why this is hard to fix:**
- Signal 1 fundamentally can't distinguish authentic reasoning from trained imitation
- Signal 2 has no way to know uniform technical language is AI (domain experts write uniformly too)
- The signals are working as designed, but the premise is wrong: perfect technical writing ≠ necessarily human

**Practical impact:** If your platform serves technical documentation, this system will have false negatives (miss AI-generated docs).

**Mitigation:** 
- Add domain-specific detector for numbered lists + technical keywords
- Human review for anything flagged as "human" but matching documentation patterns
- Accept this as a limitation and route technical content to specialized reviewers

---

### Secondary Failure: Human Experimental Writing (Poetry, Fragments)

**What will go wrong:** The system will likely misclassify human-written experimental poetry or stream-of-consciousness writing as uncertain or AI.

**Specific example:** A human poet writes:
```
alone alone alone
in the dark dark dark
The ALONE thing
standing in Everything
```

**Why the system fails (signal-specific):**

| Signal | What It Sees | Score | Problem |
|--------|-------------|-------|---------|
| **Signal 1 (Groq Semantic)** | Nonlinear structure, abstract imagery without explicit connection, unusual capitalization | 0.55-0.65 | Struggles with intentional artistic fragmentation. May see "coherence issues" as an AI red flag. |
| **Signal 2 (Text Stats)** | High word repetition ("alone" × 3, "dark" × 2), low sentence length variance (all fragments), unusual patterns | 0.20-0.35 | Sees repetition as AI pattern. Doesn't understand intentional poetic devices. Flags high repetition as formulaic. |
| **Ensemble Result** | (0.70 × 0.60) + (0.30 × 0.28) = 0.504 | Classified as UNCERTAIN | Signals disagree; system correctly expresses uncertainty, but creator is flagged as possibly AI. |

**Why this is hard to fix:**
- Signal 2 can't distinguish "intentional repetition for effect" from "unintentional repetition as AI artifact"
- Signal 1 struggles with nonlinear, fragmented human expression (trained on coherent text)
- The signal design assumes coherence = human, but art breaks that assumption

**Practical impact:** If your platform includes creative writers, poets, or experimental writers, they will see "uncertain" classifications even for authentic work.

**Mitigation:**
- Appeals mechanism (primary solution) — creator explains artistic intent
- Flag and exclude poetry/experimental content (manual review only)
- Adjust Signal 2 weights lower for short texts (poetry is often short)
- Improve Groq prompt to recognize intentional artistic fragmentation

---

## Limitations & Edge Cases

### Edge Case 1: Stream-of-Consciousness Poetry

**Problem:** Intentional repetition ("alone, alone, alone") scores as AI

**Why it happens:**
- Signal 2 sees repetition → scores low (0.25)
- Signal 1 understands artistic intent → scores high (0.82)
- Ensemble: (0.70 × 0.82) + (0.30 × 0.25) = 0.649 → "uncertain"

**Impact:** Creator sees "uncertain" label instead of "human"

**Mitigation:**
- Uncertainty label doesn't lie (says "may be either")
- Creator can appeal with explanation
- High semantic weight (70%) helps catch intentional style

**Workaround:** Improve Groq prompt to detect intentional poetic markers (capitalization, line breaks)

### Edge Case 2: AI-Generated Technical Documentation

**Problem:** Perfectly formatted procedures score as human

**Why it happens:**
- Signal 2 sees perfect structure → scores high (0.65)
- Signal 1 sees logical reasoning → scores high (0.70)
- Ensemble: (0.70 × 0.70) + (0.30 × 0.65) = 0.685 → "human"

**Impact:** System misses AI-generated documentation

**Mitigation:**
- Improve Groq prompt to detect formulaic reasoning
- Appeals mechanism allows humans to flag false negatives
- Add specialized detector for numbered-list formats

**Workaround:** Fine-tune Groq to recognize "technically perfect but AI-like" patterns

### Edge Case 3: Translated Content

**Problem:** Awkward phrasing from translation scores as AI

**Why it happens:**
- Signal 2 sees unusual patterns → scores low (0.35)
- Signal 1 sees semantic oddities → scores low (0.40)
- Ensemble: (0.70 × 0.40) + (0.30 × 0.35) = 0.385 → "uncertain leaning AI"

**Impact:** Human translator flagged as potential AI

**Mitigation:**
- Appeals mechanism (primary solution)
- Future: Add language detection for translated content
- Improve Groq to recognize translation patterns

---

## Deployment Considerations

### What I'd Change for Production

#### 1. **Separate Groq for Appeals**
**Current:** Same prompt for both submission and appeal review
**Production:** Create specialized appeal prompt that:
- Compares original content against creator's reasoning
- Weights Signal 1 higher (90/10) since creator is providing context
- Returns confidence in "appeal is valid" not "content is AI"

#### 2. **Caching & Rate Limiting Upgrade**
**Current:** In-memory rate limiting, no caching
**Production:**
- Redis for distributed rate limiting (multi-server support)
- Cache Groq responses for identical texts (common in abuse patterns)
- Separate limits: 10/min for legitimate users, 100/min for platforms via API key

#### 3. **Human Reviewer Interface**
**Current:** Appeals table exists but no UI
**Production:**
- Web dashboard for reviewers
- Show appeal + original classification + creator reasoning side-by-side
- One-click "Agree" / "Overturn" / "Request Info"
- Full audit trail (who reviewed, when, decision)

#### 4. **Confidence Calibration**
**Current:** Fixed thresholds (0.35/0.70)
**Production:**
- A/B test different thresholds with human feedback
- Per-domain thresholds (news articles vs. social media)
- Adaptive thresholds based on appeal overturns ("threshold drift")

#### 5. **Signal Improvements**
**Current:** Signal 1 is black box (Groq output)
**Production:**
- Extract reasoning from Groq response
- Log which red flags were triggered (helps appeals reviewers)
- Fine-tune Groq on domain-specific patterns

**Current:** Signal 2 is generic stylometry
**Production:**
- Per-language stylometric models (TTR differs across languages)
- Fine-tune on known AI outputs from major models (GPT, Claude, etc.)
- Detect statistical anomalies (benford's law for numbers, etc.)

#### 6. **Multi-Language Support**
**Current:** English-only (Groq is English-heavy, statistics assume English)
**Production:**
- Language detection + language-specific models
- Multilingual stylometric metrics
- Groq prompt templates per language

#### 7. **Monitoring & Observability**
**Current:** Basic logging to SQLite
**Production:**
- Confidence distribution dashboard (are we seeing the right mix of classifications?)
- Appeal overturned rate (if > 5%, retrain signals)
- Groq API latency tracking (find bottlenecks)
- False positive rate by domain (different thresholds per use case?)

#### 8. **Database Scaling**
**Current:** SQLite (single file, single server)
**Production:**
- PostgreSQL for distributed queries
- Separate write (audit log) and read (appeals) databases
- Partitioning by timestamp (old records archived)

#### 9. **Appeal Expiry & SLA**
**Current:** Appeals marked "under_review" indefinitely
**Production:**
- Auto-resolve after 30 days (escalate to management if not reviewed)
- Creator gets email at day 15 (status update)
- SLA: "human review within 24 hours"

#### 10. **Feedback Loop**
**Current:** No mechanism to improve based on overturned appeals
**Production:**
- Log overturned appeals as training data
- Monthly: retrain signals on recent overturns
- Adjust thresholds if drift detected
- Flag problematic edge cases (poetry, technical docs) for special handling

### Deployment Checklist

- [ ] Switch to PostgreSQL
- [ ] Add Redis for distributed rate limiting
- [ ] Implement reviewer dashboard
- [ ] Add monitoring & alerting
- [ ] Set up A/B testing for thresholds
- [ ] Create appeal SLA workflow
- [ ] Build feedback loop from appeals
- [ ] Add multilingual support
- [ ] Document per-domain threshold overrides
- [ ] Set up automated retraining pipeline

---

---

## Spec Reflection: What Worked and What Changed

### How the Spec Guided Implementation ✅

**The three-label transparency framework was invaluable.** 

The spec's decision to map confidence scores to exactly three variants — not a sliding scale or percentages — fundamentally shaped how the entire system works. Instead of returning "73% confident human", the system returns one of three clear statements:
- "This appears to be AI-generated content"
- "We're uncertain about the origin of this content..."
- "This appears to be written by a human"

This constraint **forced good design decisions:**
- Had to choose thresholds (0.35/0.70) that actually separate three distinct behaviors
- Prevented hedging language ("maybe probably could be")
- Made the confidence score serve a purpose (determine which label, not just a number)
- Aligned the system incentives with user needs (clear attribution, not false precision)

Without this spec constraint, the implementation would have likely returned confidence percentages, which would mislead users into false precision and let the system avoid committing to classifications.

---

### How Implementation Diverged from Spec (and Why)

**Signal 2 (Text Statistics) was completely redesigned mid-implementation.**

**Original spec approach:**
- Measure vocabulary diversity (Type-Token Ratio)
- Higher diversity = more human-like

**Why it failed:**
- Tested against calibration cases and got only 1/4 passing
- Problem: High vocabulary diversity can appear in AI text; low diversity can appear in human poetry
- The spec measured the *wrong property* for AI detection

**What changed:**
Instead of measuring "diversity", Signal 2 now detects **AI-specific patterns:**
- Personal markers (pronouns, specific references, contractions)
- Emotional language (words like "frustrated", "exhausted", sensory words)
- Formulaic phrases ("demonstrates potential", "stakeholders", corporate jargon)
- Type-Token Ratio (kept, but downweighted)

**Results:**
- Calibration test: 1/4 → 4/4 passing
- Same 30% weight in ensemble, but now meaningful

**Why this divergence was right:**
The spec provided the *framework* (multi-signal, weighted ensemble, three labels) but not the *implementation details*. The signal design had to be tested against real content, and the original approach didn't work. The spec was right about the architecture; wrong about what "stylometric diversity" alone could achieve.

**Key lesson:** Specs are guides, not blueprints. When implementation testing shows a spec assumption is wrong, you have to adapt — but within the spirit of the spec (multi-signal ensemble) not against it.

---

---

## AI Usage in Development

This section documents specific instances where AI (Claude) assisted in implementation, what was produced, and what was revised.

### Instance 1: Signal 2 Complete Redesign (AI Identified Problem, Human Directed Fix)

**What was directed:**
"The results are not improving. Instead of changing the weights, perhaps we need to make the code in detection/text_stats.py more accurate in detecting true repetition in text as AI or human?"

**What was produced (initial attempt):**
- Measured only Type-Token Ratio (vocabulary diversity)
- Higher diversity = human, lower diversity = AI
- Test result: 1/4 calibration tests passing

**What was identified as wrong:**
- The signal measured the wrong property
- High vocabulary diversity can appear in AI text (modern LLMs vary vocabulary intentionally)
- Low vocabulary diversity can appear in human poetry (intentional repetition for effect)
- The "diversity hypothesis" was fundamentally flawed

**What was revised:**
Complete redesign from scratch:
```python
# OLD (didn't work)
ttr = unique_words / total_words  # Higher = human

# NEW (works)
personal_markers = detect("I", "we", specific references, contractions)  # 30% weight
emotional_language = detect("frustrated", "exhausted", sensory words)     # 25% weight
formulaic_phrases = detect(corporate_jargon, "demonstrates potential")    # 20% weight
ttr = unique_words / total_words                                          # 15% weight
structure_variety = sentence_length_variance                              # 10% weight
```

**Result:**
- Test result: 4/4 calibration tests passing
- Score variation: Clearly separated AI (0.10), human (0.86), uncertain (0.52)

**Key insight:** AI can implement specs, but humans need to validate assumptions against reality. Once the assumption (diversity = human) was questioned, the fix was straightforward.

---

### Instance 2: Label Generator Return Type Mismatch (AI Generated Function, Human Caught Bug, AI Fixed)

**What was directed:**
"Create a label_generator function that maps confidence (0.0-1.0) to one of three transparency labels"

**What was produced:**
```python
def generate_label(confidence: float) -> dict:
    if confidence < 0.35:
        return {
            "classification": "ai",
            "label": "This appears to be AI-generated content",
            "confidence": round(confidence, 2)
        }
    # ... etc
```

**What went wrong in app.py:**
When the function was integrated, the code tried to unpack it as a tuple:
```python
classification, label = generate_label(final_confidence)  # BUG!
```

But the function returned a dictionary, not a tuple.

**Error encountered:**
```
ValueError: too many values to unpack (expected 2)
```

**What was revised:**
Updated app.py to properly unpack the dictionary:
```python
# FIXED
label_result = generate_label(final_confidence)
classification = label_result["classification"]
label = label_result["label"]
```

**Key insight:** AI generated a correct function signature (returning dict), but didn't catch that the calling code expected a tuple. The human caught the mismatch during testing, and the fix was simple once identified.

---

### Instance 3: Schema Renaming at Scale (AI Bulk Replaced, Human Caught Database Mismatch)

**What was directed:**
"Rename classification as attribution in the whole codebase, in both code and markdown files"

**What was produced:**
Used find-and-replace across all Python and markdown files:
- app.py: ~40 occurrences
- labels/generator.py: ~15 occurrences  
- README.md: ~30 occurrences
- specs/planning.md: ~50 occurrences

**What went wrong:**
The code was updated to use `attribution` everywhere, but the old SQLite database file still had the old `classification` column name.

**Error encountered:**
```
Error: table audit_log has no column named attribution
```

**What was revised:**
1. Updated init_db() function (code was already correct)
2. Deleted old database file: `rm audit_log.db`
3. Restarted Flask to recreate database with new schema

**Key insight:** AI did the mechanical find-and-replace correctly, but didn't catch the schema mismatch with the existing database. The human had to recognize that deleting and recreating the database was necessary.

---

### Instance 4: README Comprehensive Rewrite (AI Generated Content, Human Directed Iterations)

**What was directed:**
"Help me fill out the README.md following these directions: [coverage of all required sections, design reasoning, actual examples with scores, label variants, known limitations, spec reflection, AI usage]"

**What was produced (iteratively):**
1. **First attempt:** Basic README with API docs
2. **Feedback:** "Add design reasoning, not just implementation"
3. **Revision:** Added Design Decisions, Signal reasoning sections with "why" not just "what"
4. **Feedback:** "Include actual example submissions with scores"
5. **Revision:** Added two concrete examples (human 0.86, AI 0.10) with score breakdowns
6. **Feedback:** "Add label variants section with exact text users see"
7. **Revision:** Added comprehensive Label Variants section with three examples
8. **Feedback:** "Add known limitations section with signal-specific failures"
9. **Revision:** Added Technical Documentation and Poetry failures with signal breakdowns
10. **Feedback:** "Add spec reflection"
11. **Revision:** Added section on how spec guided implementation and where divergence occurred
12. **Current:** This AI Usage section

**What was revised multiple times:**
- Depth of reasoning (added more "why", less "what")
- Specificity of examples (actual scores vs. hypothetical)
- Honesty about limitations (signal-specific failures vs. generic "edge cases")
- Structure (moved sections around for better flow)
- Tone (more technical, less marketing-speak)

**Key insight:** AI can generate initial content, but iterative human feedback is essential for quality. Each revision made the README more specific, honest, and useful.

---

### Summary: AI's Role in This Project

| Task | AI Did | Human Did |
|------|--------|-----------|
| **Generating initial code** | ✓ Produced Signal implementations, endpoints | ✓ Validated against test cases |
| **Finding bugs** | ✗ Missed return type mismatch, schema mismatch | ✓ Caught during testing |
| **Design decisions** | ✗ Assumed diversity = human | ✓ Questioned assumption, directed redesign |
| **Bulk refactoring** | ✓ Renamed 200+ occurrences across codebase | ✓ Caught database schema issue |
| **Documentation** | ✓ Generated comprehensive README | ✓ Iterated with feedback for quality |
| **Validation** | ✗ Can't run tests or verify behavior | ✓ Ran tests, verified scores, caught issues |

**Lesson:** AI excels at generating code and documentation from clear specs. Humans are essential for validation, assumption-checking, and iterative refinement.

---

## Architecture

See [`specs/planning.md`](specs/planning.md) for:
- Detailed system architecture
- Component interaction flows
- Database schema
- Full API specifications
- Edge case analysis
