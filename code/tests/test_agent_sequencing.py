#!/usr/bin/env python3
"""Test to verify Agent 1 (Classifier) completes before Agent 2 (Responder) is called."""

import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock
from dotenv import load_dotenv

# Load .env from code directory (same fix as main.py)
code_dir = Path(__file__).parent.parent
env_file = code_dir / ".env"
load_dotenv(env_file)

# Add code to path
sys.path.insert(0, str(code_dir))

from models.ticket import Ticket
from observability import TicketLogger
from ticket import TicketProcessor
from services import AgentService


class SequencingTracker:
    """Tracks the order of agent invocations."""

    def __init__(self):
        self.call_log = []
        self.agent1_complete = False
        self.agent2_started = False

    def log_agent1_start(self):
        self.call_log.append("AGENT1_START")
        print("✅ Agent 1 (_invoke_classifier_retriever) START")

    def log_agent1_complete(self):
        self.call_log.append("AGENT1_COMPLETE")
        self.agent1_complete = True
        print("✅ Agent 1 (_invoke_classifier_retriever) COMPLETE")

    def log_agent2_start(self):
        if not self.agent1_complete:
            raise AssertionError("❌ Agent 2 started before Agent 1 completed!")
        self.call_log.append("AGENT2_START")
        self.agent2_started = True
        print("✅ Agent 2 (_invoke_responder) START (after Agent 1 complete)")

    def log_agent2_complete(self):
        self.call_log.append("AGENT2_COMPLETE")
        print("✅ Agent 2 (_invoke_responder) COMPLETE")

    def verify_sequence(self):
        """Verify the correct sequence."""
        expected = ["AGENT1_START", "AGENT1_COMPLETE", "AGENT2_START", "AGENT2_COMPLETE"]
        if self.call_log == expected:
            return True, "Sequence correct: Agent 1 → Agent 2"
        else:
            return False, f"Expected {expected}, got {self.call_log}"


async def test_agent_sequencing():
    """Test that Agent 1 completes before Agent 2 starts."""

    print("\n" + "="*70)
    print("🧪 AGENT SEQUENCING TEST")
    print("="*70 + "\n")

    tracker = SequencingTracker()
    logger = TicketLogger()

    print("📋 Test: Agent 1 (Classifier+Retriever) must complete before Agent 2 (Responder) starts\n")

    # Create tracked versions of the agent invocation methods
    async def tracked_invoke_classifier_retriever(self):
        tracker.log_agent1_start()
        try:
            # Return mock response
            return "Mock Agent 1 output: classification and search results"
        finally:
            tracker.log_agent1_complete()

    async def tracked_invoke_responder(self, responder_input):
        tracker.log_agent2_start()
        try:
            # Simulate responder processing (would normally call save_response_to_csv)
            pass
        finally:
            tracker.log_agent2_complete()

    try:
        # Initialize agent service
        AgentService.initialize(logger)

        # Create Ticket object
        ticket = Ticket(
            ticket_id=1,
            company="Claude",
            issue="I lost access to my account",
            subject="Lost access",
        )

        # Create processor with Ticket
        processor = TicketProcessor(ticket, logger=logger)

        # Patch the agent invocation methods to track sequencing
        with patch.object(processor, '_invoke_classifier_retriever', tracked_invoke_classifier_retriever):
            with patch.object(processor, '_invoke_responder', tracked_invoke_responder):

                print("Running processor.process()...\n")
                result = await processor.process()

                print("\n" + "="*70)
                print("RESULTS")
                print("="*70)

                # Verify sequencing
                success, msg = tracker.verify_sequence()

                print(f"\n📊 Call Sequence: {' → '.join(tracker.call_log)}")
                print(f"✅ Verification: {msg}")

                if success:
                    print("\n✅ TEST PASSED: Agent 1 completed before Agent 2 started")
                    return True
                else:
                    print(f"\n❌ TEST FAILED: {msg}")
                    return False

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_agent_sequencing())
    sys.exit(0 if success else 1)
