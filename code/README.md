# HackerRank Orchestrate - Support Triage Agent

A production-grade AI agent system that automatically triages and responds to support tickets from multiple companies (Claude, HackerRank, Visa) using a 2-agent pipeline with semantic search and local embeddings.

**READ THIS FILE COMPLETELY.** It contains everything you need to understand and run the system.

---

## 🎯 Quick Start (2 Minutes)

```bash
# 1. Setup embeddings (first time only)
python3 embed_corpus.py

# 2. Run with default settings (2 tickets in parallel)
python3 main.py

# 3. Check output
cat ../support_tickets/output.csv

# OR with custom parallelism
BATCH_CONCURRENCY=5 python3 main.py
```

---

## 📋 System Overview

**Input:** CSV file with support tickets  
**Output:** CSV file with triaged responses  
**Processing:** 2-agent pipeline with semantic search

### What Each Agent Does

**Agent 1: Classifier + Retriever**
- Analyzes ticket and classifies it
- Searches relevant support documents using semantic search
- Returns: classification results + relevant doc sections

**Agent 2: Responder**
- Generates response based on documents (or escalates if needed)
- Saves result to output CSV
- Returns: final response

### Processing Flow

```
Read CSV Tickets
        ↓
Create Ticket Objects (one per ticket)
        ↓
Process in Parallel (respects BATCH_CONCURRENCY)
        ↓
Agent 1 per ticket: Classify + Search Docs
        ↓
Agent 2 per ticket: Generate Response or Escalate
        ↓
Save to output.csv
        ↓
Done!
```

---

## 🏗️ Architecture: Object-Based Design

### The Ticket Object

Each support ticket is a **self-contained Python object** that manages:

```
Ticket(ticket_id=1, company="Claude", issue="...", subject="...")
├── State
│   ├── response text
│   ├── classification (product area, request type)
│   └── escalation status
│
├── Tool Call Limits (PER-TICKET, INDEPENDENT)
│   ├── search_documents: 0/3 calls
│   └── save_response_to_csv: 0/1 call
│
└── Methods
    ├── can_call_tool(tool_name)
    ├── set_response(...)
    └── get_result()
```

### Why This Design?

✅ **No Global State** - Each ticket is independent  
✅ **No Interference** - Parallel tickets don't affect each other  
✅ **Independent Limits** - Each ticket has own tool call budget  
✅ **Easy Testing** - Self-contained objects  
✅ **Clean Code** - Clear responsibilities  

### Context Management

Uses Python's `contextvars.ContextVar` to track current Ticket:
- Each parallel execution has own Ticket instance
- Works across async + threading boundaries
- No race conditions or shared state

---

## ⚙️ Configuration: Single Environment Variable

### `BATCH_CONCURRENCY` - That's It!

Controls how many tickets execute **in parallel at the same time**. Uses a semaphore to enforce the limit.

```bash
# Set via environment (recommended)
BATCH_CONCURRENCY=3 python3 main.py

# Or set in .env file
echo "BATCH_CONCURRENCY=3" >> .env
python3 main.py

# Or via CLI (overrides env)
python3 main.py --concurrency 3

# Default (if not set)
python3 main.py  # Uses BATCH_CONCURRENCY=2
```

### Settings Guide

| BATCH_CONCURRENCY | Tickets in Parallel | Use Case |
|------------------|-------------------|----------|
| 1 | 1 | Sequential - one ticket at a time (safe) |
| 2 | 2 | Default (balanced) |
| 3 | 3 | Recommended (good speed) |
| 5 | 5 | Fast (high resource usage) |
| 10+ | 10+ | Very fast (may have errors) |

**How It Works:** 
- All tickets are created as tasks immediately
- A single `asyncio.Semaphore(max_concurrent)` controls execution
- Only `max_concurrent` tickets can be processing at the same time
- When one finishes, the next waiting task acquires the semaphore

### Examples

```bash
# Safe (single ticket, no errors)
BATCH_CONCURRENCY=1 python3 main.py

# Default (2 at a time)
python3 main.py

# Recommended (3 at a time)
BATCH_CONCURRENCY=3 python3 main.py

# Fast (5 at a time)
BATCH_CONCURRENCY=5 python3 main.py

# From .env file (loads automatically)
python3 main.py
```

---

## 🔍 Semantic Search & Local Embeddings

### How It Works

1. **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim vectors)
2. **Vector Database:** SQLite (local, no cloud)
3. **Search:**
   - Convert ticket issue to embedding
   - Find similar docs using cosine similarity
   - Extract only **relevant sections**
   - Return top 3 results

