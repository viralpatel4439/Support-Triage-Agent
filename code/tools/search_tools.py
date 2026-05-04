"""Semantic search with smart section extraction."""

from embeddings.db import EmbeddingDB
from embeddings.smart_extraction import extract_relevant_content
from .ticket_context import get_current_ticket


def search_documents(company: str, query: str) -> str:
    """Search documents and return only relevant sections.

    Uses semantic search + smart extraction to return only the most
    relevant content from each document (< 2000 chars total).

    Args:
        company: 'HackerRank', 'Claude', or 'Visa'
        query: User's issue or question

    Returns:
        Only relevant sections from top documents (condensed, < 2000 chars)
    """
    # Check tool call limit (per ticket)
    ticket = get_current_ticket()
    if ticket:
        allowed, call_count = ticket.can_call_tool("search_documents")
        if not allowed:
            return f"ERROR: Max 3 searches per ticket"
        print(f"🔧 search_documents('{company}', '{query[:40]}...') - call {call_count}/3")

    # Validate input
    if company not in {"HackerRank", "Claude", "Visa"}:
        return f"ERROR: Invalid company '{company}'"
    if not query or not query.strip():
        return "ERROR: query cannot be empty"

    try:
        # Semantic search
        db = EmbeddingDB()
        results = db.search(company, query, top_k=5)  # Get top 5, then extract
        db.close()

        if not results:
            return f"No documents found for '{company}'"

        # Smart extraction for each document
        output_lines = [f"Found {len(results)} relevant documents:\n"]
        total_chars = len(output_lines[0])
        max_per_doc = 600

        for i, (title, content, score) in enumerate(results[:3], 1):  # Use top 3
            if total_chars > 1800:
                break

            # Smart extract relevant section
            relevant = extract_relevant_content(content, query, max_chars=max_per_doc)

            doc_text = f"\n[DOC {i}] {title.strip()} ({score:.0%})\n{relevant}\n"

            if total_chars + len(doc_text) <= 2000:
                output_lines.append(doc_text)
                total_chars += len(doc_text)

        result = "".join(output_lines)
        if len(result) > 2000:
            result = result[:1950] + "\n[...truncated]"

        print(f"[DEBUG] Returned {len(output_lines)-1} doc(s), {len(result)} chars")
        return result

    except FileNotFoundError:
        return "ERROR: Embedding database not found. Run: python embed_corpus.py"
    except Exception as e:
        return f"ERROR: Search failed: {str(e)}"


def save_response_to_csv(
    ticket_id: int,
    status: str,
    product_area: str,
    response: str,
    justification: str,
    request_type: str,
) -> str:
    """Save the final triage result to output CSV.

    Call this ONCE per ticket after you have the answer and are ready to save.

    Args:
        ticket_id: The row index of the ticket (from the input CSV).
        status: 'replied' if you answered, 'escalated' if human review needed.
        product_area: Category name from the documents (e.g., 'account-management', 'billing').
        response: Your answer to the user (must be grounded in documents).
        justification: Which document(s) you used (e.g., 'account-management/delete-account.md').
        request_type: 'product_issue', 'feature_request', 'bug', or 'invalid'.

    Returns:
        Confirmation of success or error message.
    """
    # Import here to avoid circular dependency
    from .csv_tools import save_response_to_csv as _save_to_csv
    return _save_to_csv(ticket_id, status, product_area, response, justification, request_type)
