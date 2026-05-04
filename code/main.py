#!/usr/bin/env python3

import asyncio
import os
import sys
import csv
import argparse
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Tuple

# Patch logging module for litellm compatibility (Python 3.14 fix)
# litellm tries to use logging.OFF which doesn't exist
if not hasattr(logging, 'OFF'):
    logging.OFF = 100  # Custom level higher than CRITICAL

# Suppress litellm async logging issues BEFORE any imports
os.environ["LITELLM_DISABLE_LOGGING"] = "True"
os.environ["LITELLM_LOG"] = "off"

# Suppress asyncio task exceptions from litellm logging worker
def _suppress_litellm_task_error(loop, context):
    """Suppress 'task_done() called too many times' from litellm logging worker."""
    if "task_done() called too many times" in str(context.get("exception", "")):
        return  # Ignore this specific litellm logging error
    # Let other exceptions through
    loop.default_exception_handler(context)

from observability import TicketLogger
from ticket import TicketProcessor
from services import AgentService

# Load .env from code directory
code_dir = Path(__file__).parent
project_root = code_dir.parent
env_file = code_dir / ".env"
load_dotenv(env_file)

# Validation constants
VALID_COMPANIES = {"HackerRank", "Claude", "Visa", "None"}
DANGEROUS_PATTERNS = [
    "ignore previous instructions",
    "ignore the system prompt",
    "forget about",
    "pretend you are",
    "disregard",
]
MIN_ISSUE_LENGTH = 3
MAX_ISSUE_LENGTH = 50000

