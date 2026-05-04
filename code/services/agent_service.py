"""AgentService: Manages two-agent system (Classifier+Retriever and Responder)."""

from typing import Optional, Tuple
from agents.factory import create_agents
from observability import TicketLogger


class AgentService:
    """Singleton service that manages both triage agents.

    Responsibilities:
    - Create both agents once (performance optimization)
    - Cache agents for reuse across all tickets
    - Manage agent lifecycle
    - Provide agents to TicketProcessor
    """

    _instance: Optional['AgentService'] = None
    _classifier_retriever = None
    _responder = None
    _logger: Optional[TicketLogger] = None

    def __new__(cls):
        """Singleton pattern - only one AgentService per process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, logger: Optional[TicketLogger] = None) -> 'AgentService':
        """Initialize AgentService with both agents.

        Call this ONCE at startup in main.py

        Args:
            logger: TicketLogger instance for agent observability

        Returns:
            AgentService singleton instance
        """
        instance = cls()
        instance._logger = logger or TicketLogger()

        # Create both agents ONCE (reused for all tickets)
        if instance._classifier_retriever is None or instance._responder is None:
            print("[AGENT SERVICE] Creating both agents...")
            classifier_retriever, responder, instance._logger = create_agents(instance._logger)
            instance._classifier_retriever = classifier_retriever
            instance._responder = responder
            print("[AGENT SERVICE] Both agents ready")

        return instance

    def get_classifier_retriever(self):
        """Get the classifier+retriever agent (Agent 1).

        Returns:
            The cached classifier_retriever agent

        Raises:
            RuntimeError if initialize() was not called first
        """
        if self._classifier_retriever is None:
            raise RuntimeError(
                "AgentService not initialized. Call AgentService.initialize() first."
            )
        return self._classifier_retriever

    def get_responder(self):
        """Get the responder agent (Agent 2).

        Returns:
            The cached responder agent

        Raises:
            RuntimeError if initialize() was not called first
        """
        if self._responder is None:
            raise RuntimeError(
                "AgentService not initialized. Call AgentService.initialize() first."
            )
        return self._responder

    def get_both_agents(self) -> Tuple:
        """Get both agents.

        Returns:
            Tuple of (classifier_retriever, responder)
        """
        return self.get_classifier_retriever(), self.get_responder()

    def get_logger(self) -> TicketLogger:
        """Get the ticket logger.

        Returns:
            The TicketLogger instance
        """
        return self._logger or TicketLogger()

    def __repr__(self) -> str:
        status = "initialized" if self._classifier_retriever and self._responder else "not initialized"
        return f"AgentService({status})"


# Convenience function for getting the service
def get_agent_service() -> AgentService:
    """Get the AgentService singleton."""
    return AgentService()