4. **Smart Extraction:**
   - Splits docs by headers (##, ###)
   - Scores sections by relevance
   - Returns only relevant content
   - **Total: < 2000 chars per search**

### Setup Embeddings

```bash
# First time only - embed all support documents
python3 embed_corpus.py

# This:
# 1. Loads support docs from data/{company}/
# 2. Embeds them using all-MiniLM-L6-v2
# 3. Stores vectors in SQLite
# 4. Ready for semantic search
```

### Example

When Agent 1 processes "I lost access to my workspace":
- Searches Claude's knowledge base
- Finds relevant sections on account recovery
- Returns only the steps (not full docs)
- Agent 2 uses these sections to respond

---

## 🛠️ Tool Call Limits (Per-Ticket)

Each ticket has **independent** limits:

```
Ticket #1: search_documents (3/3 used)  ← ticket 1's limit
Ticket #2: search_documents (0/3 used)  ← ticket 2's limit (independent!)
```

### Tools

#### `search_documents(company, query)` - Agent 1 uses
- **Limit:** 3 calls per ticket
- **Input:** Company + search query
- **Output:** Top 3 doc sections (< 2000 chars total)
- **Example:** `search_documents("Claude", "lost access")`

#### `save_response_to_csv(...)` - Agent 2 uses
- **Limit:** 1 call per ticket
- **Input:** ticket_id, status, product_area, response, justification, request_type
- **Output:** Appends row to output.csv
- **Example:** `save_response_to_csv(1, "replied", "access", "Here's how...", "From docs", "product_issue")`

### Example Limit Behavior

```python
ticket = Ticket(ticket_id=1, ...)

# Calls 1-3: Allowed
ticket.can_call_tool("search_documents")  # (True, 1)
ticket.can_call_tool("search_documents")  # (True, 2)
ticket.can_call_tool("search_documents")  # (True, 3)

# Call 4: REJECTED
ticket.can_call_tool("search_documents")  # (False, 4)

# Different ticket has own limit
ticket2 = Ticket(ticket_id=2, ...)
ticket2.can_call_tool("search_documents")  # (True, 1) - Fresh!
```

---

## 📂 Project Structure

```
code/
├── README.md                    # THIS FILE - Complete guide
├── main.py                      # CLI entry point
├── embed_corpus.py              # Setup: embed docs for vector DB
│
├── models/
│   ├── __init__.py
│   └── ticket.py                # Ticket class (state + limits)
│
├── tools/
│   ├── __init__.py
│   ├── ticket_context.py        # ContextVar for current Ticket
│   ├── search_tools.py          # search_documents tool
│   └── csv_tools.py             # save_response_to_csv tool
│
├── ticket/
│   ├── __init__.py
│   └── ticket_processor.py      # Orchestrates 2-agent pipeline
│
├── agents/
│   ├── __init__.py
│   ├── factory.py               # Creates agents
│   ├── classifier_retriever.py  # Agent 1
│   └── responder.py             # Agent 2
│
├── embeddings/
│   ├── __init__.py
│   ├── db.py                    # SQLite vector database
│   └── smart_extraction.py      # Intelligent doc extraction
│
├── observability/
│   ├── __init__.py
│   ├── ticket_logger.py         # Logging
│   └── guardrails.py            # Safety checks
│
├── services/
│   ├── __init__.py
│   └── agent_service.py         # Agent factory
│
└── tests/
    ├── test_single_ticket.py
    ├── test_smart_extraction.py
    └── README.md
```

---

## 🚀 Running the System

### 1. First Time Setup

```bash
# Copy environment template
cp .env.example .env

# Initialize vector database (embeds all docs)
python3 embed_corpus.py
# Creates: embeddings/corpus.db
```

### 2. Test on Sample Tickets

```bash
# Process sample tickets to verify everything works
python3 main.py --test

# Check output
cat ../support_tickets/output.csv
```

### 3. Process Real Tickets

```bash
# Default (2 tickets in parallel)
python3 main.py

# Faster (5 tickets in parallel)
BATCH_CONCURRENCY=5 python3 main.py

# Slower but safer (1 ticket at a time)
BATCH_CONCURRENCY=1 python3 main.py
```

### 4. Check Results

```bash
# View output CSV
cat ../support_tickets/output.csv

# Count rows
wc -l ../support_tickets/output.csv
```

---

## 📊 Output Format

**File:** `support_tickets/output.csv`

**Columns:**
- `issue` - Original support issue
- `subject` - Ticket subject
- `company` - Claude, HackerRank, or Visa
- `response` - AI response or escalation reason
- `product_area` - Category (e.g., "access", "billing")
- `status` - "replied" or "escalated"
- `request_type` - "product_issue", "feature_request", "bug", "invalid"
- `justification` - Which docs were used / why escalated

**Example Row:**
```csv
I lost access to my workspace,Lost Access,Claude,To restore access try....,access,replied,product_issue,Used account-recovery docs
```

---

## 🔄 Parallel Processing Details

### How BATCH_CONCURRENCY Works

Simple semaphore-based concurrency control:

```python
# 1. Create ALL tasks at once
tasks = [process_ticket(ticket) for ticket in tickets]

# 2. Semaphore limits concurrent execution
semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)
# Each task acquires semaphore before processing:
#   async with semaphore:
#       process_ticket()

# 3. Run all tasks - semaphore naturally enforces limit
results = await asyncio.gather(*tasks)
```

**Timeline Example (29 tickets, BATCH_CONCURRENCY=2):**
```
[0-1s]   T1 ████ T2 ████ (2 running)
[1-2s]   T3 ████ T4 ████ (2 running)
[2-3s]   T5 ████ T6 ████ (2 running)
...
[14-15s] T29 ████ (1 running, others done)

Total: ~15 seconds (29 / 2 parallel)
```

**BATCH_CONCURRENCY=1 (Sequential):**
```
[0-1s]   T1 ████ (1 running)
[1-2s]   T2 ████ (1 running)
[2-3s]   T3 ████ (1 running)
...
[29-30s] T29 ████ (1 running)

Total: ~29 seconds (no parallelism)
```

### Thread Safety

- **CSV writes:** Protected by `threading.Lock`
- **Context isolation:** Each ticket has own `ContextVar`
- **No shared state:** Ticket objects are independent
- **Semaphore enforcement:** `asyncio.Semaphore(max_concurrent)` guarantees only N tickets execute concurrently

### Verifying Concurrency Works

Test scripts demonstrate proper semaphore enforcement:

```bash
# Test sequential (1 ticket at a time)
python3 tests/test_concurrency_1.py

# Test parallel (2 tickets at a time)
python3 tests/test_concurrency.py
```

Expected behavior:
- With max=1: tickets run one after another (sequential)
- With max=2: tickets run in pairs (truly parallel)

---

## ⚡ Performance Tips

### Fast Processing
```bash
BATCH_CONCURRENCY=5 python3 main.py
# Uses: 5 parallel tickets
# Higher concurrency = faster but more resource usage
```

### Safe Processing
```bash
BATCH_CONCURRENCY=1 python3 main.py
# Uses: 1 ticket at a time (no parallelism)
# Lowest errors, predictable, slower
```

### Balanced (Recommended)
```bash
BATCH_CONCURRENCY=3 python3 main.py
# Uses: 3 parallel tickets
# Good balance between speed and stability
```

---

## 🧪 Testing

```bash
# Test smart extraction (docs → relevant sections)
python3 tests/test_smart_extraction.py

# Test single ticket end-to-end
python3 tests/test_single_ticket.py

# Test agent sequencing
python3 tests/test_agent_sequencing.py
```

---

## 🔧 Troubleshooting

### Litellm Logging Errors
```bash
# Reduce parallelism
BATCH_CONCURRENCY=1 python3 main.py
```

### CSV File Issues
```bash
# Clear corrupted output
rm ../support_tickets/output.csv

# Re-run (creates fresh file)
python3 main.py
```

### Slow Processing
```bash
# Increase parallelism
BATCH_CONCURRENCY=5 python3 main.py

# OR ensure Ollama is running
ollama serve
```

### Embedding Issues
```bash
# Rebuild vector database
rm embeddings/corpus.db
python3 embed_corpus.py
python3 main.py
```

---

## 🎯 One README to Rule Them All

This file contains **everything** you need:

✅ How it works (2-agent pipeline)  
✅ How to run it (python3 main.py)  
✅ How to configure it (BATCH_CONCURRENCY env)  
✅ How it scales (parallel processing)  
✅ How embeddings work (semantic search)  
✅ Tool call limits (per-ticket)  
✅ Architecture (Ticket object)  
✅ Troubleshooting (quick fixes)  

**No other docs needed!** Everything is here. 🚀
