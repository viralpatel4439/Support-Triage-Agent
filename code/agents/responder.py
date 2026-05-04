"""Agent 2: Responder - generates responses or escalates, then saves to CSV."""

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

from tools.search_tools import save_response_to_csv
from observability import TicketLogger, create_input_guardrail, create_tool_guardrail

RESPONDER_PROMPT = """Read Agent 1's output (classification + documents).

EXTRACT from Agent 1's output:
1. company: Which company (Claude, HackerRank, Visa)
2. request_type: product_issue, feature_request, bug, or invalid
3. product_area: The category
4. should_escalate: true or false
5. escalation_reason: If escalation reason else ""
6. documents: The retrieved documents (if any)

THEN use the save_response_to_csv tool with:

- ticket_id: From the Ticket # in the input (ticket #1 = ticket_id=1)

- status:
  * "escalated" if should_escalate = true
  * "replied" if should_escalate = false

- product_area: The extracted product_area

- response:
  * If escalating:
    Write a clear, professional, and descriptive message explaining the issue and why it is being escalated. The message should feel like a human support reply.
    Example tone:
    "Thank you for reaching out. Based on your request, this appears to require further investigation by our specialized team. We are escalating your case to ensure it is handled appropriately."

  * If replying:
    Provide a helpful, well-explained response grounded in the documents. The response should:
    - Be descriptive and easy to understand
    - Directly address the user's issue
    - Include relevant details from the documents
    - Sound like a real support agent (not robotic or one-line)

- justification:
  * If escalating: use escalation_reason
  * If replying: mention which document(s) were used

- request_type: The extracted request_type

IMPORTANT:
- You MUST call the save_response_to_csv tool.
- Do NOT output any plain text.
- The response must be written in a descriptive, user-friendly manner.
"""

def create_responder_agent(logger: TicketLogger = None):
    """Create Agent 2: Responder."""
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
    tool_guardrail = create_tool_guardrail(logger)

    # Agent 2 has only save_response_to_csv tool
    tools = [save_response_to_csv]

    agent = Agent(
        model=model,
        name="responder",
        description="Generates responses or escalates tickets, then saves to CSV",
        instruction=RESPONDER_PROMPT,
        tools=tools,
        before_model_callback=input_guardrail,
        after_model_callback=logger.after_model_callback,
        before_tool_callback=tool_guardrail,
        after_tool_callback=logger.after_tool_callback,
    )

    return agent
