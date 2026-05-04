#!/usr/bin/env python3
"""Test sequential processing with max_concurrent=1."""

import asyncio
import time
from datetime import datetime

async def process_ticket(ticket_id: int, semaphore: asyncio.Semaphore):
    """Simulate processing a ticket with the semaphore."""
    async with semaphore:
        start_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{start_time}] START   Ticket #{ticket_id}")
        await asyncio.sleep(0.5)  # Simulate work
        end_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{end_time}] FINISH  Ticket #{ticket_id}")
        return True

async def main():
    max_concurrent = 1  # Sequential processing
    num_tickets = 4

    print(f"Testing {num_tickets} tickets with max_concurrent={max_concurrent}")
    print("Expected: 1 running at a time, sequential")
    print()

    semaphore = asyncio.Semaphore(max_concurrent)

    # Create all tasks
    tasks = [
        process_ticket(i+1, semaphore)
        for i in range(num_tickets)
    ]

    # Run all tasks - semaphore limits concurrency
    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    print()
    print(f"Completed {len(results)} tickets in {elapsed:.1f}s")
    print(f"Expected ~{(num_tickets * 0.5)}s (= {num_tickets} tickets * 0.5s each)")

if __name__ == "__main__":
    asyncio.run(main())
