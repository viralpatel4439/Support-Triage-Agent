"""Tools for support ticket processing: search, classification, response saving.

Note: search_documents and save_response_to_csv are imported dynamically by agents
to avoid circular dependencies. Use direct imports instead:
  from tools.search_tools import search_documents
  from tools.csv_tools import save_response_to_csv
"""

from .ticket_context import set_current_ticket, get_current_ticket, clear_current_ticket

__all__ = [
    "set_current_ticket",
    "get_current_ticket",
    "clear_current_ticket",
]
