import threading
import re
from pathlib import Path

# Path to output CSV
OUTPUT_CSV = Path(__file__).parent.parent.parent / "support_tickets" / "output.csv"

# File lock for concurrent writes
_csv_lock = threading.Lock()

# Import ticket context
from .ticket_context import get_current_ticket


def _normalize_status(status_input: str) -> str:
    """Normalize status using regex. Returns 'replied' or 'escalated'."""
    if not isinstance(status_input, str):
        return "escalated"  # Default to safe option

    status_lower = status_input.lower().strip()

    # Try to match against valid values first
    if status_lower in ["replied", "escalated"]:
        return status_lower

    # Use regex patterns to infer the correct status
    if re.search(r'\b(reply|respond|answer|help)\b', status_lower):
        return "replied"
    if re.search(r'\b(escalat|urgent|high.risk|sensitive|outside|ambiguous)\b', status_lower):
        return "escalated"

    # Default to escalated (safer choice)
    return "escalated"


def _normalize_request_type(request_type_input: str) -> str:
    """Normalize request_type using regex. Returns one of: product_issue, feature_request, bug, invalid."""
    if not isinstance(request_type_input, str):
        return "invalid"

    request_type_lower = request_type_input.lower().strip()

    # Try to match against valid values first
    if request_type_lower in ["product_issue", "feature_request", "bug", "invalid"]:
        return request_type_lower

    # Use regex patterns to infer the correct type
    if re.search(r'\b(feature|request|enhancement|improvement)\b', request_type_lower):
        return "feature_request"
    if re.search(r'\b(bug|issue|problem|broken|crash|error|fail)\b', request_type_lower):
        if re.search(r'\b(feature|enhancement)\b', request_type_lower):
            return "feature_request"
        return "bug"
    if re.search(r'\b(product|issue|problem|help|support)\b', request_type_lower):
        return "product_issue"

    # Default to invalid
    return "invalid"

def _escape_csv_field(field):
    """Escape a field value for CSV format."""
    if field is None:
        return ""
    field_str = str(field)
    # If field contains comma, quote, or newline, wrap in quotes and escape internal quotes
    if "," in field_str or '"' in field_str or "\n" in field_str:
        field_str = '"' + field_str.replace('"', '""') + '"'
    return field_str

def _initialize_csv():
    """Create CSV file with headers if it doesn't exist. If it exists but is corrupted, reinitialize."""
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    expected_header = "issue,subject,company,response,product_area,status,request_type,justification"

    # Check if file exists and has valid header
    file_valid = False
    if OUTPUT_CSV.exists():
        try:
            with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line == expected_header:
                    file_valid = True
                    print(f"[DEBUG] CSV file exists with valid header")
                else:
                    print(f"[DEBUG] CSV file exists but header is invalid: {first_line[:50]}...")
        except Exception as e:
            print(f"[DEBUG] Error reading CSV file: {e}")

    # Create or reinitialize if invalid
    if not file_valid:
        print(f"[DEBUG] Initializing CSV file with headers")
        header = "issue,subject,company,response,product_area,status,request_type,justification\n"
        with open(OUTPUT_CSV, "w", encoding="utf-8") as f:
            f.write(header)
        print(f"[DEBUG] CSV file initialized with fresh headers")