class TicketValidator:
    """Validates input tickets for completeness and safety."""

    def __init__(self, logger: TicketLogger):
        self.logger = logger

    def validate_ticket(self, ticket: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a single ticket.
        Returns: (is_valid, error_message_or_none)
        """
        errors = []

        # Check required fields exist
        if "issue" not in ticket or not isinstance(ticket["issue"], str):
            errors.append("Missing or invalid 'issue' field")

        if "company" not in ticket or not isinstance(ticket["company"], str):
            errors.append("Missing or invalid 'company' field")

        issue = ticket.get("issue", "").strip()
        company = ticket.get("company", "").strip()
        subject = ticket.get("subject", "").strip()

        # Check issue is not empty
        if not issue:
            errors.append("Issue field is empty")
        elif len(issue) < MIN_ISSUE_LENGTH:
            errors.append(f"Issue too short (< {MIN_ISSUE_LENGTH} chars)")
        elif len(issue) > MAX_ISSUE_LENGTH:
            errors.append(f"Issue too long (> {MAX_ISSUE_LENGTH} chars)")

        # Check company is valid
        if company not in VALID_COMPANIES:
            errors.append(f"Invalid company '{company}'. Must be one of: {VALID_COMPANIES}")

        # Check for dangerous patterns (basic prompt injection detection)
        issue_lower = issue.lower()
        subject_lower = subject.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern in issue_lower or pattern in subject_lower:
                errors.append(f"Suspicious pattern detected: '{pattern}'")

        # Check for extremely short valid-looking issue (might be test/garbage)
        if len(issue) < 10 and len(issue) >= MIN_ISSUE_LENGTH:
            # This is a warning, not an error - short issues can be valid
            self.logger.log(f"[VALIDATION] Ticket #{ticket.get('index')} has very short issue ({len(issue)} chars)")

        if errors:
            error_msg = "; ".join(errors)
            return False, error_msg

        return True, None

def read_input_csv(file_path: str) -> list[dict]:
    """Read support tickets CSV."""
    tickets = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                print("❌ CSV file is empty or has no headers")
                sys.exit(1)

            for i, row in enumerate(reader, start=1):
                tickets.append({
                    "index": i,
                    "issue": row.get("Issue", "").strip(),
                    "subject": row.get("Subject", "").strip(),
                    "company": row.get("Company", "None").strip(),
                })
    except FileNotFoundError:
        print(f"❌ Input file not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        sys.exit(1)

    return tickets

async def process_ticket_with_agent(
    ticket: dict,
    logger: TicketLogger,
    semaphore: asyncio.Semaphore
) -> bool:
    """Process a single ticket using TicketProcessor (complete lifecycle management)."""
    async with semaphore:  # Limit concurrent executions
        try:
            from models.ticket import Ticket

            # Create Ticket object (self-contained state + tool limits)
            ticket_obj = Ticket(
                ticket_id=ticket['index'],
                company=ticket['company'],
                issue=ticket['issue'],
                subject=ticket['subject'],
            )

            # Create processor to orchestrate agents
            processor = TicketProcessor(ticket_obj, logger=logger)

            # Process ticket (complete lifecycle)
            result = await processor.process()

            # Log result
            if result['error']:
                logger.log(f"❌ Ticket {ticket['index']} failed: {result['error']}")
                return False
            else:
                logger.log(f"✅ Ticket {ticket['index']} processed: status={result['status']}")
                return True

        except Exception as e:
            logger.log(f"❌ Critical error processing ticket {ticket['index']}: {str(e)}")
            return False

async def process_all_tickets(
    tickets: list[dict],
    logger: TicketLogger,
    max_concurrent: int = 3
) -> Tuple[int, int, int]:
    """Process all tickets with concurrency control via semaphore."""
    semaphore = asyncio.Semaphore(max_concurrent)

    print(f"⚙️  Processing {len(tickets)} tickets (max {max_concurrent} in parallel)...")

    # Create tasks for all tickets - semaphore will control concurrency
    tasks = [
        process_ticket_with_agent(ticket, logger, semaphore)
        for ticket in tickets
    ]

    # Run all tasks - semaphore limits concurrent execution
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Count results
    success_count = sum(1 for r in results if r is True)
    error_count = sum(1 for r in results if isinstance(r, Exception) or r is False)
    total_processed = len(tickets)

    return total_processed, success_count, error_count

def main():
    # Get concurrency setting from environment variable
    env_batch_concurrency = os.getenv("BATCH_CONCURRENCY", None)
    default_concurrency = int(env_batch_concurrency) if env_batch_concurrency else 2

    parser = argparse.ArgumentParser(
        description="HackerRank Orchestrate Support Triage Agent"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run on sample_support_tickets.csv (for testing)"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="./support_tickets/support_tickets.csv",
        help="Path to input CSV file"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=default_concurrency,
        help=f"Number of tickets to process in parallel (default: {default_concurrency}, from BATCH_CONCURRENCY env)"
    )

    args = parser.parse_args()

    # Set max_concurrent from concurrency argument
    max_concurrent = args.concurrency

    # Log the effective settings
    print(f"⚙️  Concurrency Settings:")
    if env_batch_concurrency:
        print(f"   BATCH_CONCURRENCY={env_batch_concurrency} (from environment)")
    else:
        print(f"   BATCH_CONCURRENCY=not set (using default: 2)")
    print(f"   Max Parallel Tickets: {max_concurrent}")
    print()

    # Determine input file
    if args.test:
        input_file = project_root / "support_tickets" / "sample_support_tickets.csv"
        print("🧪 Running on SAMPLE tickets (for testing)...")
    else:
        input_file = Path(args.input) if not Path(args.input).is_absolute() else Path(args.input)
        if not input_file.is_absolute():
            input_file = project_root / input_file
        print("🚀 Running on REAL support tickets...")

    # Verify input file exists
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        sys.exit(1)

    # Initialize logger
    logger = TicketLogger()
    print("📝 Logging initialized")

    # Read tickets
    print(f"📖 Reading tickets from {input_file}...")
    tickets = read_input_csv(str(input_file))
    print(f"✅ Loaded {len(tickets)} tickets")

    # Validate tickets
    print("\n🔍 Validating tickets...")
    validator = TicketValidator(logger)
    valid_tickets = []
    invalid_count = 0

    for ticket in tickets:
        is_valid, error_msg = validator.validate_ticket(ticket)
        if is_valid:
            valid_tickets.append(ticket)
        else:
            invalid_count += 1
            logger.log(f"[VALIDATION FAILED] Ticket #{ticket['index']}: {error_msg}")

    print(f"✅ Validation complete: {len(valid_tickets)} valid, {invalid_count} invalid")

    if len(valid_tickets) == 0:
        print("❌ No valid tickets to process. Exiting.")
        sys.exit(1)

    # Initialize agent service (creates orchestrator once)
    print("\n🤖 Initializing triage agent...")
    AgentService.initialize(logger)
    print("✅ Agent initialized")

    # Process tickets with batching and concurrency control
    print()
    start_time = time.time()

    # Set up asyncio to suppress litellm logging worker errors
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(_suppress_litellm_task_error)

    try:
        processed, success, errors = loop.run_until_complete(
            process_all_tickets(
                valid_tickets,
                logger,
                max_concurrent=max_concurrent
            )
        )
    finally:
        loop.close()

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "="*60)
    print("✅ PROCESSING COMPLETE")
    print("="*60)
    print(f"📊 Results:")
    print(f"   Total tickets processed: {processed}")
    print(f"   Successful: {success}")
    print(f"   Errors: {errors}")
    print(f"   Invalid (skipped): {invalid_count}")
    print(f"   Total input: {len(tickets)}")
    print(f"   Time elapsed: {elapsed:.2f}s")
    if processed > 0:
        print(f"   Avg time per ticket: {elapsed/processed:.2f}s")
    print()
    print(f"📊 Check output.csv for results")
    print(f"📝 Ticket traces: {Path.home() / 'hackerrank_orchestrate' / 'ticket_traces.log'}")
    print("="*60)

if __name__ == "__main__":
    main()
