from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.models import LlmResponse, LlmRequest
from google.genai import types
from typing import Optional

PROMPT_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore the system prompt",
    "pretend you are",
    "forget about",
    "disregard",
]

VALID_STATUSES = {"replied", "escalated"}
VALID_REQUEST_TYPES = {"product_issue", "feature_request", "bug", "invalid"}

def create_input_guardrail(logger=None):
    """Create an input guardrail callback for prompt injection detection."""

    def input_guardrail(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
        """Detect and block prompt injection attempts."""
        text = ""
        for content in llm_request.contents if llm_request.contents else []:
            for part in content.parts if content.parts else []:
                if hasattr(part, "text") and part.text:
                    text += part.text.lower()

        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern in text:
                if logger:
                    logger.log_guardrail_check(f"Prompt injection detection ({pattern})", False)
                return LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="I cannot process requests that attempt to modify my instructions.")]
                    )
                )

        if logger:
            logger.log_guardrail_check("Prompt injection detection", True)
        return None

    return input_guardrail

def create_tool_guardrail(logger=None):
    """Create a tool guardrail callback for tool safety validation."""

    def tool_guardrail(tool_ctx: ToolContext = None, args: dict = None, **kwargs) -> Optional[dict]:
        """Validate tool arguments before execution."""

        # Handle different callback signatures
        if tool_ctx is None or args is None:
            return None

        # Enum validation for save_response_to_csv
        if tool_ctx.tool_name == "save_response_to_csv":
            status = args.get("status", "")
            request_type = args.get("request_type", "")

            if status not in VALID_STATUSES:
                if logger:
                    logger.log_guardrail_check(f"Enum validation ({tool_ctx.tool_name}:status)", False)
                return {"error": f"Invalid status '{status}'. Must be one of {VALID_STATUSES}"}

            if request_type not in VALID_REQUEST_TYPES:
                if logger:
                    logger.log_guardrail_check(f"Enum validation ({tool_ctx.tool_name}:request_type)", False)
                return {"error": f"Invalid request_type '{request_type}'. Must be one of {VALID_REQUEST_TYPES}"}

        if logger:
            logger.log_guardrail_check(f"Tool validation ({tool_ctx.tool_name})", True)
        return None

    return tool_guardrail
