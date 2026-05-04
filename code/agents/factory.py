"""Two-agent factory: Classifier+Retriever (Agent 1) and Responder (Agent 2)."""

from .classifier_retriever import create_classifier_retriever_agent
from .responder import create_responder_agent
from observability import TicketLogger


def create_agents(logger: TicketLogger = None):
    """Create both Agent 1 (Classifier+Retriever) and Agent 2 (Responder).

    Returns:
        tuple: (classifier_retriever_agent, responder_agent, logger)
    """
    if logger is None:
        logger = TicketLogger()

    print("[AGENTS] Creating classifier_retriever agent...")
    classifier_retriever = create_classifier_retriever_agent(logger)

    print("[AGENTS] Creating responder agent...")
    responder = create_responder_agent(logger)

    print("[AGENTS] Both agents ready")

    return classifier_retriever, responder, logger
