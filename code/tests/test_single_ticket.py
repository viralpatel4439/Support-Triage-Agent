#!/usr/bin/env python3
"""Test script: single ticket through 2-agent pipeline."""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from code directory (same fix as main.py)
code_dir = Path(__file__).parent.parent
env_file = code_dir / ".env"
load_dotenv(env_file)

# Add code dir to path
sys.path.insert(0, str(code_dir))

from models.ticket import Ticket
from observability import TicketLogger
from ticket import TicketProcessor
from services import AgentService


async def test_single_ticket():
    """Test one ticket through Agent 1 → Agent 2 pipeline."""

    print("\n" + "="*70)
    print("🧪 SINGLE TICKET TEST - 2-AGENT PIPELINE")
    print("="*70 + "\n")

    # Initialize agent service
    logger = TicketLogger()
    print("🤖 Initializing agent service...")
    AgentService.initialize(logger)
    print("✅ Agent service ready\n")

    # Create test ticket
    test_ticket_dict = {
        "index": 1,
        "company": "Claude",
        "issue": "I lost access to my Claude team workspace after our IT admin removed my seat. Can you help?",
        "subject": "Lost Claude access"
    }

    print(f"📋 TICKET #{test_ticket_dict['index']}")
    print(f"   Company: {test_ticket_dict['company']}")
    print(f"   Subject: {test_ticket_dict['subject']}")
    print(f"   Issue: {test_ticket_dict['issue'][:70]}...\n")

    try:
        # Create Ticket object (contains all state management)
        ticket = Ticket(
            ticket_id=test_ticket_dict['index'],
            company=test_ticket_dict['company'],
            issue=test_ticket_dict['issue'],
            subject=test_ticket_dict['subject'],
        )

        # Create processor with Ticket object
        processor = TicketProcessor(ticket, logger=logger)

        print("⏱️  Starting ticket processing...\n")
        result = await processor.process()

        # Display results
        print("\n" + "="*70)
        print("✅ PROCESSING COMPLETE")
        print("="*70)

        print(f"\n📊 CLASSIFICATION (Agent 1):")
        print(f"   Request Type: {ticket._request_type}")
        print(f"   Product Area: {ticket._product_area}")
        print(f"   Should Escalate: {ticket._should_escalate}")

        print(f"\n📝 RESPONSE (Agent 2):")
        print(f"   Status: {ticket._final_status}")
        print(f"   Response Type: {ticket._request_type}")

        if ticket._response_text:
            preview = ticket._response_text[:150] + "..." if len(ticket._response_text) > 150 else ticket._response_text
            print(f"   Response: {preview}")

        if ticket._justification:
            preview = ticket._justification[:100] + "..." if len(ticket._justification) > 100 else ticket._justification
            print(f"   Justification: {preview}")

        print(f"\n⏱️  TIMING:")
        elapsed = (ticket._end_time - ticket._start_time) if (ticket._end_time and ticket._start_time) else 0
        print(f"   Elapsed: {elapsed:.2f}s")

        print(f"\n🔧 TOOL CALLS:")
        print(f"   search_documents: {ticket._tool_call_counts.get('search_documents', 0)}/3")
        print(f"   save_response_to_csv: {ticket._tool_call_counts.get('save_response_to_csv', 0)}/1")

        if result.get('error'):
            print(f"\n❌ ERROR: {result.get('error')}")
        else:
            print(f"\n✅ SUCCESS: Ticket fully processed")

        print("\n" + "="*70)

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_single_ticket())
    sys.exit(0 if success else 1)
