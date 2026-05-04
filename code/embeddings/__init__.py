"""Embeddings module - local SQLite vector database with smart extraction."""

from .db import EmbeddingDB, init_embedding_db
from .smart_extraction import extract_relevant_content, SmartExtractor

__all__ = ["EmbeddingDB", "init_embedding_db", "extract_relevant_content", "SmartExtractor"]
