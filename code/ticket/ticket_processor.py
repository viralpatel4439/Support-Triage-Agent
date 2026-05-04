"""TicketProcessor: Orchestrates 2-agent pipeline for a single Ticket object."""

import asyncio
from typing import Dict, Any
from models.ticket import Ticket
from tools import set_current_ticket, clear_current_ticket
from observability import TicketLogger
from services import get_agent_service


class TicketProcessor:
    """Processes a Ticket through both agents sequentially.

    The Ticket object manages all state and tool call limits.
    TicketProcessor just orchestrates the agent invocations.
    """

    def __init__(self, ticket: Ticket, logger: TicketLogger = None):
        """Initialize processor for a Ticket object.

        Args:
            ticket: Ticket object with all data and state management
            logger: TicketLogger for observability
        """
        self.ticket = ticket
        self.logger = logger or TicketLogger()

        # Get both agents from singleton service
        service = get_agent_service()
        ticket.set_agents(
            classifier_retriever=service.get_classifier_retriever(),
            responder=service.get_responder(),
        )

    async def process(self) -> Dict[str, Any]:
        """Execute complete ticket processing lifecycle (Agent 1 → Agent 2).

        Returns:
            Dictionary with ticket processing result
        """
        try:
            # Set ticket in context for tools to access
            set_current_ticket(self.ticket)
            self.ticket.mark_started()

            # Log start
            self.logger.set_ticket_context(self.ticket.ticket_id)
            self.logger.log_ticket_start(self.ticket.company, self.ticket.issue, self.ticket.subject)

            # STEP 1: Call Agent 1 (Classifier + Retriever)
            self.logger.log(f"[TICKET #{self.ticket.ticket_id}] Step 1/2: Invoking classifier_retriever agent...")
            agent1_output = await self._invoke_classifier_retriever()

            if not agent1_output:
                raise Exception("Classifier+Retriever failed to return output")

            self.logger.log(f"[TICKET #{self.ticket.ticket_id}] Agent 1 output received ({len(agent1_output)} chars)")
            self.ticket.set_agent1_output(agent1_output)

            # STEP 2: Call Agent 2 (Responder)
            self.logger.log(f"[TICKET #{self.ticket.ticket_id}] Step 2/2: Invoking responder agent...")
            responder_input = self._format_responder_input(agent1_output)
            await self._invoke_responder(responder_input)

            # Log completion
            self.ticket.mark_completed()
            self.logger.log_ticket_end(self.ticket._final_status or "completed", self.ticket._request_type or "unknown")

            return self.ticket.get_result()

        except Exception as e:
            self.ticket.mark_error(str(e))
            self.logger.log(f"❌ Error processing ticket {self.ticket.ticket_id}: {str(e)}")
            self.logger.log_ticket_end("error", "error")
            return self.ticket.get_result()

        finally:
            # Clean up context
            clear_current_ticket()

    def _format_ticket_input(self) -> str:
        """Format ticket data for Agent 1 input."""
        return f"""
Ticket #{self.ticket.ticket_id}

Company: {self.ticket.company}
Subject: {self.ticket.subject}
Issue: {self.ticket.issue}
"""

    async def _invoke_classifier_retriever(self) -> str:
        """Invoke Agent 1 (Classifier + Retriever) to analyze ticket and search docs.

        Returns:
            Raw response text (Agent 2 will read and understand it)
        """
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.genai import types
            import uuid

            # Format ticket for Agent 1
            ticket_text = self._format_ticket_input()

            # Set up agent session
            USER_ID = str(self.ticket.ticket_id)
            SESSION_ID = str(uuid.uuid4())
            APP_NAME = "Classifier-Retriever"

            session_service = InMemorySessionService()
            await session_service.create_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
            )

            runner = Runner(
                agent=self.ticket._classifier_retriever,
                app_name=APP_NAME,
                session_service=session_service,
            )

            content = types.Content(
                role="user",
                parts=[types.Part(text=ticket_text)],
            )

            # Run agent in thread pool (runner.run is synchronous)
            # Context is already set in process() at the start and persists throughout
            def run_agent():
                return list(runner.run(
                    user_id=USER_ID,
                    session_id=SESSION_ID,
                    new_message=content,
                ))

            events = await asyncio.to_thread(run_agent)

            # Extract final response (raw text - Agent 2 will understand it)
            for event in events:
                if event.is_final_response():
                    response_text = event.content.parts[0].text
                    self.logger.log(f"[TICKET #{self.ticket.ticket_id}] Agent 1 completed")
                    return response_text

            raise Exception("Agent 1 did not return a final response")

        except Exception as e:
            self.logger.log(f"❌ Classifier+Retriever invocation failed: {str(e)}")
            raise

    async def _invoke_responder(self, responder_input: str) -> None:
        """Invoke Agent 2 (Responder) to generate response or escalate and save to CSV.

        Args:
            responder_input: Formatted input for responder agent
        """
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.genai import types
            import uuid

            # Set up agent session
            USER_ID = str(self.ticket.ticket_id)
            SESSION_ID = str(uuid.uuid4())
            APP_NAME = "Responder"

            session_service = InMemorySessionService()
            await session_service.create_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
            )

            runner = Runner(
                agent=self.ticket._responder,
                app_name=APP_NAME,
                session_service=session_service,
            )

            content = types.Content(
                role="user",
                parts=[types.Part(text=responder_input)],
            )

            # Run agent in thread pool
            # Context is already set in process() at the start and persists throughout
            def run_agent():
                return list(runner.run(
                    user_id=USER_ID,
                    session_id=SESSION_ID,
                    new_message=content,
                ))

            events = await asyncio.to_thread(run_agent)

            # Extract final response
            for event in events:
                if event.is_final_response():
                    response_text = event.content.parts[0].text
                    self.logger.log(f"[TICKET #{self.ticket.ticket_id}] Agent 2 completed")

                    # Agent 2 should have called save_response_to_csv, which updates ticket
                    # No need to update anything here - ticket state is already updated

                    return

            raise Exception("Agent 2 did not return a final response")

        except Exception as e:
            self.logger.log(f"❌ Responder invocation failed: {str(e)}")
            raise

    def _format_responder_input(self, agent1_output: str) -> str:
        """Format input for Agent 2 with Agent 1's output.

        Args:
            agent1_output: Raw text output from Agent 1

        Returns:
            Formatted text for Responder agent
        """
        return f"""
TICKET #{self.ticket.ticket_id}
Company: {self.ticket.company}
Issue: {self.ticket.issue}

AGENT 1 OUTPUT (Classification + Retrieved Documents):
{agent1_output}

INSTRUCTIONS:
Based on Agent 1's output above, you MUST call save_response_to_csv with:

1. ticket_id: {self.ticket.ticket_id}

2. status:
   - "escalated" if Agent 1 says should_escalate is true
   - "replied" if Agent 1 says should_escalate is false

3. product_area: (extract from Agent 1 output)

4. response:
   - If escalating: brief explanation why
   - If replying: grounded answer using documents from Agent 1

5. justification:
   - If escalating: why human review is needed
   - If replying: which document(s) you used

6. request_type: (extract from Agent 1 output - product_issue, feature_request, bug, or invalid)

DO NOT generate text. DO NOT explain.
CALL save_response_to_csv with all 6 parameters NOW.
"""

    def __repr__(self) -> str:
        return f"TicketProcessor({self.ticket})"