def save_response_to_csv(
    ticket_id: int,
    status: str,
    product_area: str,
    response: str,
    justification: str,
    request_type: str,
) -> str:
    """
    Saves the final triage result for a support ticket to the output CSV file.
    New rows are appended on new lines with proper formatting.
    Thread-safe for parallel processing.

    FLEXIBLE VALIDATION: This function auto-corrects invalid values using regex patterns
    so agents don't need to be 100% accurate with enum values.

    Args:
        ticket_id: The row index of the ticket (from the input CSV). Required - must be positive int.
        status: 'replied' or 'escalated'. AUTO-CORRECTED via regex if invalid.
                - 'replied': you can answer from the corpus
                - 'escalated': high-risk, sensitive, ambiguous, or outside knowledge base
        product_area: The most relevant support category. OPTIONAL - defaults to 'general' if empty.
        response: The user-facing answer. OPTIONAL - defaults to placeholder if empty.
        justification: Explanation of routing/response decision. OPTIONAL - defaults to placeholder if empty.
        request_type: AUTO-CORRECTED via regex from variations like:
                - 'feature_request': for "feature", "request", "enhancement"
                - 'bug': for "bug", "broken", "crash", "error"
                - 'product_issue': for "product", "issue", "problem", "help"
                - 'invalid': default for unrecognized input

    Returns:
        Confirmation string on success, error message on failure.
    """
    print(f"\n[DEBUG ENTRY] save_response_to_csv called with ticket_id={ticket_id}")

    # Check tool call limit (per ticket)
    ticket = get_current_ticket()
    if ticket:
        allowed, call_count = ticket.can_call_tool("save_response_to_csv")
        if not allowed:
            return f"ERROR: Exceeded max 1 call to save_response_to_csv per ticket"
        print(f"🔧 [save_response_to_csv] ticket_id={ticket_id}, status={status} (call {call_count}/1)")
    else:
        print(f"[DEBUG] WARNING: get_current_ticket() returned None, will need ticket data from parameters")

    # Convert ticket_id to int if string
    if isinstance(ticket_id, str):
        try:
            ticket_id = int(ticket_id)
        except ValueError:
            return f"ERROR: ticket_id must be an integer. Got: {ticket_id}"

    # Validate required fields
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        return f"ERROR: ticket_id must be positive integer. Got: {ticket_id}"

    # Normalize status using regex (auto-correct invalid values)
    original_status = status
    status = _normalize_status(status)
    if original_status not in ["replied", "escalated"]:
        print(f"[DEBUG] Normalized status: '{original_status}' → '{status}'")

    # Normalize request_type using regex (auto-correct invalid values)
    original_request_type = request_type
    request_type = _normalize_request_type(request_type)
    if original_request_type not in ["product_issue", "feature_request", "bug", "invalid"]:
        print(f"[DEBUG] Normalized request_type: '{original_request_type}' → '{request_type}'")

    # Validate other required fields
    if not product_area or not isinstance(product_area, str):
        print(f"[DEBUG WARNING] product_area is empty or invalid, using 'general'")
        product_area = "general"

    if not response or not isinstance(response, str):
        response = f"Ticket {ticket_id} - see justification for details"

    if not justification or not isinstance(justification, str):
        justification = "No additional justification provided"

    try:
        # Initialize CSV if needed
        _initialize_csv()

        # Get ticket data from Ticket object
        if not ticket:
            print(f"[DEBUG ERROR] Ticket object is NONE! Thread ID context lookup failed")
            return f"ERROR: Ticket context not found (ticket is None)"

        print(f"[DEBUG] Got ticket from context: #{ticket.ticket_id}, company={ticket.company}")

        subject = ticket.subject if ticket.subject else ""
        company = ticket.company if ticket.company else ""
        issue = ticket.issue if ticket.issue else ""

        print(f"[DEBUG] Ticket data - issue: {len(issue)} chars, subject: {subject[:50] if subject else 'EMPTY'}, company: {company}")

        # Escape all fields for CSV
        escaped_issue = _escape_csv_field(issue)
        escaped_subject = _escape_csv_field(subject)
        escaped_company = _escape_csv_field(company)
        escaped_response = _escape_csv_field(response)
        escaped_product_area = _escape_csv_field(product_area)
        escaped_status = _escape_csv_field(status)
        escaped_request_type = _escape_csv_field(request_type)
        escaped_justification = _escape_csv_field(justification)

        # Build CSV row
        csv_row = f"{escaped_issue},{escaped_subject},{escaped_company},{escaped_response},{escaped_product_area},{escaped_status},{escaped_request_type},{escaped_justification}\n"

        print(f"[DEBUG] CSV row to write: {len(csv_row)} chars")

        # Write with lock for concurrent access
        with _csv_lock:
            print(f"[DEBUG] Acquiring lock for CSV write...")
            with open(OUTPUT_CSV, "a", encoding="utf-8") as f:
                f.write(csv_row)
                f.flush()
            print(f"[DEBUG] Row written and flushed")

        # Update Ticket object with response
        if ticket:
            ticket.set_response(response, justification, status)

        print(f"[DEBUG SUCCESS] Ticket {ticket_id} saved to output.csv")
        return f"✅ SAVED: Ticket {ticket_id} saved to output.csv with status={status}"

    except Exception as e:
        print(f"[DEBUG ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[DEBUG TRACEBACK]\n{traceback.format_exc()}")
        return f"ERROR: Cannot save to CSV: {str(e)}"
