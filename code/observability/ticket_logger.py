import time
from pathlib import Path
from datetime import datetime
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.models import LlmResponse, LlmRequest
from typing import Optional

TICKET_TRACES_LOG = Path.home() / "hackerrank_orchestrate" / "ticket_traces.log"

def init_ticket_log():
    """Initialize the ticket traces log file."""
    TICKET_TRACES_LOG.parent.mkdir(parents=True, exist_ok=True)

class TicketLogger:
    """Logs all agent events per ticket via ADK callbacks."""

    def __init__(self):
        self.ticket_id = None
        self.start_time = None
        self.ticket_start_time = None
        init_ticket_log()

    def set_ticket_context(self, ticket_id: int):
        """Set the current ticket being processed."""
        self.ticket_id = ticket_id
        self.ticket_start_time = time.time()

    def log(self, message: str):
        """Log a message to both file and stdout."""
        timestamp = datetime.now().isoformat()
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        with open(TICKET_TRACES_LOG, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")

    def before_model_callback(self, callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
        """Hook: before LLM call."""
        msg_count = len(llm_request.contents) if llm_request.contents else 0
        self.log(f"[{callback_context.agent_name}] LLM REASONING | messages={msg_count}")
        return None

    def after_model_callback(self, callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
        """Hook: after LLM response."""
        text = ""
        if llm_response.content and llm_response.content.parts:
            for part in llm_response.content.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
        preview = text[:100].replace("\n", " ")
        self.log(f"[{callback_context.agent_name}] LLM OUTPUT | preview={preview}")
        return None

    def before_tool_callback(self, tool_ctx: ToolContext = None, args = None, **kwargs) -> Optional[dict]:
        """Hook: before tool execution."""
        if tool_ctx is None:
            return None
        if args:
            args_str = str(args)[:120].replace("\n", " ")
            self.log(f"[{tool_ctx.agent_name}] TOOL CALL → {tool_ctx.tool_name}({args_str})")
        else:
            self.log(f"[{tool_ctx.agent_name}] TOOL CALL → {tool_ctx.tool_name}()")
        return None

    def after_tool_callback(self, tool_ctx: ToolContext = None, result = None, **kwargs) -> Optional[dict]:
        """Hook: after tool execution."""
        if tool_ctx is None:
            return None
        if result:
            result_str = str(result)[:200].replace("\n", " ")
            self.log(f"[{tool_ctx.agent_name}] TOOL RESULT ← {tool_ctx.tool_name}: {result_str}")
        else:
            self.log(f"[{tool_ctx.agent_name}] TOOL RESULT ← {tool_ctx.tool_name}")
        return None

    def log_ticket_start(self, company: str, issue: str, subject: str):
        """Log ticket start."""
        self.log("=" * 60)
        self.log(f"TICKET #{self.ticket_id} START | Company={company}")
        self.log(f"Subject: {subject[:80]}")
        self.log(f"Issue: {issue[:100]}")
        self.log("=" * 60)

    def log_ticket_end(self, status: str, request_type: str):
        """Log ticket end with summary."""
        elapsed = time.time() - self.ticket_start_time if self.ticket_start_time else 0
        self.log("=" * 60)
        self.log(f"TICKET #{self.ticket_id} END | status={status} | request_type={request_type} | time={elapsed:.1f}s")
        self.log("=" * 60)
        self.log("")

    def log_guardrail_check(self, check_name: str, passed: bool):
        """Log guardrail check result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.log(f"[GUARDRAIL] {check_name}: {status}")
