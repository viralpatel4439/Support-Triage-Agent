"""Simple, production-grade ticket context management.

When a ticket starts processing, we create a context for it and maintain it
throughout the entire execution lifecycle. This context is directly accessible
to all tools that need it.
"""

import threading
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.ticket import Ticket

# Module-level ticket context (simple, direct, reliable)
_current_ticket: Optional['Ticket'] = None
_context_lock = threading.Lock()


def set_current_ticket(ticket: 'Ticket'):
    """Set the current ticket context for the duration of this ticket's processing.

    This is called at the START of ticket processing and kept alive until completion.
    All tools can access this context to get ticket data (issue, subject, company).

    Thread-safe for parallel processing of different tickets.
    """
    global _current_ticket
    with _context_lock:
        _current_ticket = ticket


def get_current_ticket() -> Optional['Ticket']:
    """Get the current ticket context.

    Tools call this to access ticket data during processing.
    Returns the Ticket object that's currently being processed.
    """
    with _context_lock:
        return _current_ticket


def clear_current_ticket():
    """Clear the current ticket context after processing completes.

    This is called at the END of ticket processing to clean up.
    """
    global _current_ticket
    with _context_lock:
        _current_ticket = None


# Legacy compatibility - MAX_TOOL_CALLS is now defined per-tool in Ticket class
MAX_TOOL_CALLS = 3  # Kept for backward compatibility only
