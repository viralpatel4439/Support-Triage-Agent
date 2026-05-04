"""Agent 1: Classifier + Retriever - analyzes tickets and searches for relevant documents."""

import json
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

from tools.search_tools import search_documents
from observability import TicketLogger, create_input_guardrail

CLASSIFIER_RETRIEVER_PROMPT = """Analyze the incoming support ticket and return structured JSON.

You are a triage agent for:
- HackerRank (coding platform, interviews, assessments)
- Claude (AI product usage, API, access)
- Visa (financial services, cards, transactions)

-----------------------------------
Step 1: Classify
-----------------------------------
Extract:
- company: (HackerRank | Claude | Visa)
- request_type: (product_issue | feature_request | bug | invalid)
- product_area: short category (e.g., authentication, payments, API, interview, billing)

-----------------------------------
Step 2: Escalation Decision
-----------------------------------

Set should_escalate = true if ANY of the following:

A. Critical / Risk Issues:
- fraud or suspicious transaction (Visa)
- lost/stolen card (Visa)
- security breach / data leak
- account locked / access completely blocked
- platform outage
- legal / compliance concern

B. User-Specific Action Required:
- account access issues (login failure, lost access)
- refund or payment disputes
- billing issues or unexpected charges
- interview disputes / result-related complaints (HackerRank)
- API key / account-specific issues (Claude)
- anything requiring internal system lookup or manual intervention

→ For these:
  - should_escalate = true
  - escalation_reason = clear and specific
  - retrieved_documents = null

-----------------------------------
Step 3: Document-Based Resolution
-----------------------------------

If NOT escalated above:

- Search knowledge base documents

A. If relevant documents found:
  → should_escalate = false
  → escalation_reason = null
  → return retrieved_documents

B. If NO relevant documents found:
  → should_escalate = true
  → escalation_reason = "No relevant documentation found for this query"
  → retrieved_documents = null

-----------------------------------
Step 4: Output Format (STRICT JSON ONLY)
-----------------------------------

{
  "company": "HackerRank | Claude | Visa",
  "request_type": "product_issue | feature_request | bug | invalid",
  "product_area": "string",
  "should_escalate": true or false,
  "escalation_reason": "string or null",
  "retrieved_documents": [
    {
      "title": "string",
      "content": "string",
      "relevance_score": float
    }
  ] or null
}
"""

def create_classifier_retriever_agent(logger: TicketLogger = None):
    """Create Agent 1: Classifier + Retriever."""
    import os

    if logger is None:
        logger = TicketLogger()

    # Get LLM config
    llm_base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    llm_model = os.getenv("LLM_MODEL", "llama3.2")
    llm_api_key = os.getenv("LLM_API_KEY", "")

    # Model - auto-detect ollama format if using localhost
    model_name = llm_model
    if "localhost:11434" in llm_base_url and "/" not in llm_model:
        model_name = f"ollama_chat/{llm_model}"

    kwargs = {"model": model_name, "api_base": llm_base_url}
    if llm_api_key:
        kwargs["api_key"] = llm_api_key

    model = LiteLlm(**kwargs)

    # Create guardrails
    input_guardrail = create_input_guardrail(logger)

    # Agent 1 has only search_documents tool
    tools = [search_documents]

    agent = Agent(
        model=model,
        name="classifier_retriever",
        description="Analyzes support tickets and retrieves relevant documentation",
        instruction=CLASSIFIER_RETRIEVER_PROMPT,
        tools=tools,
        before_model_callback=input_guardrail,
        after_model_callback=logger.after_model_callback,
        before_tool_callback=None,  # No tool validation needed
        after_tool_callback=logger.after_tool_callback,
    )

    return agent
