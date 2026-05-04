"""Ticket: Self-contained object for processing a single support ticket.

Each ticket manages its own:
- State (company, issue, subject, response, etc.)
- Tool call limits and tracking (independent per ticket)
- Agent invocation and orchestration
- Response saving
"""

import time
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

MAX_TOOL_CALLS_SEARCH = 3
MAX_TOOL_CALLS_SAVE = 1


@dataclass
class Ticket:
    """Self-contained ticket object that handles all processing state and logic."""

    ticket_id: int
    company: str
    issue: str
    subject: str

    # Internal state - managed by this ticket object only
    _tool_call_counts: Dict[str, int] = field(default_factory=lambda: {
        "search_documents": 0,
        "save_response_to_csv": 0,
    })

    _start_time: Optional[float] = field(default=None)
    _end_time: Optional[float] = field(default=None)
    _status: str = field(default="pending")  # pending, processing, completed, error
    _error: Optional[str] = field(default=None)

    # Classification output (from Agent 1)
    _request_type: Optional[str] = field(default=None)
    _product_area: Optional[str] = field(default=None)
    _should_escalate: bool = field(default=False)
    _escalation_reason: Optional[str] = field(default=None)

    # Agent 1 output (raw text)
    _agent1_output: Optional[str] = field(default=None)

    # Response output (from Agent 2)
    _response_text: Optional[str] = field(default=None)
    _justification: Optional[str] = field(default=None)
    _final_status: str = field(default="pending")  # replied or escalated

    # Agents (set by factory)
    _classifier_retriever: Optional[Any] = field(default=None)
    _responder: Optional[Any] = field(default=None)

    def set_agents(self, classifier_retriever, responder):
        """Set the agents for this ticket."""
        self._classifier_retriever = classifier_retriever
        self._responder = responder

    def can_call_tool(self, tool_name: str) -> tuple[bool, int]:
        """Check if this ticket can call a tool, and return call count.

        Each ticket has independent limits:
        - search_documents: max 3 calls
        - save_response_to_csv: max 1 call
        """
        if tool_name not in self._tool_call_counts:
            return False, 0

        current = self._tool_call_counts[tool_name]
        new_count = current + 1

        # Determine max for this tool
        max_calls = MAX_TOOL_CALLS_SEARCH if tool_name == "search_documents" else MAX_TOOL_CALLS_SAVE

        if new_count > max_calls:
            return False, new_count

        # Increment and return
        self._tool_call_counts[tool_name] = new_count
        return True, new_count

    def get_tool_call_count(self, tool_name: str) -> int:
        """Get current tool call count for this ticket."""
        return self._tool_call_counts.get(tool_name, 0)

    def set_classification(self, request_type: str, product_area: str, should_escalate: bool = False, reason: str = ""):
        """Set classification results from Agent 1."""
        self._request_type = request_type
        self._product_area = product_area
        self._should_escalate = should_escalate
        self._escalation_reason = reason

    def set_agent1_output(self, output: str):
        """Store raw output from Agent 1 to pass to Agent 2."""
        self._agent1_output = output

    def set_response(self, response: str, justification: str, status: str):
        """Set final response from Agent 2."""
        self._response_text = response
        self._justification = justification
        self._final_status = status

    def mark_started(self):
        """Mark ticket as started processing."""
        self._start_time = time.time()
        self._status = "processing"

    def mark_completed(self):
        """Mark ticket as completed."""
        self._end_time = time.time()
        self._status = "completed"

    def mark_error(self, error: str):
        """Mark ticket as errored."""
        self._end_time = time.time()
        self._status = "error"
        self._error = error

    def get_elapsed_seconds(self) -> float:
        """Get elapsed time for processing."""
        if self._start_time and self._end_time:
            return round(self._end_time - self._start_time, 2)
        return 0.0

    def to_csv_row(self) -> Dict[str, str]:
        """Convert ticket to CSV row dict for output.csv."""
        return {
            "issue": self.issue,
            "subject": self.subject,
            "company": self.company,
            "response": self._response_text or "",
            "product_area": self._product_area or "unknown",
            "status": self._final_status or "pending",
            "request_type": self._request_type or "invalid",
            "justification": self._justification or "",
        }

    def get_result(self) -> Dict[str, Any]:
        """Get complete result dict for logging/reporting."""
        return {
            "ticket_id": self.ticket_id,
            "company": self.company,
            "status": self._status,
            "final_status": self._final_status,
            "request_type": self._request_type,
            "product_area": self._product_area,
            "response": self._response_text,
            "justification": self._justification,
            "tool_calls": self._tool_call_counts.copy(),
            "elapsed_seconds": self.get_elapsed_seconds(),
            "error": self._error,
        }

    def __repr__(self) -> str:
        return f"Ticket(#{self.ticket_id}, {self.company}, status={self._status})"

    def summary(self) -> str:
        """Get a summary of ticket state."""
        return f"""
Ticket #{self.ticket_id}:
  Company: {self.company}
  Status: {self._status}
  Final Status: {self._final_status}
  Request Type: {self._request_type}
  Product Area: {self._product_area}
  Tool Calls: {self._tool_call_counts}
  Elapsed: {self.get_elapsed_seconds()}s
  Error: {self._error}
"""
