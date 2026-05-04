# Test Suite for HackerRank Orchestrate

This folder contains comprehensive tests for the 2-agent support triage system.

## Test Files

### 1. `test_smart_extraction.py`
**Purpose**: Verify smart section extraction from documents

**Tests**:
- Parse YAML front matter from markdown
- Split documents into sections by headers
- Score sections by relevance to queries
- Extract only relevant content (< 800 chars)
- Extract action items (numbered steps, bullets, code)
- Verify condensed output stays under char limit

**Run**:
```bash
cd code
python3 tests/test_smart_extraction.py
```

**Expected Output**:
```
✅ test_parse_yaml_front_matter PASSED
✅ test_split_into_sections PASSED
✅ test_score_section_reset_password PASSED
✅ test_score_section_delete_account PASSED
✅ test_extract_relevant_section PASSED
✅ test_extract_action_items PASSED
✅ test_condensed_output PASSED
✅ test_multiple_queries PASSED
RESULTS: 8 passed, 0 failed
```

---

### 2. `test_single_ticket.py`
**Purpose**: End-to-end test of a single ticket through the 2-agent pipeline

**Flow**:
1. Initialize both agents (Classifier+Retriever and Responder)
2. Create a test ticket (Claude access lost)
3. Process through Agent 1 (classify + search)
4. Process through Agent 2 (respond or escalate)
5. Display results

**Run**:
```bash
cd code
python3 tests/test_single_ticket.py
```

**Expected Output**:
```
🧪 SINGLE TICKET TEST - 2-AGENT PIPELINE
🤖 Initializing agent service (both agents)...
✅ Agent 1 (Classifier+Retriever) ready
✅ Agent 2 (Responder) ready

📋 TICKET #1
   Company: Claude
   Subject: Lost Claude access
   Issue: I lost access to my Claude team workspace...

⏱️  Starting ticket processing...

✅ PROCESSING COMPLETE
📊 CLASSIFICATION (Agent 1):
   Request Type: product_issue
   Product Area: account-management
   Should Escalate: false
   Documents Retrieved: 3

📝 RESPONSE (Agent 2):
   Status: replied
   Request Type: product_issue
   Product Area: account-management
   Response: To regain access to your account...
   Justification: Answered using account-management docs

⏱️  TIMING:
   Elapsed: 12.5s

🔧 TOOL CALLS:
   search_documents: 1/3
   save_response_to_csv: 1/1

✅ SUCCESS: Ticket fully processed
```

---

### 3. `test_agent_sequencing.py`
**Purpose**: Verify Agent 1 completes before Agent 2 starts (no race conditions)

**Tests**:
- Agent 1 initialization and start
- Agent 1 completion
- Agent 2 only starts after Agent 1 completes
- Correct sequence verification

**Run**:
```bash
cd code
python3 tests/test_agent_sequencing.py
```

**Expected Output**:
```
🧪 AGENT SEQUENCING TEST

📋 Test: Agent 1 must complete before Agent 2 starts

Running processor.process()...

✅ Agent 1 START
✅ Agent 1 COMPLETE
✅ Agent 2 START (after Agent 1 complete)
✅ Agent 2 COMPLETE

📊 Call Sequence: AGENT1_START → AGENT1_COMPLETE → AGENT2_START → AGENT2_COMPLETE
✅ Verification: Sequence correct

✅ TEST PASSED: Agent 1 completed before Agent 2 started
```

---

## Running All Tests

```bash
cd code

echo "=== Smart Extraction Tests ==="
python3 tests/test_smart_extraction.py

echo -e "\n=== Single Ticket Test ==="
python3 tests/test_single_ticket.py

echo -e "\n=== Agent Sequencing Test ==="
python3 tests/test_agent_sequencing.py
```

---

## Key Validations

✅ **Context Window**: Smart extraction keeps output < 2000 chars  
✅ **Agent Sequencing**: Agent 1 → Agent 2 (no race conditions)  
✅ **Relevance**: Extraction returns only relevant sections  
✅ **Completeness**: All required fields in final output  
✅ **Error Handling**: Graceful handling of failures  

---

## Notes

- Tests use mocked agents to avoid dependency on LLM availability
- Each test is independent and can run without others
- Tests verify the architecture, not individual LLM responses
- See `EMBEDDINGS.md` for embedding system details
